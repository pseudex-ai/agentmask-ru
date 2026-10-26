"""The schema comparator must fail on executable changes, not metadata changes.

Extract only the actual pure comparator definitions to avoid importing the
customer's database driver into the host-side test environment. No duplicate
comparator implementation and no network/client data are involved.
"""

import ast
import copy
from pathlib import Path
import unittest

TREE = ast.parse((Path(__file__).with_name("catalog_gate.py")).read_text())
FUNCTIONS = [node for node in TREE.body if isinstance(node, ast.FunctionDef)
             and node.name in ("schema_structure", "structural")]
NAMESPACE = {}
exec(compile(ast.Module(body=FUNCTIONS, type_ignores=[]), "catalog_comparator", "exec"), NAMESPACE)
compare = NAMESPACE["structural"]


def fixture():
    return [{"type": "function", "function": {"name": "synthetic", "description": "before",
        "parameters": {"type": "object", "title": "schema heading", "properties": {
            "title": {"type": "string", "description": "field prose"},
            "record": {"type": "object", "default": {"title": "literal", "description": "literal"}},
            "kind": {"enum": [{"description": "literal enum"}]},
        }, "required": ["title"]}}}]


class ComparatorTests(unittest.TestCase):
    def test_prose_metadata_changes_are_allowed(self):
        before = fixture(); after = copy.deepcopy(before)
        after[0]["function"]["description"] = "after"
        after[0]["function"]["parameters"]["title"] = "after"
        after[0]["function"]["parameters"]["properties"]["title"]["description"] = "after"
        self.assertEqual(compare(before), compare(after))

    def test_argument_named_title_is_not_erased(self):
        before = fixture(); after = copy.deepcopy(before)
        after[0]["function"]["parameters"]["properties"]["title"]["type"] = "integer"
        self.assertNotEqual(compare(before), compare(after))

    def test_literal_default_metadata_names_are_executable_data(self):
        before = fixture(); after = copy.deepcopy(before)
        after[0]["function"]["parameters"]["properties"]["record"]["default"]["title"] = "changed"
        self.assertNotEqual(compare(before), compare(after))

    def test_literal_enum_is_not_schema_prose(self):
        before = fixture(); after = copy.deepcopy(before)
        after[0]["function"]["parameters"]["properties"]["kind"]["enum"][0]["description"] = "changed"
        self.assertNotEqual(compare(before), compare(after))

    def test_required_and_names_are_never_dropped(self):
        for mutation in ("required", "name"):
            before = fixture(); after = copy.deepcopy(before)
            if mutation == "name": after[0]["function"]["name"] = "changed"
            else: after[0]["function"]["parameters"]["required"] = []
            self.assertNotEqual(compare(before), compare(after))


if __name__ == "__main__":
    unittest.main()
