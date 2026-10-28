# DragonTools — Dragon Tool Suite

A desktop **tool suite** for **FIRST Robotics Team 302 (Lake Orion Robotics)**.
The suite is a tabbed PyQt6 application designed to hold many robot-development
tools; each tool lives in its own tab.

The first tool, the **Mechanism Generator**, turns a visual mechanism definition
into ready-to-build C++ for a WPILib / CTRE Phoenix 6 robot project. You describe
your robots, their mechanisms, the hardware on each mechanism, the control data
(PID / control requests), and the states each mechanism can be in — all through
the GUI. The tool then generates the matching subsystem classes, per-state command
classes, container glue, and the per-team control-data XML.

```
GUI (PyQt6)  →  project JSON  →  code generator  →  Jinja2 templates  →  C++ + XML
```

### Tools in the suite

| Tab                     | Status        | What it does                                            |
| ----------------------- | ------------- | ------------------------------------------------------- |
| **Mechanism Generator** | Available     | Generates mechanism/command/container C++ + control XML.|
| **Auton Builder**       | Placeholder   | Reserved blank tab for the upcoming autonomous tool.    |
| **Camera Creator**      | Available     | Configures robot cameras with a live interactive 3D mounting preview and C++ export. |

---

## Features

- **Visual project editor** — a tree of Robots → Mechanisms → Hardware / Control
  Data / States, with a contextual property editor for every node.
- **Multi-robot aware** — the same mechanism can live on several robots (comp bot,
  practice bot, etc.); each robot gets its own `Create`/`Initialize` methods and
  its own control-data XML keyed by team number.
- **Hardware support** — TalonFX, TalonFXS, CANCoder, CANdi, Solenoid, and
  DigitalInput, each with sensible CTRE Phoenix 6 default configurations.
- **Closed & open loop** — control data drives Slot0 gains, Motion Magic, and the
  correct control request per motor target.
- **Deterministic output** — the generated tree drops straight into a WPILib
  project layout (`src/main/cpp/mechanisms/...` and `src/main/deploy/...`).
- **Save / load** — projects are plain JSON, so they diff and version-control well.

---

## Requirements

- Python 3.10+
- [PyQt6](https://pypi.org/project/PyQt6/)
- [Jinja2](https://pypi.org/project/Jinja2/)

Install the dependencies:

```powershell
pip install PyQt6 Jinja2
```

---

## Running the tool

From the repository root:

```powershell
python main.py
```

This launches the tabbed Dragon Tool Suite window. The tool remembers the last project
you opened (stored in `tool_settings.json`) and reloads it on startup.

### Typical workflow

1. Open the **Mechanism Generator** tab.
2. **Add a Robot** — give it a name and team number.
3. **Add a Mechanism** to that robot (e.g. `Intake`, `Elevator`).
4. Under the mechanism, fill in:
   - **Hardware** — the motors, sensors, solenoids, and their CTRE configs.
   - **Control Data** — named control requests + PID/feedforward gains + units.
   - **States / Commands** — each state sets a target value + control data per
     motor, and an on/off state per solenoid.
5. Click **Generate C++ Code**. Output is written to `output_code/`.

The generated tree looks like:

```
output_code/
  src/main/cpp/mechanisms/<mech>/
    <Mech>.h / .cpp                     # subsystem
    <Mech>Container.h / .cpp            # container glue
    commands/
      <Mech><State>Command.h / .cpp     # one command class per state
  src/main/deploy/<team>/mechanisms/
    <Mech>.xml                          # per-team control-data XML
```

---

### Camera Creator workflow

1. Add your robots in **Mechanism Generator**, then open **Camera Creator** and
   select a robot. Camera settings belong to that robot in the same project JSON.
2. Enter the robot **length** (front to back) and **width** (left to right).
   Defaults are 30 inches; replace them with your robot's dimensions.
3. Use **+ Add Limelight** or **+ Add Quest**. Select a device to edit its mounting
   X/Y/Z and pitch/yaw/roll. Limelights also expose their NetworkTables name,
   identifier, model, usage, initial pipeline, and LED mode from the robot APIs.
   Names must use lowercase letters, numbers and hyphens, starting with a letter.
4. Every length and angle field has its own unit dropdown beside it. Lengths
   default to **inches** (or **meters**) and angles to **degrees** (or
   **radians**); switching a field's unit converts its display without
   changing the mounting pose. Values are shown and generated with 4 decimal
   places. Generated C++ uses each field's unit literal
   (`_in` / `_m` and `_deg` / `_rad`), reusing the generator's unit suffix helpers
   without explicit C++ type wrappers or conversion calls.
5. Drag the **3D preview** to orbit, scroll to zoom, or select Top, Front, Left,
   or Reset 3D. The highlighted device is the selected camera. Its main arrow
   shows its facing direction; the blue line shows its local up direction, so
   roll is visible too. Robot/device thicknesses and device sizes are illustrative.
6. **Save Project** (Ctrl+S) saves cameras and dimensions alongside mechanisms.
   **Generate Camera C++** exports all configured robots' camera definitions;
   **Generate C++ Code** in Mechanism Generator also includes them.

Robot space matches the supplied `DragonLimelight` / `DragonQuest` constructors:
**+X forward, +Y left, +Z up**, measured from robot center at floor level.
The rotation is WPILib's `Rz(yaw) * Ry(pitch) * Rx(roll)`: positive yaw turns
left, positive pitch tilts down, and roll turns around local forward.
The linked [Limelight pose documentation](https://docs.limelightvision.io/docs/docs-limelight/pipeline-apriltag/apriltag-robot-localization-megatag2#configuring-your-limelights-robot-space-pose)
describes an offset labeled Right: if entering values in such a UI, **Right = -Y**.
Generated code uses the robot API's **left-positive** convention directly.

The current robot API provides four distinct Limelight identifiers and a single
Quest registration per robot. The editor prevents adding more than four
Limelights or one Quest; generation also rejects duplicate identifiers/names,
unsupported options, invalid values and ambiguous team numbers.

Camera files are written under
`output_code/src/main/cpp/vision/definitions/`:

- `CameraConfig_<TEAM_NUMBER>.h` / `.cpp` for each configured robot.
- `CameraConfigMgr.h` / `.cpp` mapping those robots' `RobotIdentifier` entries
  to their configurations. **This replaces the robot project's existing camera
  manager mappings**; only robots configured in this project are mapped. There
  is no implicit simulation mapping.

Generate the matching `RobotIdentifier.h` using Mechanism Generator, then copy
the generated files into your robot project, retaining its existing base
`CameraConfig` and vision implementation. The generator does not modify the
reference robot sources. Older projects without camera settings are unchanged
and do not emit camera files. Stale files from earlier exports are not deleted.

Run camera data, generation, GUI and suite integration tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_cameras.py -v
```

---

## Project layout

| Path                     | What lives there                                                   |
| ------------------------ | ------------------------------------------------------------------ |
| `main.py`                | Entry point — launches the Dragon Tool Suite window.              |
| `gui/`                   | The desktop app: suite shell, window, data model, constants.      |
| `gui/suite.py`           | The tabbed suite shell that hosts every tool.                     |
| `generation/`            | The code generator: orchestrator + focused builders + naming.     |
| `templates/`             | Jinja2 templates for the generated C++ and XML.                   |
| `docs/`                  | Developer documentation (see below).                              |
| `output_code/`           | Generated output (git-ignored, created on Generate).              |
| `tool_settings.json`     | Remembers the last opened project (git-ignored).                  |

---

## Documentation for contributors

If you want to extend this tool — add a new hardware type, a new config block, a
new template, or a new generator filter — start here:

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how the whole tool fits
  together, the data model, each module's job, and step-by-step recipes for the
  most common changes.
- **[docs/TEMPLATE_GUIDE.md](docs/TEMPLATE_GUIDE.md)** — a focused guide to the
  generator/template layer and a Jinja2 cheat-sheet.

---

## License

MIT — see [LICENSE](LICENSE). Generated files carry the Team 302 copyright header.