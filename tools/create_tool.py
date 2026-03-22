"""
Create a new tool. THE key capability.
This is how the agent evolves: by creating tools it needs but doesn't have.
"""

import importlib.util
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

TOOL_SPEC = {
    "name": "create_tool",
    "description": "Create a new tool. Provide name, description, and Python code for execute() body. Tool becomes available immediately.",
    "params": {
        "name": "Tool name (snake_case)",
        "description": "What the tool does",
        "params_spec": "Dict of param_name: description",
        "code": "Python code for the execute(params) function body",
    },
}

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
EVOLUTION_DIR = ROOT / "evolution"


def execute(params: dict) -> str:
    name = params.get("name", "").strip()
    description = params.get("description", "")
    params_spec = params.get("params_spec", {})
    code = params.get("code", "")

    if not name or not code:
        return "Need 'name' and 'code' at minimum."
    if not name.replace("_", "").isalnum():
        return "Name must be snake_case alphanumeric."
    if name == "core":
        return "Cannot create tool named 'core'."

    indented = "\n".join("    " + line for line in code.strip().split("\n"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tool_code = f'"""{name}: {description}\nCreated: {ts}\n"""\n\n'
    tool_code += "TOOL_SPEC = {\n"
    tool_code += f'    "name": {repr(name)},\n'
    tool_code += f'    "description": {repr(description)},\n'
    tool_code += f'    "params": {repr(params_spec)},\n'
    tool_code += "}\n\n\ndef execute(params: dict) -> str:\n"
    tool_code += indented + "\n"

    tool_path = TOOLS_DIR / f"{name}.py"
    tool_path.write_text(tool_code, encoding="utf-8")

    try:
        spec = importlib.util.spec_from_file_location(f"tools_{name}", str(tool_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "TOOL_SPEC") or not hasattr(module, "execute"):
            raise ValueError("Tool must have TOOL_SPEC and execute")
        result = module.execute({})
        if not isinstance(result, str):
            raise ValueError(f"execute must return str, got {type(result)}")
    except Exception as e:
        tool_path.unlink(missing_ok=True)
        return f"Tool created but smoke test failed: {e}. Fix the tool and try again."

    EVOLUTION_DIR.mkdir(exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "tool_created", "name": name, "description": description}
    with open(EVOLUTION_DIR / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return f"🌱 Tool '{name}' created → tools/{name}.py"
