"""Requirements extraction node."""

from oma_info_system.json_utils import parse_json_response
from oma_info_system.providers.openai_compatible import get_provider
from oma_info_system.workflow.state import AgentState


def understand_requirements(state: AgentState) -> AgentState:
    """Extract project requirements from user input."""
    user_input = state["user_input"]

    provider = get_provider()

    system_prompt = """Extract the following information from the user's project description:
1. Project name (in Chinese)
2. Business domain
3. Key features mentioned
4. Upper bound on module count if the user explicitly specified one (e.g. "不超过4个模块" → 4; "生成3到5个模块" → 5). If not specified, use null.
5. Upper bound on field count per module if explicitly specified (e.g. "每个模块不超过12个字段" → 12). If not specified, use null.

Respond in JSON format:
{
  "project_name": "项目名称",
  "business_domain": "业务领域",
  "features": ["特性1", "特性2"],
  "module_count_max": null,
  "field_count_max": null
}

Return exactly one JSON object. Do not use Markdown fences or explanatory text."""

    detail = {
        "title": "需求理解",
        "summary": "",
        "thinking": None,
        "prompt": user_input,
        "response": None,
        "data": None,
        "error": None,
    }

    try:
        resp = provider.call_detailed(
            prompt=user_input,
            system_prompt=system_prompt,
        )
        detail["response"] = resp.get("content")
        detail["thinking"] = resp.get("thinking")
        result = parse_json_response(resp.get("content"))

        state["project_name"] = result.get("project_name", "管理系统")
        state["business_domain"] = result.get("business_domain", "通用管理")

        # Coerce counts to int or None. LLM may emit null, missing key,
        # or strings like "4" — accept any, fall back to None on failure.
        def _coerce_count(v):
            if v is None:
                return None
            try:
                n = int(v)
                return n if n > 0 else None
            except (TypeError, ValueError):
                return None

        state["module_count_max"] = _coerce_count(result.get("module_count_max"))
        state["field_count_max"] = _coerce_count(result.get("field_count_max"))

        detail["summary"] = (
            f"项目: {state['project_name']}, 领域: {state['business_domain']}"
            f", 模块上限: {state['module_count_max'] if state['module_count_max'] else '默认'}"
            f", 字段上限: {state['field_count_max'] if state['field_count_max'] else '默认'}"
        )
        detail["response"] = resp["content"]
        detail["thinking"] = resp.get("thinking")
        detail["data"] = {
            "user_input": user_input,
            "features": result.get("features", []),
            "module_count_max": state["module_count_max"],
            "field_count_max": state["field_count_max"],
        }

    except Exception as e:
        state["project_name"] = "管理系统"
        state["business_domain"] = "通用管理"
        state["module_count_max"] = None
        state["field_count_max"] = None
        detail["error"] = str(e)
        detail["summary"] = f"提取失败，使用默认值: {e}"

    # Persist into step_details
    details = dict(state.get("step_details") or {})
    details["understand_requirements"] = detail
    state["step_details"] = details

    state["current_step"] = "understand_requirements"
    state["step_history"] = state.get("step_history", []) + ["understand_requirements"]
    state["status"] = "running"

    return state
