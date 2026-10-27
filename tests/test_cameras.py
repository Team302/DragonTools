import copy
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from generation import DragonCodeGenerator
from generation.cameras import (
    INCH_TO_METER, LIMELIGHT_OPTIONS, POSE_FIELDS, configured_robots,
    default_camera_config, new_camera, validate_camera_config,
)
from gui.camera_creator import CameraCreatorWidget
from gui.camera_preview import rotate_point
from gui.model import ProjectModel
from gui.suite import DragonSuiteWindow


class CameraDataTests(unittest.TestCase):
    def test_defaults_are_independent_and_valid(self):
        first, second = default_camera_config(), default_camera_config()
        first["cameras"].append(new_camera("Limelight", []))
        self.assertEqual(second["cameras"], [])
        validate_camera_config(first)
        self.assertEqual(first["cameras"][0]["camera_type"], "LIMELIGHT4")

    def test_identifiers_names_and_limits(self):
        cameras = []
        for identifier in LIMELIGHT_OPTIONS["identifier"]:
            camera = new_camera("Limelight", cameras)
            self.assertEqual(camera["identifier"], identifier)
            cameras.append(camera)
        self.assertEqual(len({c["name"] for c in cameras}), 4)
        with self.assertRaisesRegex(ValueError, "four"):
            new_camera("Limelight", cameras)
        cameras.append(new_camera("Quest", cameras))
        with self.assertRaisesRegex(ValueError, "one Quest"):
            new_camera("Quest", cameras)
        del cameras[1]
        replacement = new_camera("Limelight", cameras)
        self.assertEqual(replacement["name"], "limelight-2")
        self.assertEqual(replacement["identifier"], "FRONT")

    def test_validation_rejects_invalid_values(self):
        original = default_camera_config()
        original["cameras"].append(new_camera("Limelight", []))
        for field, value in (("x", float("nan")), ("z", float("inf")), ("yaw", "0"), ("x", True)):
            with self.subTest(field=field, value=value):
                config = copy.deepcopy(original)
                config["cameras"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_camera_config(config)
        for value in (0, -1, float("nan"), "30", True):
            with self.subTest(dimension=value):
                config = copy.deepcopy(original)
                config["robot_length_in"] = value
                with self.assertRaises(ValueError):
                    validate_camera_config(config)

    def test_validation_rejects_duplicate_names_identifiers_and_quests(self):
        for kind in ("Limelight", "Quest"):
            config = default_camera_config()
            camera = new_camera(kind, [])
            config["cameras"] = [camera, copy.deepcopy(camera)]
            with self.assertRaisesRegex(ValueError, "Duplicate camera name"):
                validate_camera_config(config)
            config["cameras"][1]["name"] = "other"
            with self.assertRaisesRegex(ValueError, "identifier|one Quest"):
                validate_camera_config(config)

    def test_validation_rejects_unsupported_enums_and_unsafe_names(self):
        config = default_camera_config()
        camera = new_camera("Limelight", [])
        config["cameras"] = [camera]
        for key in LIMELIGHT_OPTIONS:
            broken = copy.deepcopy(config)
            broken["cameras"][0][key] = "NOT_AN_ENUM"
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_camera_config(broken)
        camera["name"] = 'bad"); injected(); //'
        with self.assertRaisesRegex(ValueError, "names must"):
            validate_camera_config(config)
        validate_camera_config(config, structural_only=True)

    def test_wpilib_orientation(self):
        for angles, point, expected in (
            ((0, 0, 0), (1, 0, 0), (1, 0, 0)),
            ((0, 0, 90), (1, 0, 0), (0, 1, 0)),
            ((0, 90, 0), (1, 0, 0), (0, 0, -1)),
            ((90, 0, 0), (0, 0, 1), (0, -1, 0)),
            ((90, 90, 90), (0, 0, 1), (1, 0, 0)),
        ):
            with self.subTest(angles=angles):
                for actual, target in zip(rotate_point(point, *angles), expected):
                    self.assertAlmostEqual(actual, target)


class CameraGenerationTests(unittest.TestCase):
    def setUp(self):
        self.model = ProjectModel()
        self.model.add_robot("COMP_BOT_302", "Comp Bot", 302)
        config = default_camera_config()
        limelight = new_camera("Limelight", [])
        limelight.update(x=-10.7354, y=-10.3104, z=9.39, pitch=5, yaw=-150, roll=12)
        quest = new_camera("Quest", [])
        quest.update(x=-11.216, y=-10.362, z=16.762, pitch=7, yaw=180)
        config["cameras"] = [limelight, quest]
        self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"] = config
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.generator = DragonCodeGenerator(output_dir=self.temp.name)

    def test_generated_constructor_order_types_and_manager_wiring(self):
        written = self.generator.generate_camera_configs(self.model.project_data)
        self.assertEqual(len(written), 4)
        source = Path(written[1]).read_text()
        self.assertIn("-0.2727_m, // LL Forward (-10.7354 in)", source)
        self.assertIn("0.2619_m, // LL Right (10.3104 in)", source)
        self.assertIn("0.2385_m, // LL Up (9.39 in)", source)
        self.assertIn("-5.0_deg,\n        -150.0_deg,\n        12.0_deg", source)
        self.assertIn("-11.216_in", source)
        self.assertIn("-10.362_in", source)
        self.assertIn("16.762_in", source)
        self.assertIn("7.0_deg,\n        180.0_deg", source)
        self.assertNotIn("wpi::units::", source)
        self.assertIn('std::make_unique<DragonLimelight>(\n        "limelight-1"', source)
        self.assertIn("vision->AddLimelight", source)
        self.assertIn("vision->AddQuest", source)
        manager = Path(written[3]).read_text()
        self.assertIn("case RobotIdentifier::COMP_BOT_302:", manager)
        self.assertIn("new CameraConfig_COMP_BOT_302()", manager)

    def test_pitch_sign_is_flipped_only_for_limelight(self):
        source = Path(self.generator.generate_camera_configs(self.model.project_data)[1]).read_text()
        self.assertIn("-5.0_deg, // LL Pitch", source)
        self.assertIn("7.0_deg, // <I> - Pitch of Quest", source)

    def test_y_offset_is_flipped_only_for_limelight(self):
        source = Path(self.generator.generate_camera_configs(self.model.project_data)[1]).read_text()
        self.assertIn("0.2619_m, // LL Right (10.3104 in)", source)
        self.assertIn("-10.362_in,  // <I> y offset of Quest", source)

    def test_generated_literals_follow_selected_units_without_mutating_project(self):
        config = self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"]
        config["length_unit"] = "in"
        config["angle_unit"] = "rad"
        before = copy.deepcopy(self.model.project_data)
        written = self.generator.generate_camera_configs(self.model.project_data)
        source = Path(written[1]).read_text()
        self.assertIn("-0.2727_m, // LL Forward (-10.7354 in)", source)
        self.assertIn("0.2619_m, // LL Right (10.3104 in)", source)
        self.assertIn("0.2385_m, // LL Up (9.39 in)", source)
        self.assertIn("-11.216_in", source)
        self.assertIn("-2.618_rad", source)
        self.assertIn("3.1416_rad", source)
        self.assertNotIn("_deg,", source)
        self.assertNotIn("wpi::units::", source)
        self.assertEqual(self.model.project_data, before)

    def test_generated_literals_use_each_fields_unit(self):
        limelight = self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"]["cameras"][0]
        limelight["units"] = {"x": "m", "z": "in", "yaw": "rad"}
        source = Path(self.generator.generate_camera_configs(self.model.project_data)[1]).read_text()
        self.assertIn("-0.2727_m, // LL Forward (-10.7354 in)", source)
        self.assertIn("0.2619_m, // LL Right (10.3104 in)", source)
        self.assertIn("0.2385_m, // LL Up (9.39 in)", source)
        self.assertIn("-5.0_deg, // LL Pitch", source)
        self.assertIn("-2.618_rad, // LL Yaw", source)
        self.assertIn("12.0_deg, // LL Roll", source)
        self.assertIn("-11.216_in", source)

    def test_invalid_field_units_are_rejected(self):
        config = self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"]
        for units in ({"x": "deg"}, {"yaw": "m"}, {"bogus": "in"}, "m"):
            with self.subTest(units=units):
                config["cameras"][0]["units"] = units
                with self.assertRaises(ValueError):
                    validate_camera_config(config)

    def test_full_generation_includes_cameras_and_preserves_empty_mechanism_behavior(self):
        self.generator.generate(self.model.project_data)
        root = Path(self.temp.name) / "src" / "main" / "cpp"
        self.assertTrue((root / "RobotIdentifier.h").is_file())
        self.assertTrue((root / "RobotContainer.cpp").is_file())
        self.assertTrue((root / "vision" / "definitions" / "CameraConfig_COMP_BOT_302.cpp").is_file())

    def test_cameras_do_not_change_existing_mechanism_output(self):
        self.model.add_mechanism("COMP_BOT_302", "Intake")
        mechanism = self.model.project_data["robots"]["COMP_BOT_302"]["mechanisms"]["Intake"]
        self.model.add_hardware(mechanism, "TalonFX")
        self.model.add_state(mechanism)
        without_cameras = copy.deepcopy(self.model.project_data)
        del without_cameras["robots"]["COMP_BOT_302"]["camera_config"]
        with tempfile.TemporaryDirectory() as folder:
            DragonCodeGenerator(output_dir=folder).generate(without_cameras)
            self.generator.generate(self.model.project_data)
            for path in Path(folder).rglob("*"):
                if path.is_file():
                    relative = path.relative_to(folder)
                    with self.subTest(file=relative):
                        self.assertEqual(path.read_bytes(), (Path(self.temp.name) / relative).read_bytes())

    def test_multiple_robots_including_empty_camera_config(self):
        self.model.add_robot("PRACTICE_303", "Practice", 303)
        self.model.project_data["robots"]["PRACTICE_303"]["camera_config"] = default_camera_config()
        written = self.generator.generate_camera_configs(self.model.project_data)
        self.assertEqual(len(written), 6)
        self.assertIn("case RobotIdentifier::PRACTICE_303:", Path(written[-1]).read_text())

    def test_old_projects_do_not_generate_camera_files_or_mutate_data(self):
        del self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"]
        before = copy.deepcopy(self.model.project_data)
        self.assertEqual(self.generator.generate_camera_configs(self.model.project_data), [])
        self.generator.generate(self.model.project_data)
        self.assertEqual(self.model.project_data, before)
        self.assertFalse((Path(self.temp.name) / "src" / "main" / "cpp" / "vision").exists())

    def test_invalid_data_fails_before_any_output(self):
        self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"]["cameras"][0]["pipeline"] = "INVALID"
        with self.assertRaisesRegex(ValueError, "pipeline"):
            self.generator.generate(self.model.project_data)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_invalid_robot_identifier_and_ambiguous_team_numbers(self):
        robots = self.model.project_data["robots"]
        robots["BAD-ID"] = robots.pop("COMP_BOT_302")
        with self.assertRaisesRegex(ValueError, "C\\+\\+ identifier"):
            configured_robots(self.model.project_data)
        robots["COMP_BOT_302"] = robots.pop("BAD-ID")
        robots["OTHER_302"] = copy.deepcopy(robots["COMP_BOT_302"])
        with self.assertRaisesRegex(ValueError, "share team number"):
            configured_robots(self.model.project_data)
        del robots["OTHER_302"]["camera_config"]
        with self.assertRaisesRegex(ValueError, "share team number"):
            configured_robots(self.model.project_data)
        del robots["OTHER_302"]
        robots["comp_bot_302"] = {"team_number": 303}
        with self.assertRaisesRegex(ValueError, "same RobotIdentifier"):
            configured_robots(self.model.project_data)

    def test_chassis_robot_identifier_is_not_duplicated(self):
        self.model.add_robot("CHASSIS_BOT_9999", "Chassis Bot", 9999)
        self.model.project_data["robots"]["CHASSIS_BOT_9999"]["camera_config"] = default_camera_config()
        self.generator.generate(self.model.project_data)
        cpp = Path(self.temp.name) / "src" / "main" / "cpp"
        self.assertEqual((cpp / "RobotIdentifier.h").read_text().count("CHASSIS_BOT_9999 ="), 1)
        manager = (cpp / "vision" / "definitions" / "CameraConfigMgr.cpp").read_text()
        self.assertIn("case RobotIdentifier::CHASSIS_BOT_9999:", manager)


class CameraGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.model = ProjectModel()
        self.widget = CameraCreatorWidget(self.model)
        self.widget.resize(1100, 800)
        self.widget.show()
        self.addCleanup(self.widget.close)
        self.model.add_robot("COMP_BOT_302", "Comp Bot", 302)
        self.widget.refresh_robots()
        self.app.processEvents()

    def test_opening_tab_does_not_modify_legacy_project(self):
        self.assertNotIn("camera_config", self.model.project_data["robots"]["COMP_BOT_302"])

    def test_add_edit_remove_and_quest_limit(self):
        QTest.mouseClick(self.widget.add_limelight_button, Qt.MouseButton.LeftButton)
        self.widget.pose_widgets["x"].setValue(-10.7354)
        self.widget.name_edit.setText("limelight-left")
        self.widget.option_widgets["pipeline"].setCurrentText("FUEL_PL")
        QTest.mouseClick(self.widget.add_quest_button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.widget.add_quest_button.isEnabled())
        self.assertTrue(self.widget.option_widgets["pipeline"].isHidden())
        self.widget.remove_camera()
        self.assertTrue(self.widget.add_quest_button.isEnabled())
        self.assertEqual(self.widget.selected_camera()["name"], "limelight-left")
        self.assertEqual(self.widget.selected_camera()["x"], -10.7354)
        self.assertEqual(self.widget.selected_camera()["pipeline"], "FUEL_PL")
        self.widget.remove_camera()
        self.assertFalse(self.widget.camera_box.isEnabled())
        self.assertFalse(self.widget.remove_button.isEnabled())

    def test_display_unit_changes_preserve_canonical_values(self):
        w = self.widget
        w.add_camera("Limelight")
        w.robot_length.setValue(32)
        w.pose_widgets["x"].setValue(-10.7354)
        w.pose_widgets["yaw"].setValue(-150)
        before = copy.deepcopy(w.config["cameras"][0])
        for _ in range(5):
            w.dimension_unit_widgets["robot_length_in"].setCurrentIndex(1)
            w.pose_unit_widgets["x"].setCurrentIndex(1)
            w.pose_unit_widgets["yaw"].setCurrentIndex(1)
            self.assertEqual(w.robot_length.value(), round(32 * INCH_TO_METER, 4))
            self.assertEqual(w.pose_widgets["x"].value(), round(-10.7354 * INCH_TO_METER, 4))
            self.assertEqual(w.pose_widgets["yaw"].value(), round(math.radians(-150), 4))
            # Other fields keep their own units.
            self.assertEqual(w.robot_width.value(), 30)
            self.assertEqual(w.pose_unit_widgets["y"].currentData(), "in")
            self.assertEqual(w.pose_unit_widgets["pitch"].currentData(), "deg")
            w.dimension_unit_widgets["robot_length_in"].setCurrentIndex(0)
            w.pose_unit_widgets["x"].setCurrentIndex(0)
            w.pose_unit_widgets["yaw"].setCurrentIndex(0)
        for field in POSE_FIELDS:
            self.assertEqual(w.config["cameras"][0][field], before[field])
        self.assertEqual(w.config["robot_length_in"], 32)
        w.pose_unit_widgets["x"].setCurrentIndex(1)
        w.pose_unit_widgets["yaw"].setCurrentIndex(1)
        w.dimension_unit_widgets["robot_width_in"].setCurrentIndex(1)
        w.pose_widgets["x"].setValue(0.254)
        w.pose_widgets["yaw"].setValue(math.pi / 2)
        w.robot_width.setValue(0.762)
        self.assertAlmostEqual(w.selected_camera()["x"], 10)
        self.assertAlmostEqual(w.selected_camera()["yaw"], 90, places=3)
        self.assertAlmostEqual(w.config["robot_width_in"], 30)

    def test_units_are_per_camera(self):
        w = self.widget
        w.add_camera("Limelight")
        w.pose_unit_widgets["z"].setCurrentIndex(1)
        w.add_camera("Quest")
        self.assertEqual(w.pose_unit_widgets["z"].currentData(), "in")
        w.camera_list.setCurrentRow(0)
        self.assertEqual(w.pose_unit_widgets["z"].currentData(), "m")

    def test_robot_switch_save_reload_and_removal(self):
        self.widget.add_camera("Limelight")
        self.widget.pose_widgets["x"].setValue(12)
        self.model.add_robot("PRACTICE_303", "Practice", 303)
        self.widget.refresh_robots()
        self.widget.robot_combo.setCurrentIndex(1)
        self.widget.add_camera("Quest")
        self.widget.pose_widgets["z"].setValue(20)
        self.widget.pose_unit_widgets["z"].setCurrentIndex(1)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "project.json")
            self.model.save_project(path)
            self.model.new_project()
            self.widget.refresh_robots()
            self.assertFalse(self.widget.controls.isEnabled())
            self.model.load_project(path)
        self.widget.refresh_robots()
        self.assertEqual(self.widget.selected_camera()["x"], 12)
        self.widget.robot_combo.setCurrentIndex(1)
        self.assertEqual(self.widget.selected_camera()["z"], 20)
        self.assertEqual(self.widget.pose_unit_widgets["z"].currentData(), "m")
        self.model.delete_node({"type": "robot", "robot": "PRACTICE_303"})
        self.widget.refresh_robots()
        self.assertEqual(self.widget.robot_combo.currentData(), "COMP_BOT_302")

    def test_invalid_name_remains_editable_after_refresh(self):
        self.widget.add_camera("Limelight")
        self.widget.name_edit.setText("")
        self.assertFalse(self.widget.generate_button.isEnabled())
        self.widget.refresh_robots()
        self.assertTrue(self.widget.name_edit.isEnabled())
        self.widget.name_edit.setText("limelight-fixed")
        self.assertTrue(self.widget.generate_button.isEnabled())

    def test_malformed_saved_camera_data_reports_error_without_crashing(self):
        for config in (None, {"cameras": []}, {"robot_length_in": "bad"}):
            with self.subTest(config=config):
                self.model.project_data["robots"]["COMP_BOT_302"]["camera_config"] = config
                self.widget.refresh_robots()
                self.assertFalse(self.widget.controls.isEnabled())
                self.assertIn("Invalid saved camera configuration", self.widget.validation_label.text())
                self.widget.preview.grab()

    def test_orbit_zoom_presets_and_3d_rendering(self):
        self.widget.add_camera("Limelight")
        self.widget.pose_widgets["z"].setValue(16)
        preview = self.widget.preview
        self.app.processEvents()
        before = preview.azimuth
        QTest.mousePress(preview, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
        QTest.mouseMove(preview, QPoint(160, 140))
        QTest.mouseRelease(preview, Qt.MouseButton.LeftButton, pos=QPoint(160, 140))
        self.assertNotEqual(preview.azimuth, before)
        self.assertIsNone(preview._drag_position)
        wheel = QWheelEvent(
            QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        QApplication.sendEvent(preview, wheel)
        self.assertGreater(preview.zoom, 1)
        for azimuth, elevation in ((-55, 28), (0, 89.9), (0, 0), (90, 0)):
            preview.set_view(azimuth, elevation)
            self.assertFalse(preview.grab().isNull())
        self.assertNotEqual(preview.view_coordinates((0, 0, 0)), preview.view_coordinates((0, 0, 16)))

    def test_generate_action_writes_files_and_surfaces_errors(self):
        self.widget.add_camera("Limelight")
        with tempfile.TemporaryDirectory() as folder:
            generator = DragonCodeGenerator(output_dir=folder)
            with patch("gui.camera_creator.DragonCodeGenerator", return_value=generator), \
                 patch("gui.camera_creator.QMessageBox.information") as success:
                QTest.mouseClick(self.widget.generate_button, Qt.MouseButton.LeftButton)
                success.assert_called_once()
                self.assertTrue(list(Path(folder).rglob("CameraConfig_COMP_BOT_302.cpp")))
            self.model.add_robot("INVALID_303", "Invalid", 303)
            self.model.project_data["robots"]["INVALID_303"]["camera_config"] = None
            with patch("gui.camera_creator.DragonCodeGenerator", return_value=generator), \
                 patch("gui.camera_creator.QMessageBox.critical") as error:
                self.widget.generate_cameras()
                error.assert_called_once()
                self.assertIn("INVALID_303", error.call_args.args[2])

    def test_suite_tab_shares_model_and_refreshes_after_project_changes(self):
        with patch.object(ProjectModel, "load_app_settings"), patch.object(ProjectModel, "_save_app_settings"):
            suite = DragonSuiteWindow()
            self.addCleanup(suite.close)
            self.assertEqual(suite.tabs.tabText(2), "Camera Creator")
            self.assertIs(suite.camera_creator.model, suite.mechanism_generator.model)
            suite.show()
            suite.mechanism_generator.model.add_robot("TEST_302", "Test", 302)
            suite.tabs.setCurrentIndex(2)
            self.app.processEvents()
            self.assertEqual(suite.camera_creator.robot_combo.currentData(), "TEST_302")
            suite.camera_creator.add_camera("Quest")
            self.assertIn("camera_config", suite.mechanism_generator.project_data["robots"]["TEST_302"])
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "project.json")
                suite.mechanism_generator.model.save_project(path)
                suite.camera_creator.robot_length.lineEdit().setText("42.5")
                suite._save_project()
                loaded = ProjectModel()
                loaded.load_project(path)
                self.assertEqual(loaded.project_data["robots"]["TEST_302"]["camera_config"]["robot_length_in"], 42.5)
            suite._new_project()
            self.assertEqual(suite.camera_creator.robot_combo.count(), 0)


if __name__ == "__main__":
    unittest.main()
