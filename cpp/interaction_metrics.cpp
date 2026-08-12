#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <optional>
#include <stdexcept>
#include <utility>

namespace py = pybind11;

namespace {

struct Point {
  double x;
  double y;
};

using Box = std::array<Point, 4>;
using Matrix = py::array_t<double, py::array::c_style | py::array::forcecast>;
using Mask = py::array_t<bool, py::array::c_style | py::array::forcecast>;

Point operator+(Point first, Point second) {
  return {first.x + second.x, first.y + second.y};
}

Point operator-(Point first, Point second) {
  return {first.x - second.x, first.y - second.y};
}

Point operator*(double scale, Point value) {
  return {scale * value.x, scale * value.y};
}

double dot(Point first, Point second) {
  return first.x * second.x + first.y * second.y;
}

double norm(Point value) { return std::hypot(value.x, value.y); }

Box oriented_box(double x, double y, double yaw, double length,
                 double width) {
  const Point forward{std::cos(yaw), std::sin(yaw)};
  const Point lateral{-forward.y, forward.x};
  const Point center{x, y};
  const double half_length = length / 2.0;
  const double half_width = width / 2.0;
  return {
      center + half_length * forward + half_width * lateral,
      center - half_length * forward + half_width * lateral,
      center - half_length * forward - half_width * lateral,
      center + half_length * forward - half_width * lateral,
  };
}

double point_segment_distance(Point point, Point start, Point end) {
  const Point segment = end - start;
  const double squared_length = dot(segment, segment);
  if (squared_length <= 1e-12) {
    return norm(point - start);
  }
  const double fraction = std::clamp(
      dot(point - start, segment) / squared_length, 0.0, 1.0);
  const Point projection = start + fraction * segment;
  return norm(point - projection);
}

double signed_separation(const Box& first, const Box& second) {
  std::array<Point, 8> axes{};
  std::size_t axis_count = 0;
  for (const Box* polygon : {&first, &second}) {
    for (std::size_t index = 0; index < polygon->size(); ++index) {
      const Point edge = (*polygon)[(index + 1) % polygon->size()] -
                         (*polygon)[index];
      const Point normal{-edge.y, edge.x};
      const double magnitude = norm(normal);
      if (magnitude > 1e-12) {
        axes[axis_count++] = (1.0 / magnitude) * normal;
      }
    }
  }

  bool separated = false;
  double minimum_overlap = std::numeric_limits<double>::infinity();
  for (std::size_t axis_index = 0; axis_index < axis_count; ++axis_index) {
    const Point axis = axes[axis_index];
    double first_min = std::numeric_limits<double>::infinity();
    double first_max = -std::numeric_limits<double>::infinity();
    double second_min = std::numeric_limits<double>::infinity();
    double second_max = -std::numeric_limits<double>::infinity();
    for (const Point point : first) {
      const double projection = dot(point, axis);
      first_min = std::min(first_min, projection);
      first_max = std::max(first_max, projection);
    }
    for (const Point point : second) {
      const double projection = dot(point, axis);
      second_min = std::min(second_min, projection);
      second_max = std::max(second_max, projection);
    }
    const double overlap =
        std::min(first_max, second_max) - std::max(first_min, second_min);
    minimum_overlap = std::min(minimum_overlap, overlap);
    if (overlap < 0.0) {
      separated = true;
    }
  }
  if (!separated) {
    return -minimum_overlap;
  }

  double minimum_distance = std::numeric_limits<double>::infinity();
  for (const auto& pair :
       {std::pair<const Box*, const Box*>{&first, &second},
        std::pair<const Box*, const Box*>{&second, &first}}) {
    for (const Point point : *pair.first) {
      for (std::size_t index = 0; index < pair.second->size(); ++index) {
        minimum_distance = std::min(
            minimum_distance,
            point_segment_distance(
                point, (*pair.second)[index],
                (*pair.second)[(index + 1) % pair.second->size()]));
      }
    }
  }
  return minimum_distance;
}

std::optional<double> longitudinal_ttc(const double* sdc,
                                       const double* lead) {
  const Point forward{std::cos(sdc[2]), std::sin(sdc[2])};
  const Point relative_position{lead[0] - sdc[0], lead[1] - sdc[1]};
  const double center_gap = dot(relative_position, forward);
  if (center_gap <= 0.0) {
    return std::nullopt;
  }
  const double bumper_gap = center_gap - (sdc[5] + lead[5]) / 2.0;
  if (bumper_gap <= 0.0) {
    return 0.0;
  }
  const Point relative_velocity{sdc[3] - lead[3], sdc[4] - lead[4]};
  const double closing_speed = dot(relative_velocity, forward);
  if (closing_speed <= 1e-6) {
    return std::nullopt;
  }
  return bumper_gap / closing_speed;
}

py::tuple aggregate_interaction_metrics(const Matrix& sdc_values,
                                        const Matrix& lead_values,
                                        const Mask& sdc_valid,
                                        const Mask& lead_valid) {
  const auto sdc = sdc_values.unchecked<2>();
  const auto lead = lead_values.unchecked<2>();
  const auto sdc_mask = sdc_valid.unchecked<1>();
  const auto lead_mask = lead_valid.unchecked<1>();
  if (sdc.shape(1) != 7 || lead.shape(1) != 7) {
    throw std::invalid_argument("vehicle matrices must have seven columns");
  }
  if (sdc.shape(0) != lead.shape(0) || sdc.shape(0) != sdc_mask.shape(0) ||
      sdc.shape(0) != lead_mask.shape(0)) {
    throw std::invalid_argument("vehicle matrices and masks must be aligned");
  }

  std::size_t jointly_valid = 0;
  double minimum_separation = std::numeric_limits<double>::infinity();
  std::optional<double> minimum_ttc;
  for (py::ssize_t index = 0; index < sdc.shape(0); ++index) {
    if (!sdc_mask(index) || !lead_mask(index)) {
      continue;
    }
    std::array<double, 7> sdc_row{};
    std::array<double, 7> lead_row{};
    for (py::ssize_t column = 0; column < 7; ++column) {
      sdc_row[column] = sdc(index, column);
      lead_row[column] = lead(index, column);
      if (!std::isfinite(sdc_row[column]) ||
          !std::isfinite(lead_row[column])) {
        throw std::invalid_argument("oriented-box inputs must be finite");
      }
    }
    if (sdc_row[5] <= 0.0 || sdc_row[6] <= 0.0 || lead_row[5] <= 0.0 ||
        lead_row[6] <= 0.0) {
      throw std::invalid_argument("oriented-box dimensions must be positive");
    }
    const Box first = oriented_box(sdc_row[0], sdc_row[1], sdc_row[2],
                                   sdc_row[5], sdc_row[6]);
    const Box second = oriented_box(lead_row[0], lead_row[1], lead_row[2],
                                    lead_row[5], lead_row[6]);
    minimum_separation =
        std::min(minimum_separation, signed_separation(first, second));
    const std::optional<double> ttc =
        longitudinal_ttc(sdc_row.data(), lead_row.data());
    if (ttc && (!minimum_ttc || *ttc < *minimum_ttc)) {
      minimum_ttc = ttc;
    }
    ++jointly_valid;
  }
  if (jointly_valid == 0) {
    throw std::invalid_argument("tracks have no jointly valid states");
  }
  return py::make_tuple(
      jointly_valid, minimum_separation,
      minimum_ttc ? py::cast(*minimum_ttc) : py::none());
}

}  // namespace

PYBIND11_MODULE(_geometry, module) {
  module.doc() = "PlanMargin C++20 interaction-metrics kernels";
  module.def("aggregate_interaction_metrics", &aggregate_interaction_metrics,
             py::arg("sdc_values"), py::arg("lead_values"),
             py::arg("sdc_valid"), py::arg("lead_valid"));
}
