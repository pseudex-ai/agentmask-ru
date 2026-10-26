"""Qualification invariants: preserve input text; never strip missing inputs."""
import unittest
from qualify_september_replay import original_text, CUTOFF_MS


class QualificationTests(unittest.TestCase):
    def test_exact_string_retained_including_unicode_and_whitespace(self):
        text = '😀  РОП\n\t literal 1994  '
        self.assertEqual(original_text({'content': text}), text)

    def test_mongo_text_envelope_is_lossless(self):
        text = 'text\n' * 100000
        self.assertEqual(original_text({'content': {'text': text, 'type': 'text',
                                                   'format': 'markdown', 'language': 'ru'}}), text)

    def test_attachment_envelope_is_not_silently_reduced_to_text(self):
        with self.assertRaisesRegex(ValueError, 'unarchived_user_content_fields'):
            original_text({'content': {'text': 'message', 'attachments': [{'file_id': 'synthetic'}]}})

    def test_multimodal_input_is_not_stripped(self):
        with self.assertRaisesRegex(ValueError, 'unsupported_original_input'):
            original_text({'content': [{'type': 'text', 'text': 'message'},
                                      {'type': 'image_url', 'image_url': {'url': 'data:synthetic'}}]})

    def test_cutoff_is_september_not_an_inferred_lookback_window(self):
        from datetime import datetime, timezone
        self.assertEqual(CUTOFF_MS, int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()*1000))


if __name__ == '__main__':
    unittest.main()
