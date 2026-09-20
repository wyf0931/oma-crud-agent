"""LLM prompt templates for user manual outline generation."""

OUTLINE_PROMPT_TEMPLATE = """你是用户手册大纲生成器。基于项目信息生成结构化大纲 JSON。

项目名: {project_name}
业务领域: {business_domain}
模块列表（共 {module_count} 个）:
{module_list}

输出 JSON（严格按此 schema，不要多余字段，不要 markdown 代码块包裹）:
{{
  "system_overview": "1-2 段中文，介绍系统由哪些模块组成，每个模块的核心作用。要自然流畅，不要列点。",
  "modules": [
    {{
      "name": "BookManagement",
      "entity_name": "图书",
      "overview_sentence": "..."
    }}
  ]
}}

约束:
- entity_name 必须是 label 的简称，例如 "图书管理"→"图书"、"用户管理"→"用户"、"打印机信息管理"→"打印机"
- system_overview 必须提到每个模块的 label
- modules 数组的 name 必须与输入的模块 name 完全一致
- 不要臆造字段名或业务规则
- 输出纯 JSON
"""


def build_outline_prompt(project_config: dict, business_domain: str = "") -> str:
    """Format the outline prompt with project metadata."""
    project = project_config["project"]
    modules = project_config.get("modules", [])
    module_list = "\n".join(
        f"  {i+1}. name={m['name']}, label={m['label']}, description={m.get('description', '')}"
        for i, m in enumerate(modules)
    )
    return OUTLINE_PROMPT_TEMPLATE.format(
        project_name=project["name"],
        business_domain=business_domain or "(未提供)",
        module_count=len(modules),
        module_list=module_list,
    )
