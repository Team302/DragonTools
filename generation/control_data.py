"""Control-data derived generation: control requests, active targets, update
methods, closed-loop slot mapping, and the per-loop motor Update() statements.

Everything here is computed from a mechanism's control data and the motor targets
that reference it. Pure naming/formatting is delegated to :mod:`gen_naming`.
"""

from . import naming as nm


class ControlDataBuilder:
    """Builds the control-request/target plumbing for a mechanism."""

    def hardware_control_requests(self, mech_info):
        """One entry per unique (motor, control-data) pair referenced by states."""
        hardware_types = {
            name: hw_type
            for (name, hw_type) in mech_info.get("hardware", {})
            if hw_type in nm.MOTOR_TYPES
        }
        requests = []
        seen = set()
        for state_name in mech_info.get("states", []):
            state = mech_info["state_details"].get(state_name, {})
            for motor_target in state.get("motor_targets", []):
                hw_name = motor_target.get("HardwareName") or motor_target.get("hardware_name")
                control_data_name = motor_target.get("ControlData")
                if not hw_name or not control_data_name:
                    continue
                key = (hw_name, control_data_name)
                if key in seen:
                    continue
                seen.add(key)
                control_data = mech_info["control_data"].get(control_data_name, {})
                requests.append({
                    "hardware_name": hw_name,
                    "control_data_name": control_data_name,
                    "ControlRequest": control_data.get("ControlRequest", "ControlRequest"),
                    "Unit": control_data.get("Unit", "double"),
                    "hardware_type": hardware_types.get(hw_name, "TalonFX"),
                })
        return requests

    def hardware_active_targets(self, mech_info, control_requests):
        """Map each motor to the control data it activates first (its default target)."""
        active = {}
        for state_name in mech_info.get("states", []):
            state = mech_info["state_details"].get(state_name, {})
            for motor_target in state.get("motor_targets", []):
                hw_name = motor_target.get("HardwareName") or motor_target.get("hardware_name")
                control_data_name = motor_target.get("ControlData")
                if not hw_name or not control_data_name:
                    continue
                if hw_name not in active:
                    active[hw_name] = control_data_name

        for hw_name, _hw_type in mech_info.get("hardware", {}).keys():
            if hw_name not in active:
                first_request = next(
                    (req for req in control_requests if req["hardware_name"] == hw_name),
                    None,
                )
                if first_request:
                    active[hw_name] = first_request["control_data_name"]
                else:
                    active[hw_name] = ""

        return active

    def update_methods(self, control_requests):
        """Build the UpdateTarget<Motor><ControlData> setter descriptors."""
        methods = []
        seen = set()
        for req in control_requests:
            hw_name = req["hardware_name"]
            cd_name = req["control_data_name"]
            key = (hw_name, cd_name)
            if key in seen:
                continue
            seen.add(key)

            target_name = nm.member_variable({"name": hw_name + cd_name, "type": "ControlData"})
            active_target_name = nm.member_variable({"name": hw_name, "type": "ControlData"}) + "ActiveTarget"
            param_type = nm.get_unit(req["Unit"])
            param_name = self._param_name(req["ControlRequest"])
            prop_name, use_slot = self._update_property(req["ControlRequest"])
            is_talon_srx = req.get("hardware_type") == "TalonSRX"
            target_expr = (
                f"&{target_name}"
                if is_talon_srx
                else f"&{target_name}.WithSlot(0)" if use_slot else f"&{target_name}"
            )

            methods.append({
                "name": f"UpdateTarget{nm.pascal_case(hw_name)}{nm.pascal_case(cd_name)}",
                "param_type": param_type,
                "param_name": param_name,
                "target_name": target_name,
                "prop_name": prop_name,
                "target_expr": target_expr,
                "active_target_name": active_target_name,
                "is_talon_srx": is_talon_srx,
                "assignment_expr": f"{param_name}.value()" if is_talon_srx and req["Unit"] != "double" else param_name,
            })
        return methods

    def motor_closed_loop_data(self, mech_info):
        """Map each motor name to its first closed-loop control data name.

        Open-loop requests (DutyCycleOut/VoltageOut) need no slot, so motors that
        only ever run open-loop are absent from the result and get no Slot0.
        """
        result = {}
        for state_name in mech_info.get("states", []):
            state = mech_info["state_details"].get(state_name, {})
            for mt in state.get("motor_targets", []):
                hw_name = mt.get("HardwareName") or mt.get("hardware_name")
                cd_name = mt.get("ControlData")
                if not hw_name or not cd_name or hw_name in result:
                    continue
                cd = mech_info["control_data"].get(cd_name, {})
                if nm.is_closed_loop(cd.get("ControlRequest")):
                    result[hw_name] = cd_name
        return result

    def motor_updates(self, hardware, hardware_active_targets, control_requests):
        """Build the per-loop Update() statements that push motor active targets.

        Motors get "<member>->SetControl(*<activeTarget>);". Only motors that
        have an active target are included; sensors and solenoids are handled
        elsewhere.
        """
        updates = []
        for hw in hardware:
            hw_name = hw.get("name", "")
            hw_type = hw.get("type", "")
            if hw_type not in nm.MOTOR_TYPES:
                continue
            if not hardware_active_targets.get(hw_name):
                continue
            hardware_var = nm.member_variable(hw)
            active_target_var = nm.member_variable({"name": hw_name, "type": "ControlData"}) + "ActiveTarget"
            update = {"hardware_var": hardware_var, "active_target_var": active_target_var}
            if hw_type == "TalonSRX":
                cd_name = hardware_active_targets.get(hw_name, "")
                request = next((req for req in control_requests
                                if req["hardware_name"] == hw_name and req["control_data_name"] == cd_name), None)
                update["is_talon_srx"] = True
                update["control_mode"] = nm.TALON_SRX_CONTROL_MODES.get(
                    request["ControlRequest"] if request else "DutyCycleOut"
                )
                if update["control_mode"] is None:
                    raise ValueError(
                        f"Control request {request['ControlRequest']} is not supported by TalonSRX {hw_name}"
                    )
            else:
                update["is_talon_srx"] = False
            updates.append(update)
        return updates

    def _param_name(self, control_request):
        if "Position" in control_request:
            return "position"
        if "DutyCycle" in control_request or control_request.endswith("Out"):
            return "percentOut"
        return "value"

    def _update_property(self, control_request):
        prop_name = nm.request_value_property(control_request)
        use_slot = nm.is_closed_loop(control_request)
        return prop_name, use_slot
