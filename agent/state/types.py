"""State type definitions for the agent workflow."""

from typing import TypedDict, Literal, Optional, List, Dict, Any


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
    suggestion: Optional[str]


class StepDetail(TypedDict, total=False):
    """Detail info for a single workflow step — persisted & shown in UI."""
    title: str
    summary: str                          # one-line human summary
    thinking: Optional[str]               # LLM reasoning / chain-of-thought
    prompt: Optional[str]                 # the prompt sent to LLM
    response: Optional[str]               # raw LLM response text
    data: Optional[Dict[str, Any]]        # structured output (modules, fields, etc.)
    error: Optional[str]                  # error message if step failed
    duration_ms: Optional[int]            # wall-clock time for this step


class AgentState(TypedDict):
    """Main state for the admin generator workflow."""
    # Input
    user_input: str
    mode: Literal["yolo", "hitl"]
    output_dir: str

    # Workflow progress
    current_step: str
    step_history: List[str]
    step_details: Dict[str, Any]  # step_id → StepDetail dict

    # Requirements
    project_name: Optional[str]
    business_domain: Optional[str]
    module_count_max: Optional[int]   # user-supplied upper bound; None = use default
    field_count_max: Optional[int]    # user-supplied upper bound per module; None = use default

    # Generated content
    modules: Optional[List[Module]]
    fields: Optional[Dict[str, List[Field]]]

    # Project
    project_config: Optional[Dict[str, Any]]
    project_path: Optional[str]

    # Review
    review_issues: List[ReviewIssue]
    review_fixes: List[str]

    # Test state
    test_errors: Optional[str]
    retry_count: int
    max_retries: int

    # HITL
    approval_required: bool
    pending_approval: Optional[str]
    approval_response: Optional[str]

    # Result
    result: Optional[str]
    error: Optional[str]
    status: Literal["pending", "running", "completed", "failed"]
