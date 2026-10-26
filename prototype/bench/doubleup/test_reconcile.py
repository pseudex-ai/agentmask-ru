"""An intake instrument must reject false dialog independence before a live run."""

import unittest

from .corpus import dialog_split_proof, identified_dialog, normalize_group, unique_tool_coverage
from .storage import PilotError


def trace(identifier, dialog, tenant):
    metadata = {"org_id": tenant} if tenant else {}
    if dialog:
        metadata["billing_dialog_id"] = dialog
    return {"id": identifier, "metadata": metadata}


def group(identifier, dialog, tenant, split):
    value = normalize_group(identifier, [trace(identifier, dialog, tenant)])
    value["split"] = split
    return value


class IdentityTests(unittest.TestCase):
    def test_same_dialog_cannot_cross_split(self):
        groups = [group("trace-a", "dialog-a", "org-a", "train"),
                  group("trace-b", "dialog-a", "org-a", "holdout")]
        with self.assertRaisesRegex(PilotError, "dialog_identity_cross_split"):
            dialog_split_proof(groups)

    def test_same_dialog_cannot_masquerade_as_two_train_cases(self):
        groups = [group("trace-a", "dialog-a", "org-a", "train"),
                  group("trace-b", "dialog-a", "org-a", "train")]
        with self.assertRaisesRegex(PilotError, "same_dialog_in_multiple_groups"):
            dialog_split_proof(groups)

    def test_missing_identity_is_quarantined_not_inferred_from_user(self):
        value = trace("trace-a", None, None)
        value["userId"] = "org-a"
        value["sessionId"] = "shared-session"
        self.assertIsNone(identified_dialog(value))
        unknown = group("trace-a", None, None, "holdout")
        with self.assertRaisesRegex(PilotError, "unidentified_dialog_in_comparative_split"):
            dialog_split_proof([unknown])
        unknown["split"] = "unscoped"
        proof = dialog_split_proof([unknown])
        self.assertEqual(proof["quarantined_unscoped_groups"], 1)
        self.assertEqual(proof["confirmed_dialog_groups"], 0)
        self.assertFalse(proof["whole_history_proven"])

    def test_session_and_dialog_namespaces_are_tenant_bound(self):
        left = {**trace("left", None, "org-a"), "sessionId": "same-session"}
        right = {**trace("right", None, "org-b"), "sessionId": "same-session"}
        self.assertNotEqual(identified_dialog(left), identified_dialog(right))
        self.assertNotEqual(identified_dialog(trace("x", "same-dialog", "org-a")),
                            identified_dialog(trace("y", "same-dialog", "org-b")))

    def test_duplicate_schema_occurrences_are_not_unique_tools(self):
        schema = {"type": "function", "function": {"name": "synthetic_tool", "parameters": {
            "type": "object", "properties": {"text": {"type": "string"}}}}}
        groups = []
        for identifier in ("a", "b"):
            item = trace(identifier, identifier, "org-a")
            item["input"] = {"tools": [schema]}
            groups.append(normalize_group(identifier, [item]))
        coverage = unique_tool_coverage(groups)
        self.assertEqual(coverage["schema_occurrences"], 2)
        self.assertEqual(coverage["distinct_schema_names"], 1)
        self.assertEqual(coverage["distinct_schema_variants"], 1)


if __name__ == "__main__":
    unittest.main()
