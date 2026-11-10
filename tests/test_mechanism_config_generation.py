import tempfile
import unittest
from pathlib import Path

from generation import DragonCodeGenerator
from gui.model import ProjectModel


class MechanismConfigGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.generator = DragonCodeGenerator(output_dir=self.temp.name)
        self.model = ProjectModel()

    def tearDown(self):
        self.temp.cleanup()

    @property
    def configs_dir(self):
        return Path(self.temp.name) / "src" / "main" / "cpp" / "mechanisms" / "configs"

    def test_generate_robot_configs_and_manager_dispatch(self):
        self.model.add_robot("COMP_BOT_302", "Comp Bot", 302)
        self.model.add_mechanism("COMP_BOT_302", "Intake")
        self.model.add_robot("PRACTICE_BOT_303", "Practice Bot", 303)
        self.model.add_mechanism("PRACTICE_BOT_303", "Launcher")

        self.generator.generate(self.model.project_data)

        manager = (self.configs_dir / "MechanismConfigMgr.cpp").read_text()
        comp_header = (self.configs_dir / "MechanismConfigCompBot_302.h").read_text()
        comp_source = (self.configs_dir / "MechanismConfigCompBot_302.cpp").read_text()
        practice_source = (self.configs_dir / "MechanismConfigPracticeBot_303.cpp").read_text()

        self.assertIn("case RobotIdentifier::COMP_BOT_302:", manager)
        self.assertIn("new MechanismConfigCompBot_302()", manager)
        self.assertIn("case RobotIdentifier::PRACTICE_BOT_303:", manager)
        self.assertIn("new MechanismConfigPracticeBot_303()", manager)
        self.assertNotIn(".h#include", manager)
        self.assertIn("Intake *m_theIntake", comp_header)
        self.assertIn("CreateCompBot302()", comp_source)
        self.assertNotIn("Launcher", comp_source)
        self.assertIn("CreatePracticeBot303()", practice_source)

    def test_duplicate_team_numbers_are_rejected(self):
        self.model.add_robot("COMP_BOT_302", "Comp Bot", 302)
        self.model.add_robot("PRACTICE_BOT_302", "Practice Bot", 302)

        with self.assertRaisesRegex(ValueError, "share team number 302"):
            self.generator.generate(self.model.project_data)


if __name__ == "__main__":
    unittest.main()