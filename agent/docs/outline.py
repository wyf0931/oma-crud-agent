"""LLM-driven outline generation: one call produces ProjectOutline for all modules."""

import logging
from typing import Optional, Tuple

from agent.docs.prompts import build_outline_prompt
from agent.docs.schema import ModuleOutline, ProjectOutline
from agent.providers.openai_compatible import get_provider
from agent.json_utils import parse_json_response

logger = logging.getLogger(__name__)


def generate_outline(
    project_config: dict,
    business_domain: str = "",
    return_error: bool = False,
):
    """Call LLM once to produce a ProjectOutline.

    Args:
        project_config: session's project_config dict
        business_domain: optional domain hint
        return_error: if True, returns (ProjectOutline, error_str); else just ProjectOutline

    Returns:
        ProjectOutline (possibly empty on failure), or (ProjectOutline, error) tuple.
    """
    prompt = build_outline_prompt(project_config, business_domain)
    error: Optional[str] = None
    raw_content: Optional[str] = None

    try:
        resp = get_provider().call_detailed(
            prompt=prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        raw_content = resp.get("content")
    except Exception as e:
        error = f"LLM call failed: {e}"
        logger.warning(error)

    outline, parse_error = _parse_outline(raw_content, project_config)
    if parse_error and not error:
        error = parse_error

    if return_error:
        return outline, (error or "")
    return outline


def _parse_outline(
    raw_content: Optional[str], project_config: dict
) -> Tuple[ProjectOutline, Optional[str]]:
    """Parse LLM JSON response; backfill/drop modules to match project_config.

    Returns (outline, error). On any parse/validation failure, returns a
    fallback empty outline and a non-empty error string.
    """
    fallback = ProjectOutline(system_overview="", modules=[])

    if not raw_content:
        return fallback, "LLM returned empty content"

    try:
        data = parse_json_response(raw_content)
    except ValueError as e:
        logger.warning(f"LLM outline JSON parse failed: {e}")
        return fallback, f"LLM outline JSON parse failed: {e}"

    try:
        outline = ProjectOutline(**data)
    except Exception as e:
        logger.warning(f"LLM outline schema validation failed: {e}")
        return fallback, f"LLM outline schema validation failed: {e}"

    # Reconcile modules against project_config: iterate config order,
    # drop LLM-hallucinated modules not in config, backfill missing ones.
    config_modules = project_config.get("modules", [])
    outline_by_name = {m.name: m for m in outline.modules}

    reconciled: list[ModuleOutline] = []
    for cfg_module in config_modules:
        name = cfg_module["name"]
        if name in outline_by_name:
            reconciled.append(outline_by_name[name])
        else:
            # Backfill: use label as entity_name fallback
            reconciled.append(ModuleOutline(
                name=name,
                entity_name=cfg_module["label"],
                overview_sentence=cfg_module.get("description", ""),
            ))

    return ProjectOutline(
        system_overview=outline.system_overview,
        modules=reconciled,
    ), None
