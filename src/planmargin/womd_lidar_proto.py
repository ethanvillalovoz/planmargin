"""Runtime descriptors for the minimal wire-compatible WOMD-LiDAR schema."""

from __future__ import annotations

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory


def _field(
    message: descriptor_pb2.DescriptorProto,
    name: str,
    number: int,
    field_type: int,
    *,
    repeated: bool = False,
    type_name: str | None = None,
    packed: bool = False,
) -> None:
    value = message.field.add(
        name=name,
        number=number,
        type=field_type,
        label=(
            descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            if repeated
            else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        ),
    )
    if type_name is not None:
        value.type_name = f".planmargin.womd.{type_name}"
    if packed:
        value.options.packed = True


def _message(
    schema: descriptor_pb2.FileDescriptorProto, name: str
) -> descriptor_pb2.DescriptorProto:
    return schema.message_type.add(name=name)


def _schema() -> descriptor_pb2.FileDescriptorProto:
    """Build the audited subset documented in womd_lidar_minimal.proto."""
    schema = descriptor_pb2.FileDescriptorProto(
        name="womd_lidar_minimal.proto",
        package="planmargin.womd",
        syntax="proto2",
    )
    types = descriptor_pb2.FieldDescriptorProto

    transform = _message(schema, "Transform")
    _field(transform, "transform", 1, types.TYPE_DOUBLE, repeated=True)

    calibration = _message(schema, "LaserCalibration")
    _field(calibration, "name", 1, types.TYPE_INT32)
    _field(calibration, "beam_inclinations", 2, types.TYPE_DOUBLE, repeated=True)
    _field(calibration, "beam_inclination_min", 3, types.TYPE_DOUBLE)
    _field(calibration, "beam_inclination_max", 4, types.TYPE_DOUBLE)
    _field(calibration, "extrinsic", 5, types.TYPE_MESSAGE, type_name="Transform")

    range_image = _message(schema, "CompressedRangeImage")
    _field(range_image, "range_image_delta_compressed", 1, types.TYPE_BYTES)
    _field(range_image, "range_image_pose_delta_compressed", 4, types.TYPE_BYTES)

    laser = _message(schema, "CompressedLaser")
    _field(laser, "name", 1, types.TYPE_INT32)
    _field(
        laser,
        "ri_return1",
        2,
        types.TYPE_MESSAGE,
        type_name="CompressedRangeImage",
    )
    _field(
        laser,
        "ri_return2",
        3,
        types.TYPE_MESSAGE,
        type_name="CompressedRangeImage",
    )

    frame = _message(schema, "CompressedFrameLaserData")
    _field(
        frame,
        "lasers",
        1,
        types.TYPE_MESSAGE,
        repeated=True,
        type_name="CompressedLaser",
    )
    _field(
        frame,
        "laser_calibrations",
        2,
        types.TYPE_MESSAGE,
        repeated=True,
        type_name="LaserCalibration",
    )
    _field(frame, "pose", 3, types.TYPE_MESSAGE, type_name="Transform")

    metadata = _message(schema, "Metadata")
    _field(metadata, "shape", 1, types.TYPE_INT32, repeated=True, packed=True)
    _field(
        metadata,
        "quant_precision",
        2,
        types.TYPE_FLOAT,
        repeated=True,
        packed=True,
    )

    delta = _message(schema, "DeltaEncodedData")
    _field(delta, "residual", 1, types.TYPE_SINT64, repeated=True, packed=True)
    _field(delta, "mask", 2, types.TYPE_UINT32, repeated=True, packed=True)
    _field(delta, "metadata", 3, types.TYPE_MESSAGE, type_name="Metadata")

    scenario = _message(schema, "Scenario")
    _field(scenario, "scenario_id", 5, types.TYPE_STRING)
    _field(
        scenario,
        "compressed_frame_laser_data",
        12,
        types.TYPE_MESSAGE,
        repeated=True,
        type_name="CompressedFrameLaserData",
    )
    return schema


_POOL = descriptor_pool.DescriptorPool()
_POOL.Add(_schema())


def _class(name: str) -> type:
    return message_factory.GetMessageClass(
        _POOL.FindMessageTypeByName(f"planmargin.womd.{name}")
    )


Scenario = _class("Scenario")
DeltaEncodedData = _class("DeltaEncodedData")
