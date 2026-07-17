"""Pure naming, formatting, and unit-mapping helpers for code generation.

This module is intentionally free of any project/template state: every function
here is a pure transformation used both as a Jinja2 filter and internally by the
HW / Control Data / State builders. Keeping it standalone lets every builder share
one consistent source of truth for identifiers, C++ types, and unit mappings.
"""

import re


# Maps hardware types to the friendly suffix used in member variable names.
MEMBER_TYPE_SUFFIX = {
    "TalonFX": "Motor",
    "TalonFXS": "Motor",
    "CANCoder": "CANcoder",
    "Solenoid": "Solenoid",
    "CANdi": "CANdi",
    "DigitalInput": "DigitalInput",
}

# Maps hardware types to their fully-qualified C++ class.
HARDWARE_CPP_TYPE = {
    "Solenoid": "frc::Solenoid",
    "DigitalInput": "frc::DigitalInput",
}

# Maps a control-data unit to the matching C++ units type.
UNIT_PREFIXES = {
    "double": "double",
    "turn": "wpi::units::angle::turn_t",
    "inch": "wpi::units::length::inch_t",
    "deg": "wpi::units::angle::degree_t",
    "RPM": "wpi::units::angular_velocity::revolutions_per_minute_t",
    "volt": "wpi::units::voltage::volt_t",
}

# Maps a control-data unit to the units library header it requires.
UNIT_INCLUDES = {
    "turn": "wpi/units/angle.hpp",
    "inch": "wpi/units/length.hpp",
    "deg": "wpi/units/angle.hpp",
    "RPM": "wpi/units/angular_velocity.hpp",
    "volt": "wpi/units/voltage.hpp",
}

# Maps a control-data unit to the short suffix used in method/member naming.
SHORT_UNIT_SUFFIX = {
    "double": "",
    "turn": "_tr",
    "inch": "_in",
    "deg": "_deg",
    "RPM": "_rpm",
    "volt": "_V",
}

# Hardware types that are motors (drive ControlData/Slot0 logic).
MOTOR_TYPES = ("TalonFX", "TalonFXS")

# Control-request name fragments that indicate a closed-loop (PID slot) request.
CLOSED_LOOP_KEYWORDS = ("Position", "Velocity", "MotionMagic")


def pascal_case(name):
    """PascalCase a name while preserving existing internal capitals.

    "intake" -> "Intake", "intake_roller" -> "IntakeRoller",
    "PercentOut" -> "PercentOut" (unchanged).
    """
    parts = [p for p in re.split(r"[\s_\-]+", str(name)) if p]
    return "".join(p[0].upper() + p[1:] for p in parts)


def camel_case(name):
    """camelCase a name: PascalCase, then lowercase the first letter."""
    pascal = pascal_case(name)
    return pascal[0].lower() + pascal[1:] if pascal else pascal


def upper_camel_case(name):
    """UpperCamelCase a name: PascalCase, then capitalize the first letter."""
    pascal = pascal_case(name)
    return pascal[0].upper() + pascal[1:] if pascal else pascal


def state_parts(name):
    """Split a state display name into normalized UPPER tokens.

    Accepts any of "Empty Hopper", "empty_hopper", "EmptyHopper", or an
    already-prefixed "STATE_EMPTY_HOPPER" and yields ["EMPTY", "HOPPER"].
    """
    base = str(name).strip()
    if base.upper().startswith("STATE_"):
        base = base[len("STATE_"):]
    # Insert a separator at camelCase boundaries, then normalize delimiters.
    base = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", base)
    base = re.sub(r"[\s\-]+", "_", base)
    return [p for p in base.split("_") if p]


def state_enum(name):
    """Derive the C++ enum identifier from a display name (-> STATE_EMPTY_HOPPER)."""
    parts = state_parts(name)
    return "STATE_" + "_".join(p.upper() for p in parts) if parts else "STATE_OFF"


def state_class(name):
    """Derive the PascalCase command suffix from a display name (-> EmptyHopper)."""
    parts = state_parts(name)
    return "".join(p.capitalize() for p in parts) if parts else "Off"


def member_variable(hw):
    """Build a C++ member variable name from a hardware dict (-> m_intakeMotor).

    Format is m_<camelCaseName><FriendlyType>, e.g. name "intake_roller" of
    type "TalonFX" becomes "m_intakeRollerMotor".
    If it is ControlData, then just use the camelCaseName without a suffix, e.g.
    "PercentOut" becomes "m_percentOut".
    """
    name = hw.get("name", "") if isinstance(hw, dict) else str(hw)
    hw_type = hw.get("type", "") if isinstance(hw, dict) else ""

    parts = [p for p in re.split(r"[\s_\-]+", name) if p]
    if parts:
        camel = parts[0][0].lower() + parts[0][1:]
        camel += "".join(p[0].upper() + p[1:] for p in parts[1:])
    else:
        camel = ""

    suffix = MEMBER_TYPE_SUFFIX.get(hw_type, hw_type)
    if hw_type == "ControlData":
        suffix = ""

    return f"m_{camel}{suffix}"


def cpp_type(hw_type):
    """Return the fully-qualified C++ class for a hardware type."""
    return HARDWARE_CPP_TYPE.get(hw_type, f"ctre::phoenix6::hardware::{hw_type}")


def get_unit(unit):
    """Map a control data unit to the appropriate C++ type prefix."""
    return UNIT_PREFIXES.get(unit, "double")


def get_short_unit(unit):
    """Map a control data unit to a short suffix for method naming."""
    return SHORT_UNIT_SUFFIX.get(unit, "")


def sig_enum(type_name):
    """Build a formatter that renders a fully-qualified Phoenix 6 signal enum."""
    return lambda v: f"ctre::phoenix6::signals::{type_name}::{v}"


def cpp_bool(value):
    """Render a Python truthiness as a C++ bool literal."""
    return "true" if value else "false"


def cpp_num(value):
    """Render a JSON number/bool as a C++ literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def is_closed_loop(control_request):
    """A control request drives a PID slot when it is position/velocity based."""
    return any(k in (control_request or "") for k in CLOSED_LOOP_KEYWORDS)


def request_value_property(control_request):
    """Pick the control-request property that holds the commanded target.

    PositionVoltage/MotionMagic -> Position, VelocityVoltage -> Velocity,
    DutyCycleOut/VoltageOut -> Output.
    """
    cr = control_request or ""
    if "Velocity" in cr:
        return "Velocity"
    if "Position" in cr or "MotionMagic" in cr:
        return "Position"
    return "Output"


def generate_target_method(target):
    """Derive the C++ setter method name for a state target.

    Motor targets become UpdateTarget<MotorName><ControlData>, e.g. a motor
    named "intake" driven by the "PercentOut" control data yields
    "UpdateTargetIntakePercentOut".
    Solenoid targets become UpdateSolenoid<SolenoidName>ActiveTarget.
    """
    if "HardwareName" in target:
        motor = pascal_case(target.get("HardwareName", ""))
        control = pascal_case(target.get("ControlData", ""))
        return f"UpdateTarget{motor}{control}"

    if "SolenoidName" in target:
        # TODO: add support for double solenoids
        solenoid = pascal_case(target.get("SolenoidName", ""))
        return f"UpdateSolenoid{solenoid}ActiveTarget"

    return "UpdateTargetValue"
