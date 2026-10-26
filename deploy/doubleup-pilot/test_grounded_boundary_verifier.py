"""A Unicode escape is not privacy: the verifier must inspect decoded JSON."""
import json
import unittest
from verify_grounded_pii_control import strings


class BoundaryVerifierTests(unittest.TestCase):
    def test_unicode_escaped_tool_output_is_not_mistaken_for_masking(self):
        value='Иван Петров'
        wire={'messages':[{'role':'tool','content':json.dumps({'result':{'stdout':value}},ensure_ascii=True)}]}
        self.assertNotIn(value,wire['messages'][0]['content'])
        self.assertIn(value,'\n'.join(strings(wire)))

    def test_actual_substitute_is_distinct_from_encoded_original(self):
        wire={'messages':[{'role':'tool','content':json.dumps({'result':{'stdout':'synthetic-substitute'}},ensure_ascii=True)}]}
        self.assertNotIn('Иван Петров','\n'.join(strings(wire)))

    def test_nested_json_strings_are_inspected_without_an_eval(self):
        wire={'content':json.dumps({'inner':json.dumps({'stdout':'ivan@example.invalid'})})}
        self.assertIn('ivan@example.invalid','\n'.join(strings(wire)))

    def test_malformed_tool_json_remains_visible_to_literal_checks(self):
        value='ivan@example.invalid'
        self.assertIn(value,'\n'.join(strings({'content':'{"broken":'+value})))


if __name__=='__main__':unittest.main()
