# Dragon Code Generator V2 — Template Authoring Guide

This guide explains how the code generator turns the project JSON into C++ files,
and gives a quick Jinja2 syntax reference so anyone can add to or edit the templates.

> For the big-picture architecture (the GUI, the data model, and how the generator
> is organized), see [ARCHITECTURE.md](ARCHITECTURE.md). This document focuses on
> the **template layer** — the payloads templates receive and the Jinja2 you write.

---

## 1. Big Picture

```
gui/ (PyQt6)  ──►  project JSON  ──►  generation/  ──►  Jinja2 templates  ──►  C++ + XML
```

- **`gui/`** — the PyQt6 desktop app (entry point `main.py`). You build robots,
  mechanisms, hardware, control data, and states. It all lives in one nested
  Python dictionary (`project_data`) that is saved/loaded as JSON.
- **`generation/`** — the `DragonCodeGenerator` orchestrator plus focused builders
  (`HardwareBuilder`, `ControlDataBuilder`, `StateBuilder`) and pure naming
  helpers (`naming.py`). It reads `project_data`, reshapes it, and feeds the
  result to the templates.
- **`templates/*.jinja`** — text templates with "holes". The generator fills the
  holes with real values and writes the result to `output_code/`.

---

## 2. The Data Flow (Python → Template)

Everything a template can see is a plain Python **dict** that the generator passes
to `template.render(...)`.

In `_render_commands()`, for each state the generator builds `cmd_data`:

```python
cmd_data = {
    "year": current_year,               # 2026
    "version": self.version,            # "2026.1.0"
    "mechanism_name": mech_name,        # "Intake"
    "command_name": cmd_name,           # "IntakeIntakeCommand"
    "state_enum": nm.state_enum(state), # "STATE_INTAKE"
    "state_data": state_data,           # the whole state dict (see below)
    "unit_includes": self.states.unit_includes(state_data),  # ["wpi/units/angle.hpp", ...]
}
```

Then:

```python
template.render(cmd_data)
```

(The mechanism `.h/.cpp` and container templates receive a larger payload built
by `_build_template_data()` — see [ARCHITECTURE.md](ARCHITECTURE.md) for its keys.)

**The one rule to remember:** every top-level key in that dict becomes a variable
you can use directly in the template.

| Python (`cmd_data`)          | Jinja                   |
| ---------------------------- | ----------------------- |
| `cmd_data["mechanism_name"]`   | `{{ mechanism_name }}`  |
| `cmd_data["state_enum"]`       | `{{ state_enum }}`      |
| `cmd_data["state_data"]`       | `{{ state_data }}`      |
| `cmd_data["unit_includes"]`    | `{{ unit_includes }}`   |

---

## 3. What `state_data` Contains

`state_data` is one state's dict, straight from the GUI/JSON:

```python
{
    "name": "Intake",
    "motor_targets": [
        {"HardwareName": "intake",   "Enabled": True,  "TargetValue": 1.0, "ControlData": "IntakePercentOut", "Unit": "double"},
        {"HardwareName": "extender", "Enabled": True,  "TargetValue": 0.0, "ControlData": "ExtenderPositionDeg", "Unit": "deg"},
    ],
    "solenoid_targets": [
        {"SolenoidName": "clamp", "Enabled": False, "State": True},
    ],
}
```

So to **get a target value**, you walk:

```
state_data  →  motor_targets (a list)  →  one target (a dict)  →  target.TargetValue
```

---

## 4. Jinja2 Syntax Cheat-Sheet

### Three building blocks

| Syntax      | Meaning                                  | Example                       |
| ----------- | ---------------------------------------- | ----------------------------- |
| `{{ ... }}` | **Output** an expression into the file   | `{{ mechanism_name }}`        |
| `{% ... %}` | **Logic** (if/for/set) — prints nothing  | `{% if target.Enabled %}`     |
| `{# ... #}` | **Comment** — not rendered               | `{# loop over motors #}`      |

### Accessing dict values (two equivalent forms)

```jinja
{{ target.TargetValue }}        {# attribute style — cleanest #}
{{ target["TargetValue"] }}     {# bracket style — needed if a key has spaces #}
{{ hw["External Feedback"] }}   {# use brackets when the key has a space #}
```

### Looping a list

```jinja
{% for target in state_data.motor_targets %}
    {{ target.HardwareName }} = {{ target.TargetValue }}
{% endfor %}
```

### Conditionals

```jinja
{% if target.Enabled %} ... {% endif %}

{% if not state_data.motor_targets and not state_data.solenoid_targets %}
    // No targets defined for this state yet.
{% endif %}
```

### Filters (the `|` pipe)

A filter runs a value through a Python function. The value on the left becomes the
function's first argument, so `{{ target | target_method }}` calls
`generate_target_method(target)`.

These custom filters are registered in `DragonCodeGenerator.__init__` (each maps
to a pure function in [`generation/naming.py`](../generation/naming.py)):

```jinja
{{ state  | state_enum }}      {# "Intake" -> "STATE_INTAKE"                 #}
{{ state  | state_class }}     {# "Empty Hopper" -> "EmptyHopper"            #}
{{ hw     | member_var }}      {# hardware dict -> "m_intakeMotor"           #}
{{ target | target_method }}   {# target dict -> "UpdateTargetIntakePercentOut" #}
{{ "deg"  | unit }}            {# "deg" -> "wpi::units::angle::degree_t"     #}
{{ "deg"  | short_unit }}      {# "deg" -> "_deg"                            #}
{{ name   | camel }}           {# "intake_roller" -> "intakeRoller"          #}
{{ name   | upper_camel }}     {# "intake_roller" -> "IntakeRoller"          #}
{{ "Solenoid" | cpp_type }}    {# "Solenoid" -> "frc::Solenoid"             #}
```

Built-in filters also work, e.g.:

```jinja
{{ command_name | replace('Command', '') }}   {# "IntakeIntakeCommand" -> "IntakeIntake" #}
```

### Setting a local variable

```jinja
{% set motorVar = target.HardwareName %}
m_{{ motorVar }}Target
```

---

## 5. Worked Example: Writing a Target Into the File

Inside `Command.cpp.jinja`, `Initialize()` loops the enabled motor targets and
emits a setter call for each:

```jinja
{% for target in state_data.motor_targets %}
{% if target.Enabled %}
    m_mechanism->{{ target | target_method }}(m_{{ target.HardwareName | camel }}Target);
{% endif %}
{% endfor %}
```

Renders to:

```cpp
m_mechanism->UpdateTargetIntakePercentOut(m_intakeTarget);
```

If instead you want to inline the **raw number** rather than a named member:

```jinja
    m_mechanism->{{ target | target_method }}({{ target.TargetValue }});
```

Renders to:

```cpp
m_mechanism->UpdateTargetIntakePercentOut(1.0);
```

> The reference code prefers a named `static constexpr` member (`m_intakeTarget{1}`)
> over a magic number. That member is typed with the target's **unit** and declared
> in the matching `.cpp` (see [`Command.cpp.jinja`](../templates/Command.cpp.jinja)):
>
> ```jinja
> {% for target in state_data.motor_targets %}
> {% if target.Enabled %}
> static constexpr {{ target.Unit | unit }} m_{{ target.HardwareName | camel }}Target{ {{ target.TargetValue }} };
> {% endif %}
> {% endfor %}
> ```
>
> A `deg` target therefore renders as
> `static constexpr wpi::units::angle::degree_t m_intakeTarget{ 1.0 };`.

---

## 6. Whitespace Control (avoiding blank lines)

`{% ... %}` tags leave the surrounding newline behind, which can produce lots of
empty lines in the generated C++. Add a `-` to trim whitespace:

- `{%- if x %}` trims whitespace **before** the tag.
- `{% if x -%}` trims whitespace **after** the tag.

```jinja
{% for target in state_data.motor_targets -%}
    ...
{%- endfor %}
```

---

## 7. Where Things Live

| File                            | Responsibility                                                |
| ------------------------------- | ------------------------------------------------------------- |
| `main.py`                       | Entry point that launches the GUI.                            |
| `gui/`                          | PyQt6 app; builds/edits `project_data`; saves/loads JSON.     |
| `generation/generator.py`       | Orchestrates reshaping `project_data` and rendering templates.|
| `generation/hardware.py`        | Builds hardware init/config bodies + include flags.           |
| `generation/control_data.py`    | Builds control requests, targets, updates, Slot0 mapping.     |
| `generation/states.py`          | Builds per-command unit includes + logging plumbing.          |
| `generation/naming.py`          | Pure naming/formatting helpers registered as Jinja2 filters.  |
| `templates/Mechanism.h.jinja`   | Subsystem header (enum, members, command factories).          |
| `templates/Mechanism.cpp.jinja` | Subsystem implementation (hardware init, control data).       |
| `templates/Container.h/.cpp.jinja` | Container glue for the mechanism.                          |
| `templates/Command.h.jinja`     | One command class header per state.                           |
| `templates/Command.cpp.jinja`   | One command class implementation per state.                   |
| `templates/Mechanism.xml.jinja` | Per-team control-data deploy XML.                             |
| `output_code/`                  | Generated output (created on Generate).                       |

---

## 8. Generator Helper Functions (the filters)

All live in [`generation/naming.py`](../generation/naming.py) and are pure
functions (no template/project state), so they are reused by the builders too.

| Function                    | Filter name     | Input → Output                                  |
| --------------------------- | --------------- | ----------------------------------------------- |
| `state_enum(name)`          | `state_enum`    | `"Empty Hopper"` → `"STATE_EMPTY_HOPPER"`       |
| `state_class(name)`         | `state_class`   | `"Empty Hopper"` → `"EmptyHopper"`              |
| `member_variable(hw)`       | `member_var`    | `{name:"intake", type:"TalonFX"}` → `"m_intakeMotor"` |
| `generate_target_method(t)` | `target_method` | motor target → `"UpdateTarget<Motor><ControlData>"` |
| `get_unit(unit)`            | `unit`          | `"deg"` → `"wpi::units::angle::degree_t"`       |
| `get_short_unit(unit)`      | `short_unit`    | `"deg"` → `"_deg"`                              |
| `camel_case(name)`          | `camel`         | `"intake_roller"` → `"intakeRoller"`            |
| `upper_camel_case(name)`    | `upper_camel`   | `"intake_roller"` → `"IntakeRoller"`            |
| `cpp_type(hw_type)`         | `cpp_type`      | `"Solenoid"` → `"frc::Solenoid"`                |

These accept any of the common name styles (`spaced`, `snake_case`, `camelCase`,
or an already-prefixed `STATE_...`) and normalize them, so you don't have to worry
about exactly how a name was typed in the GUI.

---

### TL;DR mental model

> `cmd_data` (a Python dict) → its keys become template variables →
> use `{{ }}` to print, `{% %}` to loop/branch, and `| filter` to transform values
> through generator methods. To reach a target value it's always
> `state_data.motor_targets` (list) → `target` (dict) → `target.TargetValue`.
