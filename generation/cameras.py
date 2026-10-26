"""Camera configuration defaults and validation shared by the editor and generator.

Project poses are stored in inches and degrees, using +X forward, +Y left,
+Z up and the same roll/pitch/yaw rotation as WPILib.
"""

import math
import re


LIMELIGHT_OPTIONS = {
    "identifier": ("BACK_LEFT", "FRONT", "UPPER_FRONT", "LOWER_FRONT"),
    "camera_type": (
        "LIMELIGHT4", "LIMELIGHT4_W_HAILO8", "LIMELIGHT3G",
        "LIMELIGHT3", "LIMELIGHT3_W_CORAL",
    ),
    "usage": ("APRIL_TAGS", "OBJECT_DETECTION"),
    "pipeline": ("APRIL_TAG", "BUMPERS", "FUEL_PL", "COLOR_THRESHOLD", "UNKNOWN"),
    "led_mode": ("LED_OFF", "LED_PIPELINE_CONTROL", "LED_BLINK", "LED_ON", "LED_UNKNOWN"),
}
POSE_FIELDS = ("x", "y", "z", "pitch", "yaw", "roll")
ANGLE_FIELDS = ("pitch", "yaw", "roll")
DIMENSION_FIELDS = ("robot_length_in", "robot_width_in")
INCH_TO_METER = 0.0254
DECIMAL_PLACES = 4
LENGTH_UNITS = ("in", "m")
ANGLE_UNITS = ("deg", "rad")
# Multiply a stored inch/degree value by this factor to display it in the unit.
UNIT_FACTORS = {"in": 1.0, "m": INCH_TO_METER, "deg": 1.0, "rad": math.pi / 180}
# Keys understood by the generator's ``short_unit`` filter.
UNIT_LITERAL_KEYS = {"in": "inch", "m": "meter", "deg": "deg", "rad": "rad"}


def field_unit(config, field, camera=None):
    """Return the selected display/generation unit for one field.

    Per-field choices live in ``camera["units"]`` or ``config["dimension_units"]``;
    the robot-level ``length_unit`` / ``angle_unit`` are fallbacks for older projects.
    """
    angle = field in ANGLE_FIELDS
    default = config.get("angle_unit", "deg") if angle else config.get("length_unit", "in")
    source = camera.get("units", {}) if camera is not None else config.get("dimension_units", {})
    return source.get(field, default)


def _validate_units(units, fields, owner):
    if not isinstance(units, dict):
        raise ValueError(f"{owner}: units must be an object.")
    for field, unit in units.items():
        if field not in fields:
            raise ValueError(f"{owner}: unknown unit field {field}.")
        allowed = ANGLE_UNITS if field in ANGLE_FIELDS else LENGTH_UNITS
        if unit not in allowed:
            raise ValueError(f"{owner}: {field} unit must be one of {', '.join(allowed)}.")


def default_camera_config():
    return {
        "robot_length_in": 30.0,
        "robot_width_in": 30.0,
        "length_unit": "in",
        "angle_unit": "deg",
        "cameras": [],
    }


def new_camera(kind, cameras):
    if kind not in ("Limelight", "Quest"):
        raise ValueError(f"Unsupported camera type: {kind}")
    if kind == "Quest" and any(c["type"] == "Quest" for c in cameras):
        raise ValueError("DragonVision supports only one Quest per robot.")
    names = {c["name"] for c in cameras}
    number = 1
    while f"{kind.lower()}-{number}" in names:
        number += 1
    camera = {
        "type": kind,
        "name": f"{kind.lower()}-{number}",
        **{field: 0.0 for field in POSE_FIELDS},
    }
    if kind == "Limelight":
        used = {c["identifier"] for c in cameras if c["type"] == "Limelight"}
        available = [i for i in LIMELIGHT_OPTIONS["identifier"] if i not in used]
        if not available:
            raise ValueError("All four supported Limelight identifiers are already in use.")
        camera.update({key: values[0] for key, values in LIMELIGHT_OPTIONS.items()})
        camera["identifier"] = available[0]
    return camera


def validate_camera_config(config, *, structural_only=False):
    if not isinstance(config, dict):
        raise ValueError("Camera configuration must be an object.")
    for field in ("robot_length_in", "robot_width_in"):
        value = config.get(field)
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 < value <= 10000
        ):
            raise ValueError(f"{field} must be greater than 0 and at most 10000 inches.")
    if config.get("length_unit", "in") not in ("in", "m"):
        raise ValueError("Length unit must be in or m.")
    if config.get("angle_unit", "deg") not in ("deg", "rad"):
        raise ValueError("Angle unit must be deg or rad.")
    _validate_units(config.get("dimension_units", {}), DIMENSION_FIELDS, "Robot dimensions")
    cameras = config.get("cameras")
    if not isinstance(cameras, list):
        raise ValueError("Cameras must be a list.")
    names, identifiers = set(), set()
    quest_count = 0
    for camera in cameras:
        if not isinstance(camera, dict) or camera.get("type") not in ("Limelight", "Quest"):
            raise ValueError("Each camera must have type Limelight or Quest.")
        name = camera.get("name")
        if not isinstance(name, str):
            raise ValueError("Camera names must be strings.")
        if not structural_only and not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            raise ValueError("Camera names must start with a lowercase letter and use a-z, 0-9 or hyphens.")
        if not structural_only and name in names:
            raise ValueError(f"Duplicate camera name: {name}")
        names.add(name)
        for field in POSE_FIELDS:
            value = camera.get(field)
            limit = 36000 if field in ("pitch", "yaw", "roll") else 10000
            if (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or abs(value) > limit
            ):
                raise ValueError(f"{name}: {field} must be finite and within +/-{limit}.")
        _validate_units(camera.get("units", {}), POSE_FIELDS, name)
        if camera["type"] == "Limelight":
            for key, options in LIMELIGHT_OPTIONS.items():
                if not isinstance(camera.get(key), str) or (
                    not structural_only and camera[key] not in options
                ):
                    raise ValueError(f"{name}: unsupported {key}: {camera.get(key)}")
            identifier = camera["identifier"]
            if not structural_only and identifier in identifiers:
                raise ValueError(f"Duplicate Limelight identifier: {identifier}")
            identifiers.add(identifier)
        else:
            quest_count += 1
    if not structural_only and quest_count > 1:
        raise ValueError("DragonVision supports only one Quest per robot.")


def configured_robots(project_data):
    """Validate before rendering so invalid data never produces partial output."""
    robots = []
    project_robots = project_data.get("robots", {})
    for robot_id, robot in project_robots.items():
        if "camera_config" not in robot:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", robot_id):
            raise ValueError(f"Robot ID is not a valid C++ identifier: {robot_id}")
        team = robot.get("team_number")
        if isinstance(team, bool) or not isinstance(team, int) or team <= 0:
            raise ValueError(f"{robot_id}: camera generation requires a positive team number.")
        for other_id, other in project_robots.items():
            if other_id == robot_id:
                continue
            if other_id.upper() == robot_id.upper():
                raise ValueError(f"{robot_id} and {other_id} produce the same RobotIdentifier.")
            if other.get("team_number") == team:
                raise ValueError(
                    f"{robot_id} and {other_id} share team number {team}; "
                    "RobotIdentifier must distinguish camera configurations."
                )
        try:
            validate_camera_config(robot["camera_config"])
        except ValueError as error:
            raise ValueError(f"{robot_id}: {error}") from error
        config = robot["camera_config"]
        cameras = []
        for camera in config["cameras"]:
            rendered = dict(camera)
            rendered["units"] = {}
            for field in POSE_FIELDS:
                unit = field_unit(config, field, camera)
                rendered[field] = round(camera[field] * UNIT_FACTORS[unit], DECIMAL_PLACES)
                rendered["units"][field] = UNIT_LITERAL_KEYS[unit]
            cameras.append(rendered)
        robots.append({
            "robot_id": robot_id.upper(),
            "class_name": f"CameraConfig_{team}",
            "cameras": cameras,
        })
    return robots
