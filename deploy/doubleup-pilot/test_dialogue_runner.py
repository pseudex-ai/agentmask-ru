"""Recovery may reuse known state, never silently replay prior tool effects."""

from pathlib import Path
import tempfile
import unittest
import json
import sys
import threading
from unittest.mock import patch, Mock
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import dialogue_runner as runner

from dialogue_runner import canonical, known_prefix, scope_for, seal, unseal

KEY = bytes(range(32))
PREFIX = 'a' * 64 + '-builtin'


class RecoveryTests(unittest.TestCase):
    def tearDown(self):
        runner.CANCELLED.clear()

    def fixture(self, folder):
        state = {'history': [{'role': 'user', 'content': 'Synthetic 😀'}],
            'workspace': {'result.txt': 'NQ=='}, 'mirror_state': {'memories': []},
            'counts': {'models': 3, 'tools': 2, 'turns': 1}}
        seal(folder / f'{PREFIX}:0.complete.aesgcm', state, KEY, f'{PREFIX}:0:complete')
        seal(folder / f'{PREFIX}:1-1.started.aesgcm', {'request_sha256': 'b' * 64}, KEY, f'{PREFIX}:1:1:start')
        seal(folder / f'{PREFIX}:1-1.done.aesgcm', {'http_status': 502}, KEY, f'{PREFIX}:1:1:done')
        return state

    def test_known_prefix_roundtrip_preserves_state_and_unknown_without_repay(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder = Path(root).resolve(); self.assertTrue(folder.name.startswith('obscura-recovery-'))
            expected = self.fixture(folder)
            state, turn, request = known_prefix(folder, PREFIX, KEY, 3)
            self.assertEqual(state, expected); self.assertEqual(turn, 1); self.assertEqual(request, 'b' * 64)
            self.assertEqual(len(list(folder.iterdir())), 3)

    def test_partial_tool_effect_requires_manual_reconciliation(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder = Path(root).resolve(); self.assertTrue(folder.name.startswith('obscura-recovery-'))
            self.fixture(folder)
            seal(folder / f'{PREFIX}:1-tool-3.aesgcm', {'synthetic': True}, KEY, 'fixture')
            with self.assertRaisesRegex(RuntimeError, 'effects_or_multiple'):
                known_prefix(folder, PREFIX, KEY, 3)

    def test_unknown_without_received_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder = Path(root).resolve(); self.assertTrue(folder.name.startswith('obscura-recovery-'))
            seal(folder / f'{PREFIX}:0.complete.aesgcm', {'turns': 1}, KEY, f'{PREFIX}:0:complete')
            seal(folder / f'{PREFIX}:1-1.started.aesgcm', {'request_sha256': 'b' * 64}, KEY, f'{PREFIX}:1:1:start')
            with self.assertRaisesRegex(RuntimeError, 'not_yet_reconciled'):
                known_prefix(folder, PREFIX, KEY, 3)

    def test_independent_modes_continue_without_repaying_stopped_mode(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder = Path(root).resolve(); self.assertTrue(folder.name.startswith('obscura-recovery-'))
            runtime = folder / 'runtime'; runtime.mkdir()
            packet = {'run_id': 'synthetic-run', 'cases': [{'source_index': 3, 'case_id': 'a' * 64}]}
            nonce = bytes(range(12)); (runtime / 'full-dialogue-cases.key').write_bytes(KEY)
            (runtime / 'full-dialogue-cases.aesgcm').write_bytes(nonce + AESGCM(KEY).encrypt(nonce, canonical(packet), runner.AAD))
            client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
            client.get.return_value.json.return_value = {'mode': 'fixture'}
            called = []
            def arm(_packet, _case, mode, *_args):
                called.append(mode)
                if mode == 'builtin': raise RuntimeError('synthetic_stopped_arm')
                return {'mode': mode, 'status': 'complete'}
            with patch.object(runner, 'STATE', folder), patch.object(runner.httpx, 'Client', return_value=client), \
                 patch.object(runner, 'run_arm', side_effect=arm), patch.object(sys, 'argv', ['runner', '--mode', 'builtin', '--mode', 'pseudex', '--continue-other-arms']):
                runner.main()
            self.assertEqual(called, ['builtin', 'pseudex'])
            self.assertEqual(len(list((folder / 'synthetic-run-dry-v1').glob('*.stopped-*.aesgcm'))), 1)

    def test_cases_run_in_parallel_but_each_cases_modes_stay_sequential(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder=Path(root).resolve();self.assertTrue(folder.name.startswith('obscura-recovery-'))
            runtime=folder/'runtime';runtime.mkdir()
            cases=[{'source_index':index,'case_id':str(index+1)*64} for index in range(2)]
            packet={'run_id':'synthetic-parallel','cases':cases};nonce=bytes(range(12))
            (runtime/'full-dialogue-cases.key').write_bytes(KEY)
            (runtime/'full-dialogue-cases.aesgcm').write_bytes(nonce+AESGCM(KEY).encrypt(nonce,canonical(packet),runner.AAD))
            client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False)
            client.get.return_value.json.return_value={'mode':'fixture'}
            barrier=threading.Barrier(2);order={0:[],1:[]};lock=threading.Lock()
            def arm(_packet,case,mode,*_args):
                with lock:order[case['source_index']].append(mode)
                if mode=='none':barrier.wait(timeout=2)
                return {'mode':mode,'status':'complete'}
            with patch.object(runner,'STATE',folder),patch.object(runner.httpx,'Client',return_value=client), \
                 patch.object(runner,'run_arm',side_effect=arm),patch.object(sys,'argv',['runner','--parallel-cases','2']):
                runner.main()
            self.assertEqual(order,{0:['none','builtin','pseudex'],1:['none','builtin','pseudex']})

    def test_failed_turn_saves_original_error_and_explicit_system_notice_not_a_model_answer(self):
        with tempfile.TemporaryDirectory(prefix='obscura-recovery-') as root:
            folder=Path(root).resolve();self.assertTrue(folder.name.startswith('obscura-recovery-'))
            case={'case_id':'d'*64,'source_index':0,'source_user_turns':[{'content':'Synthetic original input'}],
                'system_messages':[{'content':'Synthetic system'}],'contracts':{},'resources':{},'max_tokens':1}
            saved=[];actual={'ok':False,'messages':[{'role':'assistant','content':'Synthetic actual host error'}]}
            def bridge(command,handle=None):
                if command['kind']=='turn':raise runner.BridgeFailure(actual)
                if command['kind']=='save':saved.append(command['messages'])
                return {'ok':True}
            with patch.object(runner,'bridge',side_effect=bridge):
                with self.assertRaises(runner.BridgeFailure):runner.run_arm({},case,'none',False,KEY,folder,False)
                with self.assertRaisesRegex(RuntimeError,'not_automatically_repaid'):runner.run_arm({},case,'none',False,KEY,folder,False)
            failed=unseal(folder/(case['case_id']+'-none:0.failed.aesgcm'),KEY,case['case_id']+'-none:0:failed')
            self.assertEqual(failed['actual_bridge_payload'],actual)
            self.assertEqual(saved[0][0]['content'],'Synthetic original input')
            self.assertTrue(saved[-1][-1]['additional_kwargs']['pilot_system_error'])
            self.assertIn('не ответ модели',saved[-1][-1]['content'])
            self.assertFalse((folder/(case['case_id']+'-none.complete.aesgcm')).exists())

    def test_binary_surrogate_output_and_scope_isolation(self):
        data = canonical({'synthetic': '\udcff 😀'})
        self.assertIn(b'\\udcff', data)
        case = {'case_id': 'c' * 64}
        one = scope_for(case, 'none', 'live-v1'); other = scope_for(case, 'pseudex', 'live-v1')
        self.assertEqual(one['tenant_id'], other['tenant_id']); self.assertNotEqual(one['thread_id'], other['thread_id'])
        self.assertNotEqual(one['tenant_id'], scope_for(case, 'none', 'dry-v1')['tenant_id'])


if __name__ == '__main__': unittest.main()
