"""Factory functions for default hardware / control-data / state-target configs.

Every function returns a fresh dictionary, so callers can mutate the result
without affecting other instances. These are pure data builders with no Qt or
model dependencies.
"""


def default_motor_target(hw_name=""):
    """Default state target for a TalonFX / TalonFXS motor."""
    return {
        "HardwareName": hw_name,
        "Enabled": True,
        "TargetValue": 0.0,
        "ControlData": "",
        "Unit": "double",
    }


def default_solenoid_target(sol_name=""):
    """Default state target for a Solenoid."""
    return {
        "SolenoidName": sol_name,
        "Enabled": True,
        "State": False,
    }


def default_control_data():
    """Default control-data block."""
    return {
        "name": "ControlData",
        "ControlRequest": "DutyCycleOut",
        "Unit": "double",
        "p": 0.0,
        "i": 0.0,
        "d": 0.0,
        "f": 0.0,
        "velocity_gain": 0.0,
        "acceleration_gain": 0.0,
        "static_friction_gain": 0.0,
        "integral_zone": 0.0,
        "max_acceleration": 0.0,
        "cruise_velocity": 0.0,
        "GravityTypeValue": "Elevator_Static",
        "StaticFeedforwardSignValue": "UseVelocitySign",
    }


# Name of the control-data block auto-created for every new mechanism. New
# states default their motor targets to this block.
DEFAULT_CONTROL_DATA_NAME = "PercentOut"


def default_percent_out_control_data():
    """The default ``PercentOut`` (DutyCycleOut) control-data block."""
    cd = default_control_data()
    cd["name"] = DEFAULT_CONTROL_DATA_NAME
    cd["ControlRequest"] = "DutyCycleOut"
    return cd


def default_hardware(hw_type, name):
    """Build the default config dictionary for a piece of hardware."""
    new_hw = {"type": hw_type, "name": name, "id": 0, "bus": "canivore"}

    if hw_type in ["TalonFX", "TalonFXS"]:
        new_hw.update(
            {
                "config": {
                    "CurrentLimits": {
                        "StatorCurrentLimit": 120.0,
                        "StatorCurrentLimitEnable": True,
                        "SupplyCurrentLimit": 70.0,
                        "SupplyCurrentLimitEnable": True,
                        "SupplyCurrentLowerLimit": 35.0,
                        "SupplyCurrentLowerTime": 0.0,
                    },
                    "Voltage": {
                        "PeakForwardVoltage": 11.0,
                        "PeakReverseVoltage": -11.0,
                    },
                    "Ramping": {
                        "ClosedLoopRampType": "TorqueClosedLoopRampPeriod",
                        "ClosedLoopRampTime": 0.25,
                        "OpenLoopRampType": "DutyCycleOpenLoopRampPeriod",
                        "OpenLoopRampTime": 0.1,
                    },
                    "HardwareLimitSwitch": {
                        "ForwardLimitEnable": False,
                        "ForwardRemoteSensorId": 0,
                        "ForwardAutosetPositionEnable": False,
                        "ForwardAutosetPositionValue": 0.0,
                        "ForwardLimitSourceValue": "LimitSwitchPin",
                        "ForwardLimitTypeValue": "NormallyOpen",
                        "ReverseLimitEnable": False,
                        "ReverseRemoteSensorId": 0,
                        "ReverseAutosetPositionEnable": False,
                        "ReverseAutosetPositionValue": 0.0,
                        "ReverseLimitSourceValue": "LimitSwitchPin",
                        "ReverseLimitTypeValue": "NormallyOpen",
                    },
                    "MotorOutput": {
                        "InvertedValue": "CounterClockwise_Positive",
                        "NeutralModeValue": "Brake",
                        "PeakForwardDutyCycle": 1.0,
                        "PeakReverseDutyCycle": -1.0,
                        "DutyCycleNeutralDeadband": 0.0,
                    },
                    "Feedback": {
                        "FeedbackSensorSourceValue": "RotorSensor",
                        "SensorToMechanismRatio": 1.0,
                        "FeedbackRemoteSensorID": 0,
                        "RotorToSensorRatio": 1.0,
                    },
                    "External Feedback": {
                        "ExternalFeedbackSensorSource": "RotorSensor",
                        "SensorToMechanismRatio": 1.0,
                        "FeedbackRemoteSensorID": 0,
                        "RotorToSensorRatio": 1.0,
                    },
                    "Follower": {
                        "Enabled": False,
                        "FollowerID": 0,
                    }
                },
            }
        )

        if hw_type == "TalonFXS":
            # TalonFXS shares the TalonFX config base but drives a Minion via JST
            # commutation and ships with a lower default stator current limit.
            new_hw["config"]["CurrentLimits"]["StatorCurrentLimit"] = 100.0
            new_hw["config"]["Commutation"] = {
                "MotorArrangementValue": "Minion_JST",
            }
    elif hw_type == "CANCoder":
        new_hw.update(
            {
                "Offset": 0.0,
                "SensorDirection": "CounterClockwise_Positive",
                "AbsoluteSensorDiscontinuityPoint": "1.0_tr",
            }
        )
    elif hw_type == "Solenoid":
        new_hw.update(
            {
                "Channel": 0,
                "EnableDualChannel": False,
                "ForwardChannel": 0,
                "ReverseChannel": 0,
                "Reversed": False,
            }
        )
    elif hw_type == "CANdi":
        new_hw.update(
            {
                "config": {
                    "DigitalInputs": {
                        "S1CloseStateValue": "CloseWhenNotHigh",
                        "S1FloatStateValue": "PullHigh",
                        "S2CloseStateValue": "CloseWhenNotHigh",
                        "S2FloatStateValue": "PullHigh",
                    },
                    "PWM1": {
                        "EnableValue": False,
                        "AbsoluteSensorOffset": 0.0,
                        "AbsoluteSensorDiscontinuityPoint": "0.5_tr",
                        "SensorDirectionValue": False,
                    },
                    "PWM2": {
                        "EnableValue": False,
                        "AbsoluteSensorOffset": 0.0,
                        "AbsoluteSensorDiscontinuityPoint": "0.5_tr",
                        "SensorDirectionValue": False,
                    },
                    "Quadrature": {
                        "EnableValue": False,
                        "QuadratureEdgesPerRotation": 4096,
                    },
                },
            }
        )
    elif hw_type == "DigitalInput":
        new_hw.update(
            {
                "DigitalID": 0,
                "Reversed": False,
                "DebounceTime": 0,
            }
        )

    return new_hw
