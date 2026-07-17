"""Hardware-derived generation: per-robot/per-hardware initialization methods,
the CTRE configuration bodies (TalonFX/TalonFXS/CANdi), hardware include flags,
and the per-loop solenoid plumbing.

The configuration bodies are data-driven: each block maps JSON config keys to
C++ assignment lines, emitting only the keys that are present. Pure naming and
literal formatting are delegated to :mod:`gen_naming`.
"""

from . import naming as nm


class HardwareBuilder:
    """Builds hardware setup/configuration code for a mechanism."""

    def hardware_flags(self, hardware):
        """Compute which optional hardware includes a mechanism needs.

        Returns {"has_solenoid", "has_digital_input", "has_follower"} so the
        template can gate the corresponding #include lines.
        """
        has_follower = any(
            hw.get("config", {}).get("Follower", {}).get("Enabled") for hw in hardware
        )
        return {
            "has_solenoid": any(hw.get("type") == "Solenoid" for hw in hardware),
            "has_digital_input": any(hw.get("type") == "DigitalInput" for hw in hardware),
            "has_follower": has_follower,
        }

    def solenoids(self, hardware):
        """Build the per-solenoid bool-target plumbing.

        Solenoids do not use ControlData. Each solenoid gets a bool active-target
        member plus the setter method and the hardware member used to drive it,
        so the header can declare them and Update() can push them every loop.
        """
        solenoids = []
        seen = set()
        for hw in hardware:
            if hw.get("type") != "Solenoid":
                continue
            name = hw.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            pascal = nm.pascal_case(name)
            solenoids.append({
                "name": name,
                "method_name": f"UpdateSolenoid{pascal}ActiveTarget",
                "member_var": f"m_solenoid{pascal}ActiveTarget",
                "hardware_var": nm.member_variable(hw),
            })
        return solenoids

    def hardware_init_methods(self, mech_name, robots, mech_info, closed_loop):
        """Build the per-robot, per-hardware initialization methods.

        Each robot that owns this mechanism gets one Initialize method per piece
        of hardware (motors + CANdi). Returns a flat, order-preserving,
        deduplicated list of dicts ``{"name": <method name>, "body": [<C++ line>, ...]}``
        so the header can declare them and the source can both call and define
        them from the same source of truth. Solenoids/DigitalInputs need no
        initialization beyond construction and are skipped.
        """
        control_data = mech_info.get("control_data", {})

        methods = []
        seen = set()
        for robot_data in robots.values():
            if mech_name not in robot_data.get("mechanisms", {}):
                continue
            robot_name = f"{robot_data.get('name', '')}{robot_data.get('team_number', '')}"
            for hw in robot_data["mechanisms"][mech_name].get("hardware", []):
                hw_type = hw.get("type")
                if hw_type in ("Solenoid", "DigitalInput"):
                    continue
                name = f"Initialize{hw_type}{hw['name']}{robot_name}"
                if name in seen:
                    continue
                seen.add(name)

                if hw_type in nm.MOTOR_TYPES:
                    body = self._build_motor_init_body(
                        hw, closed_loop.get(hw.get("name")), control_data
                    )
                elif hw_type == "CANdi":
                    body = self._build_candi_init_body(hw)
                else:
                    body = self._build_generic_apply_body(hw)

                methods.append({"name": name, "body": body})
        return methods

    def _apply_block_lines(self, member, config_var):
        """The standard CTRE configurator apply-with-retry + error log boilerplate."""
        return [
            "",
            "\tctre::phoenix::StatusCode status = ctre::phoenix::StatusCode::StatusCodeNotInitialized;",
            "\tfor (int i = 0; i < 5; ++i)",
            "\t{",
            f"\t\tstatus = {member}->GetConfigurator().Apply({config_var}, wpi::units::time::second_t(0.25));",
            "\t\tif (status.IsOK())",
            "\t\t\tbreak;",
            "\t}",
            "\tif (!status.IsOK())",
            f"\t\tLogger::GetLogger()->LogData(LOGGER_LEVEL::ERROR, \"{member}\", \"{member} Status\", status.GetName());",
        ]

    def _build_motor_init_body(self, hw, closed_loop_cd_name, control_data):
        """Emit the TalonFX/TalonFXS configuration body from the JSON config block."""
        cfg = hw.get("config", {})
        hw_type = hw.get("type")
        is_fxs = hw_type == "TalonFXS"
        member = nm.member_variable(hw)
        configs_type = "TalonFXSConfiguration" if is_fxs else "TalonFXConfiguration"

        lines = []

        def add(text="", indent=1):
            lines.append(("\t" * indent + text) if text else "")

        amp = lambda v: f"wpi::units::current::ampere_t({nm.cpp_num(v)})"
        sec = lambda v: f"wpi::units::time::second_t({nm.cpp_num(v)})"
        volt = lambda v: f"wpi::units::voltage::volt_t({nm.cpp_num(v)})"
        turn = lambda v: f"wpi::units::angle::turn_t({nm.cpp_num(v)})"
        boolean = lambda v: nm.cpp_bool(v)
        raw = lambda v: nm.cpp_num(v)

        def emit(block, mapping):
            for json_key, cpp_path, fmt in mapping:
                if block is not None and json_key in block:
                    add(f"configs.{cpp_path} = {fmt(block[json_key])};")

        add(f"{configs_type} configs{{}};")

        # --- Current limits ---
        cl = cfg.get("CurrentLimits")
        emit(cl, [
            ("StatorCurrentLimit", "CurrentLimits.StatorCurrentLimit", amp),
            ("StatorCurrentLimitEnable", "CurrentLimits.StatorCurrentLimitEnable", boolean),
            ("SupplyCurrentLimit", "CurrentLimits.SupplyCurrentLimit", amp),
            ("SupplyCurrentLimitEnable", "CurrentLimits.SupplyCurrentLimitEnable", boolean),
            ("SupplyCurrentLowerLimit", "CurrentLimits.SupplyCurrentLowerLimit", amp),
            ("SupplyCurrentLowerTime", "CurrentLimits.SupplyCurrentLowerTime", sec),
        ])

        # --- Voltage ---
        volt_cfg = cfg.get("Voltage")
        if volt_cfg:
            add()
        emit(volt_cfg, [
            ("PeakForwardVoltage", "Voltage.PeakForwardVoltage", volt),
            ("PeakReverseVoltage", "Voltage.PeakReverseVoltage", volt),
        ])

        # --- Ramping (selectable closed/open loop ramp period type) ---
        ramp = cfg.get("Ramping")
        if ramp:
            if "ClosedLoopRampType" in ramp and "ClosedLoopRampTime" in ramp:
                add(f"configs.ClosedLoopRamps.{ramp['ClosedLoopRampType']} = {sec(ramp['ClosedLoopRampTime'])};")
            if "OpenLoopRampType" in ramp and "OpenLoopRampTime" in ramp:
                add(f"configs.OpenLoopRamps.{ramp['OpenLoopRampType']} = {sec(ramp['OpenLoopRampTime'])};")

        # --- Hardware limit switches ---
        hls = cfg.get("HardwareLimitSwitch")
        if hls:
            add()
            emit(hls, [
                ("ForwardLimitEnable", "HardwareLimitSwitch.ForwardLimitEnable", boolean),
                ("ForwardRemoteSensorId", "HardwareLimitSwitch.ForwardLimitRemoteSensorID", raw),
                ("ForwardAutosetPositionEnable", "HardwareLimitSwitch.ForwardLimitAutosetPositionEnable", boolean),
                ("ForwardAutosetPositionValue", "HardwareLimitSwitch.ForwardLimitAutosetPositionValue", turn),
                ("ForwardLimitSourceValue", "HardwareLimitSwitch.ForwardLimitSource", nm.sig_enum("ForwardLimitSourceValue")),
                ("ForwardLimitTypeValue", "HardwareLimitSwitch.ForwardLimitType", nm.sig_enum("ForwardLimitTypeValue")),
            ])
            add()
            emit(hls, [
                ("ReverseLimitEnable", "HardwareLimitSwitch.ReverseLimitEnable", boolean),
                ("ReverseRemoteSensorId", "HardwareLimitSwitch.ReverseLimitRemoteSensorID", raw),
                ("ReverseAutosetPositionEnable", "HardwareLimitSwitch.ReverseLimitAutosetPositionEnable", boolean),
                ("ReverseAutosetPositionValue", "HardwareLimitSwitch.ReverseLimitAutosetPositionValue", turn),
                ("ReverseLimitSourceValue", "HardwareLimitSwitch.ReverseLimitSource", nm.sig_enum("ReverseLimitSourceValue")),
                ("ReverseLimitTypeValue", "HardwareLimitSwitch.ReverseLimitType", nm.sig_enum("ReverseLimitTypeValue")),
            ])

        # --- Motor output ---
        mo = cfg.get("MotorOutput")
        if mo:
            add()
            emit(mo, [
                ("InvertedValue", "MotorOutput.Inverted", nm.sig_enum("InvertedValue")),
                ("NeutralModeValue", "MotorOutput.NeutralMode", nm.sig_enum("NeutralModeValue")),
                ("PeakForwardDutyCycle", "MotorOutput.PeakForwardDutyCycle", raw),
                ("PeakReverseDutyCycle", "MotorOutput.PeakReverseDutyCycle", raw),
                ("DutyCycleNeutralDeadband", "MotorOutput.DutyCycleNeutralDeadband", raw),
            ])

        # --- Motion Magic (only when the closed-loop request is motion-magic based) ---
        closed_cd = control_data.get(closed_loop_cd_name) if closed_loop_cd_name else None
        if closed_cd and "MotionMagic" in (closed_cd.get("ControlRequest") or ""):
            cd_member = nm.member_variable({"name": closed_loop_cd_name, "type": "ControlData"})
            add()
            add(f"configs.MotionMagic.MotionMagicCruiseVelocity = wpi::units::angular_velocity::turns_per_second_t({cd_member}->GetCruiseVelocity());")
            add(f"configs.MotionMagic.MotionMagicAcceleration = wpi::units::angular_acceleration::turns_per_second_squared_t({cd_member}->GetMaxAcceleration());")

        # --- Commutation (TalonFXS only) ---
        if is_fxs:
            comm = cfg.get("Commutation")
            if comm:
                add()
                emit(comm, [
                    ("MotorArrangementValue", "Commutation.MotorArrangement", nm.sig_enum("MotorArrangementValue")),
                ])

        # --- Feedback: TalonFX uses internal Feedback, TalonFXS uses ExternalFeedback.
        #     FeedbackRemoteSensorID and RotorToSensorRatio only apply when the
        #     sensor source is a remote sensor (i.e. not the rotor). ---
        if is_fxs:
            ext = cfg.get("External Feedback")
            if ext and ext.get("Enabled", True):
                source = ext.get("ExternalFeedbackSensorSource")
                add()
                emit(ext, [
                    ("ExternalFeedbackSensorSource", "ExternalFeedback.ExternalFeedbackSensorSource", nm.sig_enum("FeedbackSensorSourceValue")),
                    ("SensorToMechanismRatio", "ExternalFeedback.SensorToMechanismRatio", raw),
                ])
                if source != "RotorSensor":
                    emit(ext, [
                        ("FeedbackRemoteSensorID", "ExternalFeedback.FeedbackRemoteSensorID", raw),
                        ("RotorToSensorRatio", "ExternalFeedback.RotorToSensorRatio", raw),
                    ])
        else:
            fb = cfg.get("Feedback")
            if fb and fb.get("Enabled", True):
                source = fb.get("FeedbackSensorSourceValue")
                add()
                emit(fb, [
                    ("FeedbackSensorSourceValue", "Feedback.FeedbackSensorSource", nm.sig_enum("FeedbackSensorSourceValue")),
                    ("SensorToMechanismRatio", "Feedback.SensorToMechanismRatio", raw),
                ])
                if source != "RotorSensor":
                    emit(fb, [
                        ("FeedbackRemoteSensorID", "Feedback.FeedbackRemoteSensorID", raw),
                        ("RotorToSensorRatio", "Feedback.RotorToSensorRatio", raw),
                    ])

        # --- Slot0 gains, pulled from the closed-loop control data at runtime ---
        if closed_cd is not None:
            cd_member = nm.member_variable({"name": closed_loop_cd_name, "type": "ControlData"})
            add()
            add(f"configs.Slot0.kI = {cd_member}->GetI();")
            add(f"configs.Slot0.kD = {cd_member}->GetD();")
            add(f"configs.Slot0.kG = {cd_member}->GetF();")
            add(f"configs.Slot0.kS = {cd_member}->GetS();")
            add(f"configs.Slot0.kV = {cd_member}->GetV();")
            add(f"configs.Slot0.kP = {cd_member}->GetP();")
            add(f"configs.Slot0.kA = {cd_member}->GetA();")
            if "GravityTypeValue" in closed_cd:
                add(f"configs.Slot0.GravityType = ctre::phoenix6::signals::GravityTypeValue::{closed_cd['GravityTypeValue']};")
            if "StaticFeedforwardSignValue" in closed_cd:
                add(f"configs.Slot0.StaticFeedforwardSign = ctre::phoenix6::signals::StaticFeedforwardSignValue::{closed_cd['StaticFeedforwardSignValue']};")

        lines.extend(self._apply_block_lines(member, "configs"))
        return lines

    def _build_candi_init_body(self, hw):
        """Emit the CANdi configuration body from the JSON config block."""
        cfg = hw.get("config", {})
        member = nm.member_variable(hw)

        lines = []

        def add(text="", indent=1):
            lines.append(("\t" * indent + text) if text else "")

        def emit(block, mapping):
            for json_key, cpp_path, fmt in mapping:
                if block is not None and json_key in block:
                    add(f"CANdiConfig.{cpp_path} = {fmt(block[json_key])};")

        add("CANdiConfiguration CANdiConfig{};")

        di = cfg.get("DigitalInputs")
        if di:
            add()
            emit(di, [
                ("S1CloseStateValue", "DigitalInputs.S1CloseState", nm.sig_enum("S1CloseStateValue")),
                ("S1FloatStateValue", "DigitalInputs.S1FloatState", nm.sig_enum("S1FloatStateValue")),
                ("S2CloseStateValue", "DigitalInputs.S2CloseState", nm.sig_enum("S2CloseStateValue")),
                ("S2FloatStateValue", "DigitalInputs.S2FloatState", nm.sig_enum("S2FloatStateValue")),
            ])

        lines.extend(self._apply_block_lines(member, "CANdiConfig"))
        return lines

    def _build_generic_apply_body(self, hw):
        """Fallback init body for hardware types without a dedicated config builder."""
        return [f"\t// TODO: configuration for {hw.get('type')} {hw.get('name')} not yet supported"]
