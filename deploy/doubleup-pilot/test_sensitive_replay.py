"""Safe source provenance rebasing without touching business document strings."""

import copy
import unittest

from prepare_sensitive_replay import rebase_refs
from bench.doubleup import source_resources


class SensitiveReplayTests(unittest.TestCase):
    def test_exact_archive_reference_moves_to_real_private_dialogue_root(self):
        source={'run':source_resources.SOURCE_RUN,'artifact':'full-dialogues.aesgcm',
            'pointer':'/dialogues/7/source_context/application_activity/source_tool_execution_spans/2'}
        original=copy.deepcopy(source)
        result=rebase_refs({'provenance':source,'body':'/dialogues/7 must stay literal'},'synthetic-source-run',7)
        self.assertEqual(result['provenance']['run'],'synthetic-source-run')
        self.assertEqual(result['provenance']['artifact'],'complete-sensitive-dialogue.aesgcm')
        self.assertEqual(result['provenance']['pointer'],'/dialogue/source_context/application_activity/source_tool_execution_spans/2')
        self.assertEqual(result['body'],'/dialogues/7 must stay literal')
        self.assertEqual(source,original)

    def test_another_run_or_neighbouring_index_is_not_relabelled(self):
        source=[{'run':'other-run','artifact':'full-dialogues.aesgcm','pointer':'/dialogues/7/messages'},
            {'run':source_resources.SOURCE_RUN,'artifact':'full-dialogues.aesgcm','pointer':'/dialogues/70/messages'}]
        self.assertEqual(rebase_refs(source,'synthetic-run',7),source)


if __name__=='__main__':unittest.main()
