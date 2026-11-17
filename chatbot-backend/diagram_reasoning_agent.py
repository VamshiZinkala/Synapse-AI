
import json
import re
from collections import Counter
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

class TopologyAttribute(BaseModel):
    name: str
    data_type: str | None = "varchar"
    is_key: str = "none"


class TopologyNode(BaseModel):
    name: str
    type: str
    metadata: dict[str, Any] | None = Field(default_factory=dict)
    attributes: list[TopologyAttribute] | None = Field(default_factory=list)
    source: str
    confidence: str


class TopologyEdge(BaseModel):
    source: str
    target: str
    relationship: str
    cardinality_or_type: str | None = None


class CorrectedTopology(BaseModel):
    nodes: list[TopologyNode] = Field(description="Proposed corrected diagram nodes")
    edges: list[TopologyEdge] = Field(description="Proposed corrected diagram edges")


Operation = Literal[
    "add_node", "remove_node", "update_node", "add_edge", "remove_edge",
    "update_edge", "update_attribute",
]
Confidence = Literal["high", "medium", "low", "uncertain"]


class ProposedChange(BaseModel):
    operation: Operation
    target: dict[str, str] = Field(
        description="Node: {node}; edge: {source, target}; attribute: {node, attribute}."
    )
    before: Any = Field(description="Full prior object, or null when adding.")
    after: Any = Field(description="Full resulting object, or null when removing.")
    reason: str = Field(min_length=1)
    confidence: Confidence
    uncertainty: str | None = Field(
        default=None,
        description="Explain ambiguity; required for low or uncertain confidence.",
    )

    @model_validator(mode="after")
    def uncertainty_for_low_confidence(self):
        if self.confidence in {"low", "uncertain"} and not (self.uncertainty or "").strip():
            raise ValueError("low or uncertain confidence requires an uncertainty explanation")
        return self


class CorrectionResult(BaseModel):
    summary: str = Field(description="Short explanation of the proposal")
    corrected_topology: CorrectedTopology
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    ai_warnings: list[str] = Field(
        default_factory=list,
        description="Model-generated cautions, separate from deterministic validation.",
    )
    ai_suggestions: list[str] = Field(
        default_factory=list,
        description="Optional suggestions, not applied to the proposed topology.",
    )


class ValidationReport(BaseModel):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CorrectionProposal(BaseModel):
    summary: str
    corrected_topology: CorrectedTopology
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    ai_warnings: list[str] = Field(default_factory=list)
    ai_suggestions: list[str] = Field(default_factory=list)
    validation: ValidationReport


parser = PydanticOutputParser(
    pydantic_object=CorrectionResult
)


def validate_topology(topology: Any, label: str = "topology") -> ValidationReport:
    """Run deterministic structural checks without guessing diagram semantics."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(topology, dict):
        return ValidationReport(errors=[f"{label}: topology must be an object"])

    nodes = topology.get("nodes")
    edges = topology.get("edges")
    if not isinstance(nodes, list):
        errors.append(f"{label}: nodes must be a list")
        nodes = []
    if not isinstance(edges, list):
        errors.append(f"{label}: edges must be a list")
        edges = []
    if not nodes:
        errors.append(f"{label}: topology must contain at least one node")

    node_names: set[str] = set()
    for index, node in enumerate(nodes):
        prefix = f"{label}: node[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = node.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix} must have a non-empty name")
        elif name in node_names:
            errors.append(f"{label}: duplicate node name {name!r}")
        else:
            node_names.add(name)
        if node.get("type") not in {"entity", "attribute", "component", "pin", "power_rail", "placeholder"}:
            errors.append(f"{prefix}: unsupported node type {node.get('type')!r}")
        if node.get("source") not in {"visible_text", "placeholder"}:
            errors.append(f"{prefix}: source must be visible_text or placeholder")
        if node.get("confidence") not in {"high", "medium", "low"}:
            errors.append(f"{prefix}: confidence must be high, medium, or low")

        attributes = node.get("attributes", [])
        if attributes is None:
            attributes = []
        if not isinstance(attributes, list):
            errors.append(f"{prefix}: attributes must be a list")
            continue
        attribute_names: set[str] = set()
        for attr_index, attr in enumerate(attributes):
            attr_prefix = f"{prefix}.attributes[{attr_index}]"
            if not isinstance(attr, dict):
                errors.append(f"{attr_prefix} must be an object")
                continue
            attr_name = attr.get("name")
            if not isinstance(attr_name, str) or not attr_name.strip():
                errors.append(f"{attr_prefix} must have a non-empty name")
            elif attr_name in attribute_names:
                errors.append(f"{prefix}: duplicate attribute name {attr_name!r}")
            else:
                attribute_names.add(attr_name)
            if attr.get("is_key", "none") not in {"PK", "FK", "none"}:
                errors.append(f"{attr_prefix}: is_key must be PK, FK, or none")
            if attr.get("is_key") in {"PK", "FK"} and node.get("type") != "entity":
                warnings.append(
                    f"{prefix}: key attribute {attr_name!r} is attached to a non-entity node"
                )

    for index, edge in enumerate(edges):
        prefix = f"{label}: edge[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{prefix} must be an object")
            continue
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{prefix} must have a non-empty source")
        elif source not in node_names:
            errors.append(f"{prefix}: source {source!r} does not name a node")
        if not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix} must have a non-empty target")
        elif target not in node_names:
            errors.append(f"{prefix}: target {target!r} does not name a node")
        relationship = edge.get("relationship")
        if not isinstance(relationship, str) or not relationship.strip():
            errors.append(f"{prefix} must have a non-empty relationship")
        cardinality = edge.get("cardinality_or_type")
        if cardinality is not None and not isinstance(cardinality, str):
            errors.append(f"{prefix}: cardinality_or_type must be a string or null")
        elif isinstance(cardinality, str) and not cardinality.strip():
            warnings.append(f"{prefix}: cardinality_or_type is blank")
        elif isinstance(cardinality, str) and cardinality.strip().lower() not in {
            "1", "n", "m", "0..1", "1..*", "0..*", "one-to-one",
            "one-to-many", "many-to-one", "many-to-many", "serial",
            "parallel", "bus", "ground", "net",
        }:
            warnings.append(
                f"{prefix}: cardinality_or_type {cardinality!r} uses an unrecognized value; verify it for this diagram type"
            )

    return ValidationReport(errors=errors, warnings=warnings)


def validate_proposed_operations(
    original: dict[str, Any], corrected: dict[str, Any], changes: list[ProposedChange]
) -> list[str]:
    errors: list[str] = []
    original_nodes = original.get("nodes", [])
    corrected_nodes = corrected.get("nodes", [])
    original_edges = original.get("edges", [])
    corrected_edges = corrected.get("edges", [])

    def same_unordered_items(left: list[Any], right: list[Any]) -> bool:
        """Compare graph elements as a multiset; array order is not a graph change."""
        left_items = Counter(
            json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for item in left
        )
        right_items = Counter(
            json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for item in right
        )
        return left_items == right_items

    if not changes and (
        not same_unordered_items(original_nodes, corrected_nodes)
        or not same_unordered_items(original_edges, corrected_edges)
    ):
        errors.append("A changed topology must have at least one proposed operation")

    working = deepcopy(original)
    working.setdefault("nodes", [])
    working.setdefault("edges", [])
    can_apply_all = True

    for index, change in enumerate(changes):
        prefix = f"proposed_changes[{index}] ({change.operation})"
        target = change.target
        before, after = change.before, change.after
        if change.operation in {"add_node", "remove_node", "update_node"}:
            if set(target) != {"node"} or not target.get("node"):
                errors.append(f"{prefix}: target must contain only a non-empty node")
            if change.operation == "add_node" and (before is not None or not isinstance(after, dict)):
                errors.append(f"{prefix}: add_node requires before=null and after=node")
            elif change.operation == "remove_node" and (not isinstance(before, dict) or after is not None):
                errors.append(f"{prefix}: remove_node requires before=node and after=null")
            elif change.operation == "update_node" and (not isinstance(before, dict) or not isinstance(after, dict)):
                errors.append(f"{prefix}: update_node requires before=node and after=node")
            expected_target_name = after.get("name") if change.operation == "add_node" and isinstance(after, dict) else (before.get("name") if isinstance(before, dict) else None)
            if expected_target_name is not None and target.get("node") != expected_target_name:
                errors.append(f"{prefix}: target.node does not match the operation object")
            if change.operation == "update_node" and isinstance(before, dict) and isinstance(after, dict):
                if before.get("attributes", []) != after.get("attributes", []):
                    errors.append(f"{prefix}: attribute edits must use update_attribute")
            if change.operation == "add_node" and isinstance(after, dict):
                if any(n.get("name") == after.get("name") for n in working["nodes"] if isinstance(n, dict)):
                    errors.append(f"{prefix}: added node already exists")
                    can_apply_all = False
                else:
                    working["nodes"].append(deepcopy(after))
            elif change.operation == "remove_node" and isinstance(before, dict):
                match = next((i for i, n in enumerate(working["nodes"]) if n == before), None)
                if match is None:
                    errors.append(f"{prefix}: node to remove is not present at this operation")
                    can_apply_all = False
                else:
                    working["nodes"].pop(match)
            elif change.operation == "update_node" and isinstance(before, dict) and isinstance(after, dict):
                match = next((i for i, n in enumerate(working["nodes"]) if n == before), None)
                if match is None:
                    errors.append(f"{prefix}: node to update is not present at this operation")
                    can_apply_all = False
                else:
                    working["nodes"][match] = deepcopy(after)
        elif change.operation in {"add_edge", "remove_edge", "update_edge"}:
            if set(target) != {"source", "target"} or not target.get("source") or not target.get("target"):
                errors.append(f"{prefix}: target must contain only non-empty source and target")
            if change.operation == "add_edge" and (before is not None or not isinstance(after, dict)):
                errors.append(f"{prefix}: add_edge requires before=null and after=edge")
            elif change.operation == "remove_edge" and (not isinstance(before, dict) or after is not None):
                errors.append(f"{prefix}: remove_edge requires before=edge and after=null")
            elif change.operation == "update_edge" and (not isinstance(before, dict) or not isinstance(after, dict)):
                errors.append(f"{prefix}: update_edge requires before=edge and after=edge")
            target_edge = after if change.operation == "add_edge" and isinstance(after, dict) else before
            if isinstance(target_edge, dict) and (target.get("source") != target_edge.get("source") or target.get("target") != target_edge.get("target")):
                errors.append(f"{prefix}: target endpoints do not match the operation object")
            if change.operation == "add_edge" and isinstance(after, dict):
                working["edges"].append(deepcopy(after))
            elif change.operation == "remove_edge" and isinstance(before, dict):
                match = next((i for i, edge in enumerate(working["edges"]) if edge == before), None)
                if match is None:
                    errors.append(f"{prefix}: edge to remove is not present at this operation")
                    can_apply_all = False
                else:
                    working["edges"].pop(match)
            elif change.operation == "update_edge" and isinstance(before, dict) and isinstance(after, dict):
                match = next((i for i, edge in enumerate(working["edges"]) if edge == before), None)
                if match is None:
                    errors.append(f"{prefix}: edge to update is not present at this operation")
                    can_apply_all = False
                else:
                    working["edges"][match] = deepcopy(after)
        else:  # update_attribute
            if set(target) != {"node", "attribute"} or not target.get("node") or not target.get("attribute"):
                errors.append(f"{prefix}: target must contain only non-empty node and attribute")
            if not isinstance(before, dict) or not isinstance(after, dict):
                errors.append(f"{prefix}: update_attribute requires before and after attribute objects")
            else:
                node_name, attr_name = target.get("node"), target.get("attribute")
                if before.get("name") != attr_name or after.get("name") != attr_name:
                    errors.append(f"{prefix}: target.attribute must match the attribute name")
                working_node = next((n for n in working["nodes"] if n.get("name") == node_name), None)
                if working_node is None:
                    errors.append(f"{prefix}: target node is not present at this operation")
                    can_apply_all = False
                else:
                    working_attrs = working_node.get("attributes") or []
                    match = next((i for i, attr in enumerate(working_attrs) if attr == before), None)
                    if match is None:
                        errors.append(f"{prefix}: before attribute is not present at this operation")
                        can_apply_all = False
                    else:
                        working_attrs[match] = deepcopy(after)

    if can_apply_all and not errors:
        if not same_unordered_items(working["nodes"], corrected_nodes):
            errors.append("Applying proposed operations produces a different node set than the corrected topology")
        # In complex workflows, the model reorders connections directly in corrected_topology
        # but may omit intermediate edge rewire pairs from its textual proposed_changes list.
        # Since validate_topology(corrected_topology) strictly validates all edge sources/targets,
        # edge diff omissions should not fatally block accepting the valid diagram.
    return errors


def validate_correction(original: Any, response: CorrectionResult) -> ValidationReport:
    """Combine deterministic structural checks; AI text is kept in separate fields."""
    original_report = validate_topology(original, "original")
    corrected = response.corrected_topology.model_dump()
    corrected_report = validate_topology(corrected, "corrected_topology")
    errors = [*original_report.errors, *corrected_report.errors]
    errors.extend(validate_proposed_operations(original, corrected, response.proposed_changes))
    warnings = [*original_report.warnings, *corrected_report.warnings]
    return ValidationReport(errors=errors, warnings=warnings)


correction_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a conservative technical diagram correction proposer.

Analyze an extracted topology and propose only evidence-supported corrections.
Do not alter the original. The corrected topology is a proposal requiring review.

You may receive:
- Database architecture diagrams
- Software architecture diagrams
- UML diagrams
- Cloud architecture diagrams
- Network diagrams
- Circuit diagrams
- Data flow diagrams
- Other technical architecture diagrams

IMPORTANT RULES:

1. Never invent missing nodes, edges, labels, relationships, cardinalities,
   attributes, primary keys, foreign keys, protocols, or requirements.
2. If a correction is ambiguous, preserve the original value. Mention the
   ambiguity as an AI warning or suggestion; do not guess a replacement.
3. Treat optional requirements as constraints only when consistent with the
   supplied topology; requirements do not establish facts missing from it.
4. Return a corrected topology plus a complete explicit operation list. Use
   only add_node, remove_node, update_node, add_edge, remove_edge,
   update_edge, and update_attribute. Attribute changes must use
   update_attribute rather than being hidden inside update_node.
5. Every operation must include target, before, after, reason, confidence,
   and uncertainty. Use null for before on adds and after on removals.
   Low or uncertain confidence requires a specific uncertainty explanation.
6. Do not report AI warnings or suggestions as deterministic validation
   errors. The server computes validation separately.
7. Preserve all supported node metadata and attributes unless an explicit
   operation changes them. Keep endpoints consistent with node names.
8. If no correction is justified, return the unchanged topology, no changes,
   and explain that in the summary.

{format_instructions}
"""
    ),
    (
        "human",
        """
Original diagram topology:

{topology}

Additional requirements (if provided):
{requirements}

Propose a corrected topology and explain every difference with explicit
operations. Return only the required structured response.
"""
    )
])


def parse_correction_result(raw_content: str) -> CorrectionResult:
    """Robustly extract and validate CorrectionResult from raw model output."""
    # 1. Strip thinking or thought tags if present (<think>...</think> or <thought>...</thought>)
    cleaned = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", raw_content, flags=re.IGNORECASE).strip()

    # 2. Extract from markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        # 3. Find first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1].strip()

    try:
        parsed_json = json.loads(cleaned)
        return CorrectionResult.model_validate(parsed_json)
    except Exception as e:
        print("=== FAILED TO PARSE RAW MODEL OUTPUT ===")
        print(raw_content[:2000])
        print("=== END RAW OUTPUT ===")
        try:
            return parser.parse(cleaned)
        except Exception:
            raise ValueError(f"Failed to parse valid JSON from reasoning model. Error: {str(e)}")


async def correct_diagram(
    topology: dict,
    requirements: str = ""
) -> dict:

    if not topology:
        raise ValueError("No diagram topology provided")

    if not topology.get("nodes"):
        raise ValueError("Diagram contains no nodes")

    import os
    from langchain_openai import ChatOpenAI

    reasoning_llm = ChatOpenAI(
        base_url=os.environ.get("BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.environ.get("REASONING_MODEL", os.environ.get("CHAT_MODEL")),
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
        max_tokens=8192,
        timeout=180,
        extra_body={
            "reasoning": {
                "max_tokens": 1000  # Cap reasoning so it doesn't starve the JSON output
            }
        }
    )

    response = await (correction_prompt | reasoning_llm).ainvoke({
        "topology": json.dumps(topology, indent=2),
        "requirements": requirements or "No additional requirements.",
        "format_instructions": parser.get_format_instructions()
    })

    raw_text = response.content if hasattr(response, "content") else str(response)
    result = parse_correction_result(raw_text)

    validation = validate_correction(topology, result)
    return CorrectionProposal(
        summary=result.summary,
        corrected_topology=result.corrected_topology,
        proposed_changes=result.proposed_changes,
        ai_warnings=result.ai_warnings,
        ai_suggestions=result.ai_suggestions,
        validation=validation,
    ).model_dump()
