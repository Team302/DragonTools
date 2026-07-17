# Dragon Code Generator V2 — Generator & Template Guide

This guide explains how the code generator turns the project JSON into C++ files,
and gives a quick Jinja2 syntax reference so anyone can add to or edit the templates.

---

## 1. Big Picture

```
GUI (main.py)  ──►  project JSON  ──►  generator.py  ──►  Jinja2 templates  ──►  C++ files
```

- **`main.py`** — the PyQt6 GUI. You build robots, mechanisms, hardware, control
  data, and states. It all lives in one nested Python dictionary (`project_data`)
  that is saved/loaded as JSON.
- **`generator.py`** — the `DragonCodeGenerator` class. It reads `project_data`,
  reshapes it, and feeds it to the templates.
- **`templates/*.jinja`** — text templates with "holes". The generator fills the
  holes with real values and writes the result to `output_code/`.

---

## 2. The Data Flow (Python → Template)

Everything a template can see is a plain Python **dict** that the generator passes
to `template.render(...)`.

In `generate()`, for each command the generator builds `cmd_data`:

```python
cmd_data = {
    "year": current_year,            # 2026
    "mechanism_name": mech_name,     # "Intake"
    "command_name": cmd_name,        # "IntakeIntakeCommand"
    "state_enum": self.state_enum(state),  # "STATE_INTAKE"
    "state_data": state_data,        # the whole state dict (see below)
}
```

Then:

```python
template.render(cmd_data)
```

**The one rule to remember:** every top-level key in that dict becomes a variable
you can use directly in the template.

| Python (`cmd_data`)        | Jinja                  |
| -------------------------- | ---------------------- |
| `cmd_data["mechanism_name"]` | `{{ mechanism_name }}` |
| `cmd_data["state_enum"]`     | `{{ state_enum }}`     |
| `cmd_data["state_data"]`     | `{{ state_data }}`     |

---

## 3. What `state_data` Contains

`state_data` is one state's dict, straight from the GUI/JSON:

```python
{
    "name": "STATE_INTAKE",
    "motor_targets": [
        {"HardwareName": "intake",   "Enabled": True,  "TargetValue": 1.0, "ControlData": "PercentOut"},
        {"HardwareName": "extender", "Enabled": True,  "TargetValue": 0.0, "ControlData": "PositionDeg"},
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

These custom filters are registered in `DragonCodeGenerator.__init__`:

```jinja
{{ state  | state_enum }}      {# "Intake" -> "STATE_INTAKE"                 #}
{{ state  | state_class }}     {# "Empty Hopper" -> "EmptyHopper"            #}
{{ hw     | member_var }}      {# hardware dict -> "m_intakeMotor"           #}
{{ target | target_method }}   {# target dict -> "UpdateTargetIntakePercentOut" #}
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
    m_mechanism->{{ target | target_method }}(m_{{ target.HardwareName }}Target);
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
> over a magic number. That member must be **declared in the matching `.h`**, e.g.
> in `Command.h.jinja`:
>
> ```jinja
> private:
>     {{ mechanism_name }} *m_mechanism;
> {% for target in state_data.motor_targets %}
> {% if target.Enabled %}
>     static constexpr double m_{{ target.HardwareName }}Target{ {{ target.TargetValue }} };
> {% endif %}
> {% endfor %}
> ```

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

| File                          | Responsibility                                              |
| ----------------------------- | ----------------------------------------------------------- |
| `main.py`                     | GUI; builds/edits `project_data`; saves/loads JSON.         |
| `generator.py`                | Reshapes `project_data` and renders templates.              |
| `templates/Mechanism.h.jinja` | Subsystem header (enum, members, command factories).        |
| `templates/Mechanism.cpp.jinja` | Subsystem implementation (hardware init, control data).   |
| `templates/Command.h.jinja`   | One command class header per state.                         |
| `templates/Command.cpp.jinja` | One command class implementation per state.                 |
| `output_code/`                | Generated C++ output (created on Generate).                 |

---

## 8. Generator Helper Methods (the filters)

| Method                      | Filter name     | Input → Output                                  |
| --------------------------- | --------------- | ----------------------------------------------- |
| `state_enum(name)`          | `state_enum`    | `"Empty Hopper"` → `"STATE_EMPTY_HOPPER"`       |
| `state_class(name)`         | `state_class`   | `"Empty Hopper"` → `"EmptyHopper"`              |
| `as_member_variable(hw)`    | `member_var`    | `{name:"intake", type:"TalonFX"}` → `"m_intakeMotor"` |
| `generate_target_method(t)` | `target_method` | motor target → `"UpdateTarget<Motor><ControlData>"` |

These accept any of the common name styles (`spaced`, `snake_case`, `camelCase`,
or an already-prefixed `STATE_...`) and normalize them, so you don't have to worry
about exactly how a name was typed in the GUI.

---

### TL;DR mental model

> `cmd_data` (a Python dict) → its keys become template variables →
> use `{{ }}` to print, `{% %}` to loop/branch, and `| filter` to transform values
> through generator methods. To reach a target value it's always
> `state_data.motor_targets` (list) → `target` (dict) → `target.TargetValue`.
