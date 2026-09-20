"""Content generation nodes."""

from agent.state.types import AgentState
from agent.providers.openai_compatible import get_provider
from agent.json_utils import parse_json_response


def generate_modules(state: AgentState) -> AgentState:
    """Generate business modules based on requirements."""
    provider = get_provider()

    # Default upper bound when the user did not specify one.
    DEFAULT_MODULE_MAX = 6
    module_max = state.get("module_count_max") or DEFAULT_MODULE_MAX
    user_input = state.get("user_input", "")

    prompt = f"""Based on the following project, generate business modules for a CRUD admin system.

User's original request: {user_input}

Project: {state['project_name']}
Domain: {state['business_domain']}

Generate AT MOST {module_max} modules (fewer is fine if the domain is simple; never exceed {module_max}).

Output in JSON format:
{{
  "modules": [
    {{
      "name": "ModuleName",
      "label": "模块显示名",
      "description": "模块描述"
    }}
  ]
}}

Note:
- name: PascalCase (e.g., BookManagement)
- label: Chinese display name
- description: What this module does
- Honor any count constraint the user stated in their original request.
- Return exactly one JSON object. Do not use Markdown fences or explanatory text."""

    detail = {
        "title": "模块设计",
        "summary": "",
        "thinking": None,
        "prompt": prompt,
        "response": None,
        "data": None,
        "error": None,
    }

    try:
        resp = provider.call_detailed(prompt=prompt)
        detail["response"] = resp.get("content")
        detail["thinking"] = resp.get("thinking")
        payload = parse_json_response(resp.get("content"))
        modules = payload.get("modules", []) if isinstance(payload, dict) else payload
        state["modules"] = modules

        names = [m["label"] for m in modules]
        detail["summary"] = f"生成 {len(modules)} 个模块: {', '.join(names)}"
        detail["response"] = resp["content"]
        detail["thinking"] = resp.get("thinking")
        detail["data"] = modules

    except Exception as e:
        state["error"] = f"Failed to generate modules: {e}"
        state["modules"] = []
        detail["error"] = str(e)
        detail["summary"] = f"模块生成失败: {e}"

    details = dict(state.get("step_details") or {})
    details["generate_modules"] = detail
    state["step_details"] = details

    state["current_step"] = "generate_modules"
    state["step_history"] = state.get("step_history", []) + ["generate_modules"]
    return state


def generate_fields(state: AgentState) -> AgentState:
    """Generate field definitions for each module."""
    provider = get_provider()

    # Default upper bound when the user did not specify one.
    DEFAULT_FIELD_MAX = 15
    field_max = state.get("field_count_max") or DEFAULT_FIELD_MAX
    user_input = state.get("user_input", "")

    fields = {}
    all_prompts = []
    module_summaries = []

    for module in state.get("modules") or []:
        prompt = f"""Generate fields for the {module['name']} module ({module['label']}: {module['description']})

User's original request: {user_input}

Output in JSON format:
{{
  "fields": [
    {{
      "name": "field_name",
      "label": "字段显示名",
      "type": "String|Integer|Text|DateTime|Boolean|Float|Date|Time",
      "canSearch": true|false,
      "required": true|false,
      "description": "字段说明"
    }}
  ]
}}

Rules:
- name: snake_case (e.g., book_name)
- Don't include id, created_time, modified_time (auto-added)
- Choose appropriate types
- Set canSearch for searchable fields
- Generate AT MOST {field_max} fields per module (fewer is fine; never exceed {field_max})
- Honor any per-module field count constraint the user stated in their original request.
- Return exactly one JSON object. Do not use Markdown fences or explanatory text."""

        all_prompts.append(prompt)

        try:
            resp = provider.call_detailed(prompt=prompt)
            module_fields = parse_json_response(resp.get("content"))
            field_list = [_normalize_field(field) for field in module_fields.get("fields", [])]
            fields[module["name"]] = field_list

            field_names = [f["name"] for f in field_list]
            module_summaries.append(f"{module['label']}: {len(field_list)} fields ({', '.join(field_names[:5])})")

            # Per-module detail
            details = dict(state.get("step_details") or {})
            details[f"generate_fields_{module['name']}"] = {
                "title": f"字段设计 - {module['label']}",
                "summary": f"{len(field_list)} 个字段",
                "thinking": resp.get("thinking"),
                "prompt": prompt,
                "response": resp["content"],
                "data": field_list,
                "error": None,
            }
            state["step_details"] = details

        except Exception:
            fields[module["name"]] = [
                {"name": "name", "label": "名称", "type": "String",
                 "can_search": True, "required": True, "description": "名称字段"}
            ]
            module_summaries.append(f"{module['label']}: fallback (1 field)")

    state["fields"] = fields

    # Summary detail for the overall step
    detail = {
        "title": "字段设计",
        "summary": "; ".join(module_summaries),
        "thinking": None,
        "prompt": "\n\n---\n\n".join(all_prompts),
        "response": None,
        "data": fields,
        "error": None,
    }
    details = dict(state.get("step_details") or {})
    details["generate_fields"] = detail
    state["step_details"] = details

    state["current_step"] = "generate_fields"
    state["step_history"] = state.get("step_history", []) + ["generate_fields"]
    return state


def _normalize_field(field: dict) -> dict:
    """Normalize LLM field keys to the snake_case template contract."""
    normalized = dict(field)
    if "can_search" not in normalized:
        value = normalized.pop("canSearch", False)
        if isinstance(value, str):
            value = value.strip().lower() not in {"", "false", "0", "no"}
        normalized["can_search"] = bool(value)
    return normalized
