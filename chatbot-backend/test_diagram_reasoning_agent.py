import unittest

from pydantic import ValidationError

from diagram_reasoning_agent import (
    CorrectionResult,
    ProposedChange,
    validate_correction,
)


def node(name="A", node_type="entity", attributes=None):
    normalized_attributes = []
    for attribute in attributes or []:
        normalized_attributes.append({
            "data_type": "varchar",
            "is_key": "none",
            **attribute,
        })
    return {
        "name": name,
        "type": node_type,
        "metadata": {},
        "attributes": normalized_attributes,
        "source": "visible_text",
        "confidence": "high",
    }


def edge(source="A", target="B", relationship="connects", cardinality=None):
    return {
        "source": source,
        "target": target,
        "relationship": relationship,
        "cardinality_or_type": cardinality,
    }


def correction(original, corrected=None, changes=None, **extra):
    return CorrectionResult.model_validate({
        "summary": "Reviewable proposal",
        "corrected_topology": corrected or original,
        "proposed_changes": changes or [],
        **extra,
    })


class TopologyValidationTests(unittest.TestCase):
    def test_valid_nodes_edges_and_keys_have_no_errors(self):
        topology = {
            "nodes": [
                node("A", attributes=[{"name": "id", "data_type": "int", "is_key": "PK"}]),
                node("B", attributes=[{"name": "a_id", "data_type": "int", "is_key": "FK"}]),
            ],
            "edges": [edge("B", "A", "references", "many-to-one")],
        }

        report = validate_correction(topology, correction(topology))

        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_unchanged_topology_needs_no_operations(self):
        topology = {"nodes": [node("A")], "edges": []}

        report = validate_correction(topology, correction(topology))

        self.assertEqual(report.errors, [])
        self.assertEqual(correction(topology).proposed_changes, [])

    def test_duplicate_nodes_dangling_edge_bad_key_and_empty_relationship_are_errors(self):
        topology = {
            "nodes": [node("A"), node("A"), node("B", attributes=[{"name": "id", "is_key": "PRIMARY"}])],
            "edges": [edge("A", "missing", "  ")],
        }

        report = validate_correction(topology, correction(topology))

        self.assertTrue(any("duplicate node" in error for error in report.errors))
        self.assertTrue(any("does not name a node" in error for error in report.errors))
        self.assertTrue(any("non-empty relationship" in error for error in report.errors))
        self.assertTrue(any("is_key must be" in error for error in report.errors))

    def test_semantic_uncertainty_is_a_warning_not_an_error(self):
        topology = {
            "nodes": [node("R1", "component", [{"name": "id", "is_key": "PK"}]), node("R2")],
            "edges": [edge("R1", "R2", "connected", "unfamiliar-domain-term")],
        }

        report = validate_correction(topology, correction(topology))

        self.assertEqual(report.errors, [])
        self.assertTrue(any("key attribute" in warning for warning in report.warnings))

    def test_missing_operations_for_changed_topology_is_an_error(self):
        original = {"nodes": [node("A"), node("B")], "edges": []}
        corrected = {"nodes": original["nodes"], "edges": [edge()]}

        report = validate_correction(original, correction(original, corrected))

        self.assertIn("A changed topology must have at least one proposed operation", report.errors)

    def test_operation_before_and_after_must_match_the_snapshots(self):
        original = {"nodes": [node("A"), node("B")], "edges": []}
        corrected = {"nodes": original["nodes"], "edges": [edge()]}
        change = ProposedChange(
            operation="add_edge",
            target={"source": "A", "target": "B"},
            before=None,
            after=edge("A", "B", "invented relationship"),
            reason="Test mismatch",
            confidence="medium",
            uncertainty="The edge label differs from the corrected snapshot.",
        )

        report = validate_correction(original, correction(original, corrected, [change]))

        self.assertTrue(any("does not produce the corrected topology" in error for error in report.errors))

    def test_add_node_operation_reconstructs_the_corrected_topology(self):
        original = {"nodes": [node("A")], "edges": []}
        added = node("B")
        corrected = {"nodes": [node("A"), added], "edges": []}
        change = ProposedChange(
            operation="add_node",
            target={"node": "B"},
            before=None,
            after=added,
            reason="The supplied requirements explicitly identify this node.",
            confidence="high",
        )

        report = validate_correction(original, correction(original, corrected, [change]))

        self.assertEqual(report.errors, [])

    def test_update_attribute_operation_reconstructs_the_corrected_topology(self):
        old_attr = {"name": "id", "data_type": "int", "is_key": "none"}
        new_attr = {"name": "id", "data_type": "int", "is_key": "PK"}
        original = {"nodes": [node("A", attributes=[old_attr])], "edges": []}
        corrected = {"nodes": [node("A", attributes=[new_attr])], "edges": []}
        change = ProposedChange(
            operation="update_attribute",
            target={"node": "A", "attribute": "id"},
            before=old_attr,
            after=new_attr,
            reason="The input topology marks this attribute as the primary key.",
            confidence="high",
        )

        report = validate_correction(original, correction(original, corrected, [change]))

        self.assertEqual(report.errors, [])

    def test_all_seven_operations_reconstruct_corrected_topology(self):
        old_attribute = {"name": "id", "data_type": "int", "is_key": "none"}
        new_attribute = {"name": "id", "data_type": "int", "is_key": "FK"}
        old_a = node("A")
        old_b = node("B", attributes=[old_attribute])
        updated_b = {**old_b, "metadata": {"reviewed": True}}
        new_c = node("C")
        old_edge = edge("A", "B", "connects", "one-to-one")
        new_edge = edge("B", "C", "feeds", "one-to-many")
        original = {"nodes": [old_a, old_b], "edges": [old_edge]}
        corrected = {
            "nodes": [{**updated_b, "attributes": [new_attribute]}, new_c],
            "edges": [new_edge],
        }
        changes = [
            ProposedChange(
                operation="remove_edge", target={"source": "A", "target": "B"},
                before=old_edge, after=None, reason="Remove the superseded edge.", confidence="high",
            ),
            ProposedChange(
                operation="remove_node", target={"node": "A"},
                before=old_a, after=None, reason="Remove the unsupported node.", confidence="high",
            ),
            ProposedChange(
                operation="update_node", target={"node": "B"},
                before=old_b, after=updated_b, reason="Update supported node metadata.", confidence="high",
            ),
            ProposedChange(
                operation="update_attribute", target={"node": "B", "attribute": "id"},
                before=old_attribute, after=new_attribute,
                reason="Apply the specified foreign-key designation.", confidence="high",
            ),
            ProposedChange(
                operation="add_node", target={"node": "C"},
                before=None, after=new_c, reason="Add the specified node.", confidence="high",
            ),
            ProposedChange(
                operation="add_edge", target={"source": "B", "target": "C"},
                before=None, after=new_edge, reason="Add the specified connection.", confidence="high",
            ),
        ]
        # update_edge is covered separately by validating an edge replacement.
        replacement_edge = edge("A", "B", "references", "many-to-one")
        update_topology = {"nodes": [old_a, old_b], "edges": [replacement_edge]}
        changes.append(ProposedChange(
            operation="update_edge", target={"source": "A", "target": "B"},
            before=old_edge, after=replacement_edge,
            reason="Correct the explicitly identified relationship.", confidence="high",
        ))
        # Include both edge changes in the final snapshot so applying all operations is exact.
        original["edges"] = [old_edge]
        corrected["edges"] = [new_edge]
        # This change sequence removes old_edge before update_edge, so validate the
        # update operation independently against its own original/corrected snapshots.
        update_report = validate_correction(
            {"nodes": [old_a, old_b], "edges": [old_edge]},
            correction(
                {"nodes": [old_a, old_b], "edges": [old_edge]},
                update_topology,
                [changes[-1]],
            ),
        )
        combined_report = validate_correction(original, correction(original, corrected, changes[:-1]))

        self.assertEqual(update_report.errors, [])
        self.assertEqual(combined_report.errors, [])

    def test_invalid_operation_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            ProposedChange(
                operation="replace_diagram",
                target={"node": "A"},
                before=None,
                after=None,
                reason="Not a supported operation.",
                confidence="high",
            )

    def test_ambiguous_change_carries_uncertain_confidence_and_explanation(self):
        change = ProposedChange(
            operation="add_node",
            target={"node": "C"},
            before=None,
            after=node("C"),
            reason="The label may refer to a separate component.",
            confidence="uncertain",
            uncertainty="The extracted diagram does not show whether the label is a node or annotation.",
        )

        self.assertEqual(change.confidence, "uncertain")
        self.assertTrue(change.uncertainty)

    def test_validation_does_not_mutate_original_topology(self):
        original = {"nodes": [node("A"), node("B")], "edges": []}
        before_validation = {
            "nodes": [dict(n, attributes=list(n["attributes"])) for n in original["nodes"]],
            "edges": list(original["edges"]),
        }
        added = edge("A", "B")
        corrected = {"nodes": original["nodes"], "edges": [added]}
        change = ProposedChange(
            operation="add_edge", target={"source": "A", "target": "B"},
            before=None, after=added, reason="Add a supported edge.", confidence="high",
        )

        validate_correction(original, correction(original, corrected, [change]))

        self.assertEqual(original, before_validation)

    def test_all_required_operations_are_explicitly_supported(self):
        expected = {
            "add_node", "remove_node", "update_node", "add_edge",
            "remove_edge", "update_edge", "update_attribute",
        }

        self.assertEqual(set(ProposedChange.model_fields["operation"].annotation.__args__), expected)

    def test_low_or_uncertain_confidence_requires_uncertainty_text(self):
        with self.assertRaises(ValidationError):
            ProposedChange(
                operation="add_node",
                target={"node": "C"},
                before=None,
                after=node("C"),
                reason="Potentially missing node",
                confidence="uncertain",
            )

    def test_ai_warnings_and_suggestions_remain_separate_from_validation(self):
        topology = {"nodes": [node("A")], "edges": []}
        result = correction(
            topology,
            ai_warnings=["Image evidence is unavailable."],
            ai_suggestions=["Check the source image."],
        )

        report = validate_correction(topology, result)

        self.assertEqual(result.ai_warnings, ["Image evidence is unavailable."])
        self.assertEqual(result.ai_suggestions, ["Check the source image."])
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])


if __name__ == "__main__":
    unittest.main()
