// Copyright 2026 PlanMargin contributors
// SPDX-License-Identifier: Apache-2.0

#include <NvInfer.h>
#include <cuda_runtime_api.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::int64_t kFeatureWidth = 66;
constexpr std::int64_t kTrajectoryWidth = 60;

class Logger final : public nvinfer1::ILogger {
 public:
  void log(Severity severity, const char* message) noexcept override {
    if (severity <= Severity::kWARNING) {
      std::cerr << "TensorRT: " << message << '\n';
    }
  }
};

template <typename T>
struct Destroy {
  void operator()(T* value) const noexcept { delete value; }
};

template <typename T>
using TrtPtr = std::unique_ptr<T, Destroy<T>>;

void check_cuda(cudaError_t result, const char* operation) {
  if (result != cudaSuccess) {
    throw std::runtime_error(std::string(operation) + ": " +
                             cudaGetErrorString(result));
  }
}

std::vector<char> read_binary(const std::string& path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) throw std::runtime_error("cannot open engine: " + path);
  const auto size = stream.tellg();
  if (size <= 0) throw std::runtime_error("engine is empty: " + path);
  std::vector<char> bytes(static_cast<std::size_t>(size));
  stream.seekg(0);
  stream.read(bytes.data(), size);
  if (!stream) throw std::runtime_error("cannot read engine: " + path);
  return bytes;
}

double percentile(std::vector<float> values, double quantile) {
  if (values.empty()) throw std::runtime_error("no latency samples");
  std::sort(values.begin(), values.end());
  const double index = quantile * static_cast<double>(values.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(index));
  const auto upper = static_cast<std::size_t>(std::ceil(index));
  const double fraction = index - static_cast<double>(lower);
  return values[lower] * (1.0 - fraction) + values[upper] * fraction;
}

int parse_positive(const char* value, const char* name) {
  const int parsed = std::stoi(value);
  if (parsed <= 0) throw std::invalid_argument(std::string(name) + " must be positive");
  return parsed;
}

struct Arguments {
  std::string engine;
  int batch{1};
  int warmup{50};
  int iterations{500};
  std::string mode{"both"};
};

Arguments parse_arguments(int argc, char** argv) {
  Arguments args;
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (index + 1 >= argc) throw std::invalid_argument("missing value for " + key);
    const char* value = argv[++index];
    if (key == "--engine") args.engine = value;
    else if (key == "--batch") args.batch = parse_positive(value, "batch");
    else if (key == "--warmup") args.warmup = parse_positive(value, "warmup");
    else if (key == "--iterations") args.iterations = parse_positive(value, "iterations");
    else if (key == "--mode") args.mode = value;
    else throw std::invalid_argument("unknown argument: " + key);
  }
  if (args.engine.empty()) throw std::invalid_argument("--engine is required");
  if (args.mode != "device" && args.mode != "end-to-end" && args.mode != "both") {
    throw std::invalid_argument("--mode must be device, end-to-end, or both");
  }
  return args;
}

struct Summary {
  double mean_ms;
  double p50_ms;
  double p95_ms;
  double p99_ms;
};

Summary summarize(const std::vector<float>& samples) {
  const double mean = std::accumulate(samples.begin(), samples.end(), 0.0) /
                      static_cast<double>(samples.size());
  return {mean, percentile(samples, 0.50), percentile(samples, 0.95),
          percentile(samples, 0.99)};
}

void write_summary(std::ostream& output, const Summary& value) {
  output << "{\"mean\":" << value.mean_ms << ",\"p50\":" << value.p50_ms
         << ",\"p95\":" << value.p95_ms << ",\"p99\":" << value.p99_ms
         << '}';
}

void require_tensor(const nvinfer1::ICudaEngine& engine, const char* name,
                    nvinfer1::TensorIOMode mode) {
  if (engine.getTensorIOMode(name) != mode) {
    throw std::runtime_error(std::string("missing or invalid tensor: ") + name);
  }
  if (engine.getTensorDataType(name) != nvinfer1::DataType::kFLOAT) {
    throw std::runtime_error(std::string("expected float tensor: ") + name);
  }
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Arguments args = parse_arguments(argc, argv);
    Logger logger;
    const auto engine_bytes = read_binary(args.engine);
    TrtPtr<nvinfer1::IRuntime> runtime{nvinfer1::createInferRuntime(logger)};
    if (!runtime) throw std::runtime_error("failed to create TensorRT runtime");
    TrtPtr<nvinfer1::ICudaEngine> engine{runtime->deserializeCudaEngine(
        engine_bytes.data(), engine_bytes.size())};
    if (!engine) throw std::runtime_error("failed to deserialize TensorRT engine");
    TrtPtr<nvinfer1::IExecutionContext> context{engine->createExecutionContext()};
    if (!context) throw std::runtime_error("failed to create execution context");

    require_tensor(*engine, "features", nvinfer1::TensorIOMode::kINPUT);
    require_tensor(*engine, "constant_velocity", nvinfer1::TensorIOMode::kINPUT);
    require_tensor(*engine, "trajectory", nvinfer1::TensorIOMode::kOUTPUT);
    if (!context->setInputShape("features", nvinfer1::Dims2(args.batch, kFeatureWidth)) ||
        !context->setInputShape("constant_velocity",
                                nvinfer1::Dims2(args.batch, kTrajectoryWidth))) {
      throw std::runtime_error("batch is outside the engine optimization profile");
    }

    const std::size_t feature_bytes =
        static_cast<std::size_t>(args.batch * kFeatureWidth) * sizeof(float);
    const std::size_t trajectory_bytes =
        static_cast<std::size_t>(args.batch * kTrajectoryWidth) * sizeof(float);
    void* features = nullptr;
    void* baseline = nullptr;
    void* output = nullptr;
    void* host_features = nullptr;
    void* host_baseline = nullptr;
    void* host_output = nullptr;
    cudaStream_t stream{};
    cudaEvent_t start{};
    cudaEvent_t stop{};
    check_cuda(cudaMalloc(&features, feature_bytes), "cudaMalloc(features)");
    check_cuda(cudaMalloc(&baseline, trajectory_bytes), "cudaMalloc(baseline)");
    check_cuda(cudaMalloc(&output, trajectory_bytes), "cudaMalloc(output)");
    check_cuda(cudaMallocHost(&host_features, feature_bytes),
               "cudaMallocHost(features)");
    check_cuda(cudaMallocHost(&host_baseline, trajectory_bytes),
               "cudaMallocHost(baseline)");
    check_cuda(cudaMallocHost(&host_output, trajectory_bytes),
               "cudaMallocHost(output)");
    std::fill_n(static_cast<float*>(host_features),
                static_cast<std::size_t>(args.batch * kFeatureWidth), 0.0F);
    std::fill_n(static_cast<float*>(host_baseline),
                static_cast<std::size_t>(args.batch * kTrajectoryWidth), 0.0F);
    check_cuda(cudaMemset(features, 0, feature_bytes), "cudaMemset(features)");
    check_cuda(cudaMemset(baseline, 0, trajectory_bytes), "cudaMemset(baseline)");
    check_cuda(cudaStreamCreate(&stream), "cudaStreamCreate");
    check_cuda(cudaEventCreate(&start), "cudaEventCreate(start)");
    check_cuda(cudaEventCreate(&stop), "cudaEventCreate(stop)");

    const auto cleanup = [&]() {
      cudaEventDestroy(start);
      cudaEventDestroy(stop);
      cudaStreamDestroy(stream);
      cudaFreeHost(host_output);
      cudaFreeHost(host_baseline);
      cudaFreeHost(host_features);
      cudaFree(output);
      cudaFree(baseline);
      cudaFree(features);
    };

    if (!context->setTensorAddress("features", features) ||
        !context->setTensorAddress("constant_velocity", baseline) ||
        !context->setTensorAddress("trajectory", output)) {
      cleanup();
      throw std::runtime_error("failed to bind TensorRT tensor addresses");
    }

    const auto enqueue = [&]() {
      if (!context->enqueueV3(stream)) {
        throw std::runtime_error("TensorRT enqueue failed");
      }
    };
    const auto enqueue_end_to_end = [&]() {
      check_cuda(cudaMemcpyAsync(features, host_features, feature_bytes,
                                 cudaMemcpyHostToDevice, stream),
                 "cudaMemcpyAsync(features H2D)");
      check_cuda(cudaMemcpyAsync(baseline, host_baseline, trajectory_bytes,
                                 cudaMemcpyHostToDevice, stream),
                 "cudaMemcpyAsync(baseline H2D)");
      enqueue();
      check_cuda(cudaMemcpyAsync(host_output, output, trajectory_bytes,
                                 cudaMemcpyDeviceToHost, stream),
                 "cudaMemcpyAsync(output D2H)");
    };

    for (int index = 0; index < args.warmup; ++index) {
      if (args.mode == "end-to-end" || args.mode == "both") {
        enqueue_end_to_end();
      } else {
        enqueue();
      }
    }
    check_cuda(cudaStreamSynchronize(stream), "cudaStreamSynchronize(warmup)");

    std::vector<float> device_latencies;
    if (args.mode == "device" || args.mode == "both") {
      device_latencies.reserve(static_cast<std::size_t>(args.iterations));
      for (int index = 0; index < args.iterations; ++index) {
        check_cuda(cudaEventRecord(start, stream), "cudaEventRecord(start)");
        enqueue();
        check_cuda(cudaEventRecord(stop, stream), "cudaEventRecord(stop)");
        check_cuda(cudaEventSynchronize(stop), "cudaEventSynchronize(stop)");
        float elapsed_ms = 0.0F;
        check_cuda(cudaEventElapsedTime(&elapsed_ms, start, stop),
                   "cudaEventElapsedTime");
        device_latencies.push_back(elapsed_ms);
      }
    }

    std::vector<float> end_to_end_latencies;
    if (args.mode == "end-to-end" || args.mode == "both") {
      end_to_end_latencies.reserve(static_cast<std::size_t>(args.iterations));
      for (int index = 0; index < args.iterations; ++index) {
        const auto before = std::chrono::steady_clock::now();
        enqueue_end_to_end();
        check_cuda(cudaStreamSynchronize(stream),
                   "cudaStreamSynchronize(end-to-end)");
        const auto after = std::chrono::steady_clock::now();
        const auto elapsed =
            std::chrono::duration<double, std::milli>(after - before).count();
        end_to_end_latencies.push_back(static_cast<float>(elapsed));
      }
    }

    const Summary device = device_latencies.empty()
                               ? Summary{0.0, 0.0, 0.0, 0.0}
                               : summarize(device_latencies);
    const Summary end_to_end = end_to_end_latencies.empty()
                                   ? Summary{0.0, 0.0, 0.0, 0.0}
                                   : summarize(end_to_end_latencies);
    const double selected_mean = args.mode == "device" ? device.mean_ms
                                                       : end_to_end.mean_ms;
    const double throughput =
        static_cast<double>(args.batch) * 1000.0 / selected_mean;
    std::cout << std::fixed << std::setprecision(6)
              << "{\"record_type\":\"planmargin.tensorrt_cpp_benchmark\","
              << "\"schema_version\":\"2.0.0\","
              << "\"batch_size\":" << args.batch << ','
              << "\"warmup_iterations\":" << args.warmup << ','
              << "\"measured_iterations\":" << args.iterations << ','
              << "\"mode\":\"" << args.mode << "\","
              << "\"measurement_boundary\":\"pinned host input to pinned host output\","
              << "\"device_latency_ms\":";
    if (device_latencies.empty()) {
      std::cout << "null";
    } else {
      write_summary(std::cout, device);
    }
    std::cout << ",\"end_to_end_latency_ms\":";
    if (end_to_end_latencies.empty()) {
      std::cout << "null";
    } else {
      write_summary(std::cout, end_to_end);
    }
    std::cout << ",\"throughput_samples_per_second\":" << throughput << "}\n";
    cleanup();
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "planmargin_tensorrt_runner: " << error.what() << '\n';
    return 2;
  }
}
