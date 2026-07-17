"""Qt-free data layer for the Dragon Code Generator project.

`ProjectModel` owns the project dictionary and all of the mutation/query logic
that does not depend on the GUI. The GUI window holds a `ProjectModel`, calls
these methods to mutate state, and then handles its own tree/editor rendering.
"""

import os
import json
import copy

from .constants import DEFAULT_PROJECT, APP_SETTINGS_FILE
from . import hardware_defaults as hwd


class ProjectModel:
    def __init__(self):
        self.project_data = copy.deepcopy(DEFAULT_PROJECT)
        self.app_settings = {"last_project_path": ""}
        self.current_project_path = None

    # --- SETTINGS / FILE I/O ---
    def load_app_settings(self):
        if os.path.exists(APP_SETTINGS_FILE):
            try:
                with open(APP_SETTINGS_FILE, "r") as f:
                    self.app_settings = json.load(f)
            except Exception:
                pass

    def update_app_settings(self, path):
        self.app_settings["last_project_path"] = path
        try:
            with open(APP_SETTINGS_FILE, "w") as f:
                json.dump(self.app_settings, f, indent=4)
        except Exception as e:
            print(f"Could not save tool settings: {e}")

    def new_project(self):
        self.project_data = copy.deepcopy(DEFAULT_PROJECT)
        self.current_project_path = None

    def load_project(self, path):
        with open(path, "r") as f:
            self.project_data = json.load(f)
        self.current_project_path = path

    def save_project(self, path):
        with open(path, "w") as f:
            json.dump(self.project_data, f, indent=4)
        self.current_project_path = path

    # --- ROBOTS / MECHANISMS ---
    def add_robot(self, robot_id, name, team_number):
        """Add a robot. Returns True on success, False if the id already exists."""
        if robot_id in self.project_data["robots"]:
            return False
        self.project_data["robots"][robot_id] = {
            "name": name,
            "team_number": team_number,
            "mechanisms": {},
        }
        return True

    def add_mechanism(self, robot_id, mech_name):
        self.project_data["robots"][robot_id]["mechanisms"][mech_name] = {
            "hardware": [],
            "control_data": [],
            "states": [],
        }

    def delete_node(self, data):
        """Delete the tree node described by `data` (the dict stored on each tree item)."""
        r = data.get("robot")
        m = data.get("mech") or data.get("name")
        idx = data.get("index")

        if data["type"] == "robot":
            del self.project_data["robots"][r]
        elif data["type"] == "mechanism":
            del self.project_data["robots"][r]["mechanisms"][m]
        elif data["type"] == "item_hardware":
            mech = self.project_data["robots"][r]["mechanisms"][m]
            if 0 <= idx < len(mech.get("hardware", [])):
                hw = mech["hardware"][idx]
                hw_name = hw.get("name")
                hw_type = hw.get("type")

                for st in mech.get("states", []):
                    if isinstance(st, dict):
                        if hw_type in ["TalonFX", "TalonFXS"] and "motor_targets" in st:
                            st["motor_targets"] = [
                                mt for mt in st.get("motor_targets", []) if mt.get("HardwareName") != hw_name
                            ]
                        if hw_type == "Solenoid" and "solenoid_targets" in st:
                            st["solenoid_targets"] = [
                                stt for stt in st.get("solenoid_targets", []) if stt.get("SolenoidName") != hw_name
                            ]

            mech["hardware"].pop(idx)
        elif data["type"] == "item_cd":
            self.project_data["robots"][r]["mechanisms"][m]["control_data"].pop(idx)
        elif data["type"] == "item_state":
            self.project_data["robots"][r]["mechanisms"][m]["states"].pop(idx)

    # --- QUERIES / HELPERS ---
    def control_data_unit(self, mech_data, cd_name):
        """Return the Unit of the named control data block, or "double" if not found."""
        if not cd_name:
            return "double"
        for cd in mech_data.get("control_data", []):
            if cd.get("name") == cd_name:
                return cd.get("Unit", "double")
        return "double"

    def has_hardware_type(self, mech_data, types):
        if not mech_data:
            return False
        return any(
            hw.get("type") in types
            for hw in mech_data.get("hardware", [])
        )

    def find_mech_location(self, mech_data):
        """Return (robot_id, mech_name) for the given mech_data reference, or (None, None)."""
        for robot_id, robot_data in self.project_data["robots"].items():
            for mech_name, md in robot_data.get("mechanisms", {}).items():
                if md is mech_data:
                    return robot_id, mech_name
        return None, None

    def unique_hw_name(self, mech_data, hw_type):
        base = hw_type.lower()
        existing = {hw.get("name") for hw in mech_data.get("hardware", [])}
        i = 1
        candidate = f"{base}_{i}"
        while candidate in existing:
            i += 1
            candidate = f"{base}_{i}"
        return candidate

    def default_list_item(self, key, mech_data=None):
        if key == "motor_targets":
            hw_name = ""
            if mech_data:
                motors = [
                    hw["name"]
                    for hw in mech_data.get("hardware", [])
                    if hw.get("type") in ["TalonFX", "TalonFXS"]
                ]
                if motors:
                    hw_name = motors[0]
            return hwd.default_motor_target(hw_name)
        if key == "solenoid_targets":
            sol_name = ""
            if mech_data:
                solenoids = [
                    hw["name"]
                    for hw in mech_data.get("hardware", [])
                    if hw.get("type") == "Solenoid"
                ]
                if solenoids:
                    sol_name = solenoids[0]
            return hwd.default_solenoid_target(sol_name)
        return ""

    def sync_state_targets(self, state_data, mech_data):
        """Ensure the state has exactly one target per motor/solenoid present on the mechanism.

        Targets are matched to hardware by name, preserving existing values. Targets for
        hardware that no longer exists are dropped, and the order follows the hardware list.
        """
        motors = [
            hw["name"]
            for hw in mech_data.get("hardware", [])
            if hw.get("type") in ["TalonFX", "TalonFXS"]
        ]
        solenoids = [
            hw["name"]
            for hw in mech_data.get("hardware", [])
            if hw.get("type") == "Solenoid"
        ]

        existing_motors = {
            mt.get("HardwareName"): mt for mt in state_data.get("motor_targets", [])
        }
        synced_motors = []
        for name in motors:
            mt = existing_motors.get(name) or {
                "HardwareName": name,
                "Enabled": True,
                "TargetValue": 0.0,
            }
            mt["HardwareName"] = name
            mt.setdefault("Enabled", True)
            mt.setdefault("TargetValue", 0.0)
            mt.setdefault("ControlData", "")
            # Mirror the unit from the selected control data (picks up later edits).
            mt["Unit"] = self.control_data_unit(mech_data, mt.get("ControlData", ""))
            synced_motors.append(mt)
        state_data["motor_targets"] = synced_motors

        existing_sols = {
            st.get("SolenoidName"): st for st in state_data.get("solenoid_targets", [])
        }
        synced_sols = []
        for name in solenoids:
            st = existing_sols.get(name) or {
                "SolenoidName": name,
                "Enabled": False,
                "State": False,
            }
            st["SolenoidName"] = name
            st.setdefault("Enabled", True)
            st.setdefault("State", False)
            synced_sols.append(st)
        state_data["solenoid_targets"] = synced_sols

    # --- ITEM INJECTORS (return the index of the newly added item) ---
    def add_hardware(self, mech_data, hw_type):
        name = self.unique_hw_name(mech_data, hw_type)
        new_hw = hwd.default_hardware(hw_type, name)
        mech_data["hardware"].append(new_hw)

        hw_name = new_hw.get("name")
        hw_type = new_hw.get("type")
        for st in mech_data.get("states", []):
            if isinstance(st, dict):
                if hw_type in ["TalonFX", "TalonFXS"]:
                    if "motor_targets" not in st:
                        st["motor_targets"] = []
                    if not any(mt.get("HardwareName") == hw_name for mt in st["motor_targets"]):
                        st["motor_targets"].append(hwd.default_motor_target(hw_name))

                if hw_type == "Solenoid":
                    if "solenoid_targets" not in st:
                        st["solenoid_targets"] = []
                    if not any(stt.get("SolenoidName") == hw_name for stt in st["solenoid_targets"]):
                        st["solenoid_targets"].append(hwd.default_solenoid_target(hw_name))

        return len(mech_data["hardware"]) - 1

    def add_control_data(self, mech_data):
        mech_data["control_data"].append(hwd.default_control_data())
        return len(mech_data["control_data"]) - 1

    def add_state(self, mech_data):
        motor_targets = [
            hwd.default_motor_target(hw["name"])
            for hw in mech_data.get("hardware", [])
            if hw.get("type") in ["TalonFX", "TalonFXS"]
        ]
        solenoid_targets = [
            hwd.default_solenoid_target(hw["name"])
            for hw in mech_data.get("hardware", [])
            if hw.get("type") == "Solenoid"
        ]

        mech_data["states"].append(
            {
                "name": "Name",
                "motor_targets": motor_targets,
                "solenoid_targets": solenoid_targets,
            }
        )
        return len(mech_data["states"]) - 1
