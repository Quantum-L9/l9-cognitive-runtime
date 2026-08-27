"""Canonical typed models for cognitive-runtime artifacts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from l9_cognitive_runtime.models.base import ArtifactModel


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"
    UNKNOWN = "unknown"
    NOT_APPLICABLE_WITH_REASON = "not_applicable_with_reason"


class AdapterName(StrEnum):
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    CODEX = "codex"
    CHATGPT = "chatgpt"
    HUMAN_OPERATOR = "human_operator"


class RealizationMode(StrEnum):
    MUTATION = "MUTATION"
    ARTIFACT = "ARTIFACT"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    UNKNOWN = "UNKNOWN"


class DeliveryMode(StrEnum):
    RETURNED_ARCHIVE = "RETURNED_ARCHIVE"
    RETURNED_FILES = "RETURNED_FILES"
    PERSISTED_REPOSITORY = "PERSISTED_REPOSITORY"
    IN_PLACE_WORKSPACE = "IN_PLACE_WORKSPACE"
    NONE = "NONE"


class ObjectiveSpec(ArtifactModel):
    """Canonical objective facts derived once from explicit intent (INV-002)."""

    requested: bool
    realization_mode: RealizationMode
    acceptance_conditions: list[str] = Field(default_factory=list)
    validation_required: bool
    delivery_required: bool
    delivery_mode: DeliveryMode


class AccountabilitySpec(ArtifactModel):
    """Outcome-accountability requirement derived with the objective."""

    required: bool


class IntentContract(ArtifactModel):
    intent_id: str
    mission: str = Field(min_length=1)
    task_type: str
    constraints: list[str]
    desired_outputs: list[str]
    source_context: dict[str, Any] | None = None
    unknowns: list[str] | None = None
    objective: ObjectiveSpec
    accountability: AccountabilitySpec


class ExecutionContract(ArtifactModel):
    contract_id: str
    contract_type: Literal["universal_execution_contract"]
    source_activation_plan: str
    terminal_doctrine: str
    objective: str
    authority_order: list[str]
    kernel_activation: list[str]
    execution_sequence: list[str]
    validation_requirements: list[str]
    output_contract: list[str]
    adapter_targets: list[str]
    version: str | None = None
    stop_conditions: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ValidationContract(ArtifactModel):
    contract_id: str
    contract_type: Literal["validation_contract"]
    validation_ladder: list[str]
    evidence_required: list[str]
    allowed_statuses: list[ValidationStatus]
    report_outputs: list[str] | None = None


class HandoffContract(ArtifactModel):
    contract_id: str
    contract_type: Literal["handoff_contract"]
    handoff_summary: str
    loaded_context: list[str]
    next_action: str
    unknowns: list[str]
    decisions: list[str] | None = None
    adapter_notes: dict[str, Any] | None = None

    @field_validator("unknowns", mode="before")
    @classmethod
    def _coerce_null_unknowns(cls, value: Any) -> Any:
        # Compatibility: HANDOFF_CONTRACT.yaml historically used `unknowns:` (null).
        if value is None:
            return []
        return value


class AdapterRender(ArtifactModel):
    adapter: AdapterName
    source_contract: str
    render_type: str
    content: str
    limitations: list[str] | None = None


class ExecutionGraphNode(ArtifactModel):
    id: str
    phase: str
    kernel_refs: list[str]
    outputs: list[str]
    status: str | None = None


class ExecutionGraphEdge(ArtifactModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    reason: str | None = None


class ExecutionGraph(ArtifactModel):
    graph_id: str
    source_contract: str
    nodes: list[ExecutionGraphNode]
    edges: list[ExecutionGraphEdge]
    terminal_node: str
    validation_gates: list[str]
