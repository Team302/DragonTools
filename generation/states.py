"""State-derived generation: per-command unit includes and the per-motor logging
plumbing (DataLog() / RefreshCachedData()).

Both are derived from a mechanism's states and the control data their motor
targets reference. Pure naming/formatting is delegated to :mod:`gen_naming`.
"""

from . import naming as nm


class StateBuilder:
    """Builds state/command-derived generation data for a mechanism."""

    def unit_includes(self, state_data):
        """Collect the units library headers a command needs, deduplicated.

        Walks the enabled motor targets and maps each non-"double" unit to its
        units/*.h header, preserving first-seen order and emitting each header
        only once.
        """
        includes = []
        seen = set()
        for target in state_data.get("motor_targets", []):
            if not target.get("Enabled"):
                continue
            header = nm.UNIT_INCLUDES.get(target.get("Unit"))
            if header and header not in seen:
                seen.add(header)
                includes.append(header)
        return includes

    def logging_data(self, mech_name, mech_info, hardware_active_targets, closed_loop):
        """Build the per-motor logging plumbing for DataLog()/RefreshCachedData().

        For each motor we log its commanded target value and its active control
        request name. Closed-loop motors (position/velocity based) additionally
        log a cached sensor reading, refreshed every loop in RefreshCachedData().
        Returns {"logging_motors": [...], "cached_values": [...]}.
        """
        mech_pascal = nm.pascal_case(mech_name)
        control_data = mech_info.get("control_data", {})

        # First (name, type) wins so a logical device maps to its motor object.
        motor_hw = {}
        for (name, hw_type), hw in mech_info.get("hardware", {}).items():
            if hw_type in nm.MOTOR_TYPES and name not in motor_hw:
                motor_hw[name] = hw

        logging_motors = []
        cached_values = []
        for hw_name, active_cd_name in hardware_active_targets.items():
            if hw_name not in motor_hw:
                continue
            # Prefer the motor's closed-loop control data for logging (so position/
            # velocity gets cached and logged); fall back to the active target.
            cd_name = closed_loop.get(hw_name) or active_cd_name
            if not cd_name:
                continue
            hw = motor_hw[hw_name]
            hw_pascal = nm.pascal_case(hw_name)
            cd = control_data.get(cd_name, {})
            control_request = cd.get("ControlRequest", "")
            unit = cd.get("Unit", "double")

            request_member = nm.member_variable(
                {"name": hw_name + cd_name, "type": "ControlData"}
            )
            value_prop = nm.request_value_property(control_request)
            active_target_var = (
                nm.member_variable({"name": hw_name, "type": "ControlData"})
                + "ActiveTarget"
            )

            entry = {
                "hardware_name": hw_name,
                "target_path_member": f"m_logging{hw_pascal}TargetPath",
                "target_path": f"/{mech_pascal}/{hw_pascal}MotorTarget",
                "target_value_expr": f"{request_member}.{value_prop}.value()",
                "control_request_member": f"m_logging{hw_pascal}ControlRequest",
                "control_request_path": f"/{mech_pascal}/{hw_pascal}ControlRequest",
                "active_target_var": active_target_var,
                "closed_loop": nm.is_closed_loop(control_request),
            }

            if entry["closed_loop"]:
                is_velocity = "Velocity" in (control_request or "")
                label = "Velocity" if is_velocity else "Position"
                getter = "GetVelocity" if is_velocity else "GetPosition"
                cached_var = f"m_cached{hw_pascal}{nm.pascal_case(cd_name)}"
                motor_var = nm.member_variable(hw)
                entry["position_path_member"] = f"m_logging{hw_pascal}{label}Path"
                entry["position_path"] = f"/{mech_pascal}/{hw_pascal}{label}"
                entry["cached_value_expr"] = f"{cached_var}.value()"
                cached_values.append({
                    "var": cached_var,
                    "type": nm.get_unit(unit),
                    "getter": f"{motor_var}->{getter}().GetValue()",
                })

            logging_motors.append(entry)

        return {"logging_motors": logging_motors, "cached_values": cached_values}
