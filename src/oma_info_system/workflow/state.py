"""State type definitions for the agent workflow."""

from typing import Any, Literal, TypedDict


class Module(TypedDict):
    """Business module definition."""

    name: str
    label: str
    description: str


class Field(TypedDict):
    """Field definition."""

    name: str
    label: str
    type: Literal["String", "Integer", "Text", "DateTime", "Boolean", "Float", "Date", "Time"]
    can_search: bool
    required: bool
    description: str


class ReviewIssue(TypedDict):
    """Review issue."""

    type: str
    severity: Literal["error", "warning", "info"]
    message: str
    suggestion: str | None


class StepDetail(TypedDict, total=False):
    """Detail info for a single workflow step — persisted & shown in UI."""

    title: str
    summary: str  # one-line human summary
    thinking: str | None  # LLM reasoning / chain-of-thought
    prompt: str | None  # the prompt sent to LLM
    response: str | None  # raw LLM response text
    data: dict[str, Any] | None  # structured output (modules, fields, etc.)
    error: str | None  # error message if step failed
    duration_ms: int | None  # wall-clock time for this step


class AgentState(TypedDict):
    """Main state for the admin generator workflow."""

    # Input
    user_input: str
    mode: Literal["yolo", "hitl"]
    output_dir: str

    # Workflow progress
    current_step: str
    step_history: list[str]
    step_details: dict[str, Any]  # step_id → StepDetail dict

    # Requirements
    project_name: str | None
    business_domain: str | None
    module_count_max: int | None  # user-supplied upper bound; None = use default
    field_count_max: int | None  # user-supplied upper bound per module; None = use default

    # Generated content
    modules: list[Module] | None
    fields: dict[str, list[Field]] | None

    # Project
    project_config: dict[str, Any] | None
    project_path: str | None

    # Review
    review_issues: list[ReviewIssue]
    review_fixes: list[str]

    # Test state
    test_errors: str | None
    retry_count: int
    max_retries: int

    # HITL
    approval_required: bool
    pending_approval: str | None
    approval_response: str | None

    # Result
    result: str | None
    error: str | None
    status: Literal["pending", "running", "completed", "failed"]
