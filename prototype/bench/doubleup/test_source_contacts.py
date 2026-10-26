"""Qualification is narrow source evidence, not a permissive PII score."""

import unittest
from .qualify_dialogues import evidence


class ContactEvidenceTests(unittest.TestCase):
    def test_reserved_examples_are_not_real_contact_selection(self):
        self.assertEqual(evidence('a@example.org b@x.invalid c@demo.test', '/text'), [])

    def test_nonreserved_email_and_valid_phone_have_exact_codepoint_ranges(self):
        source='😀 Контакт fixture.person@company.fixture +7 916 123-45-67'
        values=evidence(source,'/text')
        self.assertEqual({v['type'] for v in values},{'email_contact','phone_contact'})
        for item in values:
            self.assertEqual(source[item['start']:item['end']],item['value'])
            self.assertEqual(item['pointer'],'/text')

    def test_invalid_phone_and_opaque_ids_do_not_qualify(self):
        self.assertEqual(evidence('ID abcdefab-12a3-4def-abcd-abcdefabcdef; +7 000 000-00-00; 12345','/text'),[])

    def test_binary_media_remains_not_contact_text(self):
        self.assertEqual(evidence('data:image/png;base64,abc+79161234567xyz','/image_url'),[])

    def test_phone_variants_match_by_identity_without_changing_original(self):
        first=evidence('+7 (916) 123-45-67','/a')[0]
        second=evidence('8 916 123 45 67','/b')[0]
        self.assertEqual(first['canonical'],second['canonical'])
        self.assertNotEqual(first['value'],second['value'])

    def test_nested_source_pointer_is_explicit(self):
        found=evidence({'a/b~c':['fixture@company.fixture']},'/input')
        self.assertEqual(found[0]['pointer'],'/input/a~1b~0c/0')


if __name__=='__main__':unittest.main()
