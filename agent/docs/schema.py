"""Pydantic models for LLM-generated user manual outline."""

from pydantic import BaseModel, Field


class ModuleOutline(BaseModel):
    """LLM-generated outline metadata for a single module."""

    name: str = Field(..., description="Module name, must match project_config module.name")
    entity_name: str = Field(
        ...,
        description="Singular short name (e.g. 图书 for 图书管理)",
    )
    overview_sentence: str = Field(..., description="One-sentence module purpose")


class ProjectOutline(BaseModel):
    """Top-level outline returned by LLM, covers all modules in one call."""

    system_overview: str = Field(..., description="1-2 paragraph system overview in Chinese")
    modules: list[ModuleOutline] = Field(default_factory=list)
