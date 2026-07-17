"""Static application constants for the Dragon Code Generator GUI.

These values are pure data (no Qt / no logic) so they can be shared freely
between the GUI, the data model, and any tooling without import side effects.
"""

DEFAULT_PROJECT = {"project_name": "New_FRC_Project", "robots": {}}
APP_SETTINGS_FILE = "tool_settings.json"

VERSION = "2026.1.0"

# Control-data target unit options (shared by the enum dropdown and the
# motor-target unit picker).
UNIT_OPTIONS = ["double", "turn", "inch", "deg", "RPM", "volt"]

# --- ENUM FIELD MAPPINGS ---
# Maps field names to their allowed enum values from CTRE Phoenix6 library
ENUM_FIELDS = {
    # Motor bridge neutral mode
    "NeutralModeValue": ["Coast", "Brake"],

    # Motor inversion
    "InvertedValue": ["CounterClockwise_Positive", "Clockwise_Positive"],

    # Limit switch sources (forward)
    "ForwardLimitSourceValue": ["LimitSwitchPin", "RemoteTalonFX", "RemoteCANifier", "RemoteCANcoder",
                       "RemoteCANrange", "RemoteCANdiS1", "RemoteCANdiS2", "Disabled"],

    # Limit switch sources (reverse)
    "ReverseLimitSourceValue": ["LimitSwitchPin", "RemoteTalonFX", "RemoteCANifier", "RemoteCANcoder",
                       "RemoteCANrange", "RemoteCANdiS1", "RemoteCANdiS2", "Disabled"],

    # Limit switch types
    "ForwardLimitTypeValue": ["NormallyOpen", "NormallyClosed"],
    "ReverseLimitTypeValue": ["NormallyOpen", "NormallyClosed"],

    # Feedback sensor sources
    "FeedbackSensorSourceValue": ["RotorSensor", "RemoteCANcoder", "RemotePigeon2Yaw", "RemotePigeon2Pitch",
                               "RemotePigeon2Roll", "FusedCANcoder", "SyncCANcoder",
                               "RemoteCANdiPWM1", "RemoteCANdiPWM2", "RemoteCANdiQuadrature",
                               "FusedCANdiPWM1", "FusedCANdiPWM2", "FusedCANdiQuadrature",
                               "SyncCANdiPWM1", "SyncCANdiPWM2"],

    #External feedback sensor sources
    "ExternalFeedbackSensorSource": ["RotorSensor", "RemoteCANcoder", "RemotePigeon2Yaw", "RemotePigeon2Pitch",
                               "RemotePigeon2Roll", "FusedCANcoder", "SyncCANcoder",
                               "RemoteCANdiPWM1", "RemoteCANdiPWM2", "RemoteCANdiQuadrature",
                               "FusedCANdiPWM1", "FusedCANdiPWM2", "FusedCANdiQuadrature",
                               "SyncCANdiPWM1", "SyncCANdiPWM2"],

    # Gravity feedforward type
    "GravityTypeValue": ["Elevator_Static", "Arm_Cosine"],

    # Static feedforward sign
    "StaticFeedforwardSignValue": ["UseVelocitySign", "UseClosedLoopSign"],

    # TalonFXS commutation / motor arrangement
    "MotorArrangementValue": ["Minion_JST", "Brushed_DC", "NEO_JST", "NEO550_JST", "VORTEX_JST"],

    # CANdi S1/S2 float states
    "S1FloatStateValue": ["FloatDetect", "PullHigh", "PullLow", "BusKeeper"],
    "S2FloatStateValue": ["FloatDetect", "PullHigh", "PullLow", "BusKeeper"],

    # CANdi S1/S2 close states
    "S1CloseStateValue": ["CloseWhenNotHigh", "CloseWhenNotLow", "CloseWhenNotFloating",
                       "CloseWhenHigh", "CloseWhenLow", "CloseWhenFloating"],
    "S2CloseStateValue": ["CloseWhenNotHigh", "CloseWhenNotLow", "CloseWhenNotFloating",
                       "CloseWhenHigh", "CloseWhenLow", "CloseWhenFloating"],

    # Control Request
    "ControlRequest": ["DifferentialDutyCycle", "DifferentialMotionMagicExpoDutyCycle",  "DutyCycleOut", "DynamicMotionMagicDutyCycle", "DynamicMotionMagicExpoDutyCycle",
                         "DynamicMotionMagicExpoTorqueCurrentFOC", "DynamicMotionMagicExpoVoltage", "DynamicMotionMagicTorqueCurrentFOC", "DynamicMotionMagicVoltage",
                        "MotionMagicDutyCycle", "MotionMagicExpoDutyCycle", "MotionMagicExpoTorqueCurrentFOC", "MotionMagicExpoVoltage", "MotionMagicTorqueCurrentFOC",
                       "MotionMagicVelocityDutyCycle", "MotionMagicVelocityTorqueCurrentFOC", "MotionMagicVelocityVoltage", "MotionMagicVoltage",
                       "PositionDutyCycle", "PositionTorqueCurrentFOC", "PositionVoltage",  "TorqueCurrentFOC", "VelocityDutyCycle",
                         "VelocityTorqueCurrentFOC", "VelocityVoltage", "VoltageOut"],

    # CANCoder Magnet Sensor Configs
    "SensorDirection": ["CounterClockwise_Positive", "Clockwise_Positive"],
    "AbsoluteSensorDiscontinuityPoint": ["1.0_tr", "0.5_tr", "0.0_tr"],

    # Control data target unit
    "Unit": UNIT_OPTIONS,

    # ClosedLoopRampsConfigs
    "ClosedLoopRampType": [
        "DutyCycleClosedLoopRampPeriod",
        "VoltageClosedLoopRampPeriod",
        "TorqueClosedLoopRampPeriod",
    ],

    # OpenLoopRampsConfigs
    "OpenLoopRampType": [
        "DutyCycleOpenLoopRampPeriod",
        "VoltageOpenLoopRampPeriod",
        "TorqueOpenLoopRampPeriod",
    ],

}
