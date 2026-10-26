"""No inference in these tests: engine pin, mode scope, finally-disable."""

import sys
import unittest
from unittest.mock import patch

import run_dialogue_live as wrapper

IMAGE='sha256:45dc6170bf493ef5bf3a9eb78a2213bb69aad26460554ce6a41514fbd60c5c98'


class LiveWrapperTests(unittest.TestCase):
    def test_wrong_engine_cannot_enable_paid_egress(self):
        with patch.object(sys,'argv',['wrapper']),patch.object(wrapper.subprocess,'check_output',return_value='sha256:wrong\n'), \
             patch.object(wrapper,'live_mode') as mode,patch.object(wrapper.dialogue_runner,'main') as execute:
            with self.assertRaisesRegex(RuntimeError,'approved_engine_image_not_running'):wrapper.main()
        self.assertEqual([call.args for call in mode.call_args_list],[(False,)])
        execute.assert_not_called()

    def test_dead_upstream_never_starts_any_case_and_always_closes_egress(self):
        with patch.object(sys,'argv',['wrapper']),patch.object(wrapper.subprocess,'check_output',return_value=IMAGE+'\n'), \
             patch.object(wrapper,'live_mode') as mode,patch.object(wrapper,'require_upstream_ready',side_effect=RuntimeError('upstream_preflight_failed_no_model_request')), \
             patch.object(wrapper.dialogue_runner,'main') as execute:
            with self.assertRaisesRegex(RuntimeError,'preflight_failed'):wrapper.main()
        self.assertEqual([call.args for call in mode.call_args_list],[(True,),(False,)])
        execute.assert_not_called()

    def test_explicit_bundle_and_modes_reach_runner_and_close_on_failure(self):
        seen=[]
        def fail():
            seen.extend(sys.argv)
            raise RuntimeError('synthetic')
        with patch.object(sys,'argv',['wrapper','--bundle','sensitive-corpus-cases-v1','--case-index','29','--mode','builtin','--mode','pseudex','--continue-other-arms']), \
             patch.object(wrapper.subprocess,'check_output',return_value=IMAGE+'\n'),patch.object(wrapper,'live_mode') as mode, \
             patch.object(wrapper,'require_upstream_ready',return_value={'transport_ok':True}), \
             patch.object(wrapper.dialogue_runner,'main',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'synthetic'):wrapper.main()
        self.assertEqual([call.args for call in mode.call_args_list],[(True,),(False,)])
        self.assertIn('sensitive-corpus-cases-v1',seen)
        self.assertEqual([seen[i+1] for i,x in enumerate(seen) if x=='--mode'],['builtin','pseudex'])
        self.assertIn('--continue-other-arms',seen)


if __name__=='__main__':unittest.main()
