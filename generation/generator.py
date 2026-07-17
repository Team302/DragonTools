"""Top-level code-generation orchestration for the Dragon Code Generator.

This class wires the Jinja2 templates to the data computed by the focused
builder classes:
  * :class:`gen_hardware.HardwareBuilder`        - hardware setup/config + flags
  * :class:`gen_control_data.ControlDataBuilder` - control requests/targets/updates
  * :class:`gen_states.StateBuilder`             - command unit includes + logging
Pure naming/formatting helpers live in :mod:`gen_naming` and are registered here
as Jinja2 filters.
"""

import os
import datetime
from jinja2 import Environment, FileSystemLoader

from . import naming as nm
from .hardware import HardwareBuilder
from .control_data import ControlDataBuilder
from .states import StateBuilder

# Project root (the folder that contains the `generation` package). Used to
# resolve the bundled templates regardless of the current working directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DragonCodeGenerator():
    def __init__(self, version=None, template_dir=None, output_dir="output_code"):
        self.version = version
        if template_dir is None:
            template_dir = os.path.join(_PROJECT_ROOT, "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters["state_enum"] = nm.state_enum
        self.env.filters["state_class"] = nm.state_class
        self.env.filters["member_var"] = nm.member_variable
        self.env.filters["target_method"] = nm.generate_target_method
        self.env.filters["unit"] = nm.get_unit
        self.env.filters["short_unit"] = nm.get_short_unit
        self.env.filters["camel"] = nm.camel_case
        self.env.filters["upper_camel"] = nm.upper_camel_case
        self.env.filters["cpp_type"] = nm.cpp_type
        self.output_dir = output_dir

        # Focused builders that compute the HW / Control Data / State payloads.
        self.hardware = HardwareBuilder()
        self.control_data = ControlDataBuilder()
        self.states = StateBuilder()

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate(self, project_data):
        global_mechanisms = self._collect_mechanisms(project_data)
        current_year = datetime.datetime.now().year

        for mech_name, mech_info in global_mechanisms.items():
            print(f"Generating Mechanism: {mech_name}")

            # C++ sources live under src/main/cpp/mechanisms/<Mech>/ so the
            # generated tree drops straight into a WPILib project.
            mech_dir = os.path.join(
                self.output_dir, "src", "main", "cpp", "mechanisms", mech_name.lower()
            )
            cmd_dir = os.path.join(mech_dir, "commands")
            os.makedirs(mech_dir, exist_ok=True)
            os.makedirs(cmd_dir, exist_ok=True)

            template_data = self._build_template_data(
                mech_name, mech_info, project_data, current_year
            )

            # Render Subsystem Files
            self._render_and_write(
                "Mechanism.h.jinja",
                template_data,
                os.path.join(mech_dir, f"{mech_name}.h"),
            )
            self._render_and_write(
                "Mechanism.cpp.jinja",
                template_data,
                os.path.join(mech_dir, f"{mech_name}.cpp"),
            )

            self._render_and_write(
                "Container.h.jinja",
                template_data,
                os.path.join(mech_dir, f"{mech_name}Container.h"),
            )

            self._render_and_write(
                "Container.cpp.jinja",
                template_data,
                os.path.join(mech_dir, f"{mech_name}Container.cpp"),
            )

            # Render Command Classes for each state
            self._render_commands(mech_name, mech_info, template_data, cmd_dir, current_year)

            # Render the per-team control-data XML into the deploy tree.
            self._render_xml(mech_name, project_data)

    # --- Data assembly -------------------------------------------------------

    def _collect_mechanisms(self, project_data):
        """Gather a unique view of every mechanism across all robots."""
        global_mechanisms = {}
        for robot_id, robot_data in project_data.get("robots", {}).items():
            for mech_name, mech_data in robot_data.get("mechanisms", {}).items():
                if mech_name not in global_mechanisms:
                    global_mechanisms[mech_name] = {
                        "states": [],
                        "state_details": {},
                        "hardware": {},
                        "control_data": {},
                    }

                mech_info = global_mechanisms[mech_name]
                for hw in mech_data.get("hardware", []):
                    # Key by (name, type): a single logical device (e.g. "extender")
                    # can map to multiple hardware objects (TalonFXS + CANdi), so the
                    # name alone is not unique.
                    mech_info["hardware"][(hw["name"], hw["type"])] = hw

                for cd in mech_data.get("control_data", []):
                    mech_info["control_data"][cd["name"]] = cd

                for state in mech_data.get("states", []):
                    if isinstance(state, dict):
                        state_name = state.get("name", "")
                        if state_name and state_name not in mech_info["state_details"]:
                            mech_info["states"].append(state_name)
                            mech_info["state_details"][state_name] = state
                    else:
                        if state not in mech_info["state_details"]:
                            mech_info["states"].append(state)
                            mech_info["state_details"][state] = {
                                "name": state,
                                "motor_targets": [],
                                "solenoid_targets": [],
                            }
        return global_mechanisms

    def _build_template_data(self, mech_name, mech_info, project_data, current_year):
        """Compute the full payload shared by the mechanism .h/.cpp templates."""
        control_requests = self.control_data.hardware_control_requests(mech_info)
        hardware_list = list(mech_info["hardware"].values())
        active_targets = self.control_data.hardware_active_targets(mech_info, control_requests)
        closed_loop = self.control_data.motor_closed_loop_data(mech_info)
        logging_data = self.states.logging_data(
            mech_name, mech_info, active_targets, closed_loop
        )

        return {
            "year": current_year,
            "version": self.version,
            "mechanism_name": mech_name,
            "robots": project_data.get("robots", {}),
            "states": mech_info["states"] if mech_info["states"] else ["STATE_OFF"],
            "state_details": mech_info["state_details"],
            "hardware": hardware_list,
            "control_data": list(mech_info["control_data"].values()),
            "control_requests": control_requests,
            "hardware_active_targets": active_targets,
            "update_methods": self.control_data.update_methods(control_requests),
            "motor_updates": self.control_data.motor_updates(hardware_list, active_targets),
            "solenoids": self.hardware.solenoids(hardware_list),
            "logging_motors": logging_data["logging_motors"],
            "cached_values": logging_data["cached_values"],
            "hardware_init_methods": self.hardware.hardware_init_methods(
                mech_name, project_data.get("robots", {}), mech_info, closed_loop
            ),
            **self.hardware.hardware_flags(hardware_list),
        }

    def _render_commands(self, mech_name, mech_info, template_data, cmd_dir, current_year):
        """Render the per-state command .h/.cpp files."""
        for state in template_data["states"]:
            # Cleans "Empty Hopper" into "IntakeEmptyHopperCommand"
            cmd_name = f"{mech_name}{nm.state_class(state)}Command"
            state_data = template_data["state_details"].get(
                state,
                {
                    "name": state,
                    "motor_targets": [],
                    "solenoid_targets": [],
                },
            )

            cmd_data = {
                "year": current_year,
                "version": self.version,
                "mechanism_name": mech_name,
                "command_name": cmd_name,
                "state_enum": nm.state_enum(state),
                "state_data": state_data,
                "unit_includes": self.states.unit_includes(state_data),
            }

            self._render_and_write(
                "Command.h.jinja", cmd_data, os.path.join(cmd_dir, f"{cmd_name}.h")
            )
            self._render_and_write(
                "Command.cpp.jinja",
                cmd_data,
                os.path.join(cmd_dir, f"{cmd_name}.cpp"),
            )

    def _render_xml(self, mech_name, project_data):
        """Render the per-team control-data XML into the deploy tree.

        Each robot that owns this mechanism gets its own copy under its team
        number, built from that robot's own control data.
        """
        for robot_data in project_data.get("robots", {}).values():
            if mech_name not in robot_data.get("mechanisms", {}):
                continue
            team = robot_data.get("team_number", "")
            xml_dir = os.path.join(
                self.output_dir, "src", "main", "deploy", str(team), "mechanisms"
            )
            os.makedirs(xml_dir, exist_ok=True)
            self._render_and_write(
                "Mechanism.xml.jinja",
                {
                    "mechanism_name": mech_name,
                    "control_data": robot_data["mechanisms"][mech_name].get(
                        "control_data", []
                    ),
                },
                os.path.join(xml_dir, f"{mech_name}.xml"),
            )

    def _render_and_write(self, template_name, data, out_path):
        """Helper function to load template, render it, and write to disk."""
        template = self.env.get_template(template_name)
        with open(out_path, "w") as f:
            f.write(template.render(data))
