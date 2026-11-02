import json
import tempfile
import unittest
from pathlib import Path

from generation import DragonCodeGenerator
from gui.model import ProjectModel


class SparkMaxGenerationTests(unittest.TestCase):
    def setUp(self):
        self.model = ProjectModel()
        self.model.add_robot("TEST_302", "TestBot", 302)
        self.model.add_mechanism("TEST_302", "Intake")
        self.mechanism = self.model.project_data["robots"]["TEST_302"]["mechanisms"]["Intake"]
        self.temp = tempfile.TemporaryDirectory()
        self.generator = DragonCodeGenerator(output_dir=self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def generated_mechanism(self):
        return Path(self.temp.name) / "src" / "main" / "cpp" / "mechanisms" / "intake"

    def test_spark_max_defaults_create_motor_target(self):
        self.model.add_hardware(self.mechanism, "SparkMax")
        self.model.add_state(self.mechanism)
        hardware = self.mechanism["hardware"][0]
        state = self.mechanism["states"][0]

        self.assertEqual(hardware["canbus"], 0)
        self.assertIsInstance(hardware["canbus"], int)
        self.assertEqual(hardware["config"]["MotorType"], "kBrushless")
        self.assertEqual(hardware["config"]["IdleMode"], "kBrake")
        self.assertEqual(state["motor_targets"][0]["HardwareName"], hardware["name"])

    def test_generation_uses_revlib_constructor_config_and_duty_cycle(self):
        self.model.add_hardware(self.mechanism, "SparkMax")
        self.mechanism["hardware"][0]["canbus"] = 5
        self.model.add_state(self.mechanism)
        self.generator.generate(self.model.project_data)

        header = (self.generated_mechanism() / "Intake.h").read_text()
        source = (self.generated_mechanism() / "Intake.cpp").read_text()
        self.assertIn('#include "rev/SparkMax.h"', header)
        self.assertIn("rev::spark::SparkMax* m_sparkmax1Motor", header)
        self.assertIn("rev::spark::SparkMax(5, 0", source)
        self.assertNotIn("canivore", source)
        self.assertIn("rev::spark::SparkLowLevel::MotorType::kBrushless", source)
        self.assertIn("configs.SetIdleMode(rev::spark::SparkBaseConfig::IdleMode::kBrake)", source)
        self.assertIn("GetClosedLoopController().SetSetpoint(*m_sparkmax1ActiveTarget", source)
        self.assertIn("ControlType::kDutyCycle", source)
        self.assertNotIn("phoenix::motorcontrol", source)

    def test_closed_loop_request_maps_to_revlib_position_api(self):
        self.model.add_hardware(self.mechanism, "SparkMax")
        self.model.add_control_data(self.mechanism)
        control_data = self.mechanism["control_data"][-1]
        control_data.update({"name": "Position", "ControlRequest": "PositionVoltage", "Unit": "turn"})
        self.model.add_state(self.mechanism)
        target = self.mechanism["states"][0]["motor_targets"][0]
        target["ControlData"] = "Position"
        target["Unit"] = "turn"
        self.generator.generate(self.model.project_data)

        header = (self.generated_mechanism() / "Intake.h").read_text()
        source = (self.generated_mechanism() / "Intake.cpp").read_text()
        self.assertIn("UpdateTargetSparkmax1Position(wpi::units::angle::turn_t position)", header)
        self.assertIn("ControlType::kPosition", source)
        self.assertIn("GetEncoder().GetPosition().GetValue()", source)

    def test_spark_max_follower_config_and_target_exclusion(self):
        self.model.add_hardware(self.mechanism, "SparkMax")
        self.mechanism["hardware"][0]["name"] = "leader"
        self.mechanism["hardware"][0]["id"] = 1
        self.model.add_hardware(self.mechanism, "SparkMax")
        follower = self.mechanism["hardware"][1]
        follower["name"] = "follower"
        follower["id"] = 2
        follower["config"]["Follower"].update(
            {"Enabled": True, "FollowerID": 1, "Invert": True}
        )
        self.model.add_state(self.mechanism)

        targets = self.mechanism["states"][0]["motor_targets"]
        self.assertEqual([target["HardwareName"] for target in targets], ["leader"])
        targets.append({
            "HardwareName": "follower",
            "Enabled": True,
            "TargetValue": 0.5,
            "ControlData": "PercentOut",
            "Unit": "double",
        })

        self.generator.generate(self.model.project_data)
        header = (self.generated_mechanism() / "Intake.h").read_text()
        source = (self.generated_mechanism() / "Intake.cpp").read_text()
        command = (
            self.generated_mechanism() / "commands" / "IntakeNameCommand.cpp"
        ).read_text()

        self.assertIn("configs.Follow(1, true);", source)
        self.assertIn("m_leaderActiveTarget", header)
        self.assertNotIn("m_followerActiveTarget", header)
        self.assertNotIn("UpdateTargetFollower", command)
        self.assertNotIn("m_followerMotor->GetClosedLoopController()", source)

    def test_legacy_talon_srx_project_is_migrated_when_loaded(self):
        legacy = {
            "project_name": "legacy",
            "robots": {
                "TEST_302": {
                    "name": "TestBot",
                    "team_number": 302,
                    "mechanisms": {
                        "Intake": {
                            "hardware": [{
                                "type": "TalonSRX",
                                "name": "roller",
                                "id": 5,
                                "config": {
                                    "Inverted": True,
                                    "NeutralModeValue": "Coast",
                                    "ContinuousCurrentLimit": 30,
                                    "OpenLoopRamp": 0.2,
                                    "ClosedLoopRamp": 0.3,
                                },
                            }],
                            "control_data": [],
                            "states": [],
                        }
                    },
                }
            },
        }
        path = Path(self.temp.name) / "legacy.json"
        path.write_text(json.dumps(legacy))
        self.model.load_project(path)

        migrated = self.model.project_data["robots"]["TEST_302"]["mechanisms"]["Intake"]["hardware"][0]
        self.assertEqual(migrated["type"], "SparkMax")
        self.assertEqual(migrated["canbus"], 0)
        self.assertNotIn("bus", migrated)
        self.assertEqual(migrated["config"]["MotorType"], "kBrushless")
        self.assertTrue(migrated["config"]["Inverted"])
        self.assertEqual(migrated["config"]["IdleMode"], "kCoast")
        self.assertEqual(migrated["config"]["SmartCurrentLimit"], 30)
        self.assertEqual(migrated["config"]["OpenLoopRampRate"], 0.2)


if __name__ == "__main__":
    unittest.main()
