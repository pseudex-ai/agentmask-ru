"""Zero-network relay proof: aligned deadlines, classified failure, no refund/retry."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi import HTTPException
import gateway


class RelayTransportTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, error=None):
        received={};ledger=Mock();ledger.reserve.return_value='synthetic-budget-id'
        class Client:
            def __init__(self, **kwargs):received.update(kwargs)
            async def __aenter__(self):return self
            async def __aexit__(self,*_args):return False
            async def post(self,url,**kwargs):
                received['url']=url;received['body']=kwargs['json']
                if error:raise error
                return httpx.Response(200,json={'choices':[],'usage':{'prompt_tokens':2,'completion_tokens':1}})
        request=SimpleNamespace(headers={'authorization':'Bearer '+'k'*24})
        body={'model':'deepseek-v4-flash','messages':[{'role':'user','content':'Synthetic fixture'}]}
        with patch.object(gateway,'_live_config',return_value={'model':'deepseek-v4-flash','request_key':'k'*24,'upstream_key':'s'*24}), \
             patch.object(gateway,'load_pricing',return_value={}),patch.object(gateway,'quote',return_value={'reserved_nano':1}), \
             patch.object(gateway,'Ledger',return_value=ledger),patch.object(gateway.httpx,'AsyncClient',Client),patch('builtins.print') as logged:
            try:result=await gateway._live(request,body)
            except HTTPException as exc:result=exc
        return result,ledger,received,logged

    async def test_long_buffered_reply_has_bounded_read_timeout_and_fixed_route(self):
        result,ledger,received,_logged=await self.exercise()
        self.assertEqual(result.status_code,200)
        self.assertEqual(received['timeout'].read,300)
        self.assertEqual(received['timeout'].connect,10)
        self.assertFalse(received['follow_redirects']);self.assertFalse(received['trust_env'])
        self.assertEqual(received['url'],'https://litellm.inf.2up.dev/v1/chat/completions')
        self.assertTrue(received['body']['no-log'])
        ledger.reserve.assert_called_once();ledger.settle.assert_called_once();ledger.unknown.assert_not_called()

    async def test_read_timeout_is_classified_and_unknown_reserve_is_retained(self):
        result,ledger,_received,logged=await self.exercise(httpx.ReadTimeout('SYNTHETIC_PRIVATE_TEXT_MUST_NOT_LEAK'))
        self.assertEqual(result.status_code,502)
        self.assertEqual(result.headers['X-Pilot-Transport-Error'],'ReadTimeout')
        self.assertEqual(result.headers['Cache-Control'],'no-store')
        ledger.reserve.assert_called_once();ledger.unknown.assert_called_once_with('synthetic-budget-id');ledger.settle.assert_not_called()
        self.assertNotIn('SYNTHETIC_PRIVATE_TEXT',str(logged.call_args))
        self.assertNotIn('SYNTHETIC_PRIVATE_TEXT',result.detail)

    async def test_connection_failure_remains_distinct_and_is_not_automatically_retried(self):
        result,ledger,_received,_logged=await self.exercise(httpx.ConnectError('synthetic'))
        self.assertEqual(result.headers['X-Pilot-Transport-Error'],'ConnectError')
        ledger.reserve.assert_called_once();ledger.unknown.assert_called_once()

    def test_bridge_deadline_is_above_the_relay_read_deadline(self):
        tree=ast.parse((Path(__file__).parent/'dialogue_bridge.py').read_text())
        values=[keyword.value.value for node in ast.walk(tree) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute) and node.func.attr=='update'
            for keyword in node.keywords if keyword.arg=='timeout' and isinstance(keyword.value,ast.Constant)]
        self.assertIn(360,values)
        self.assertGreater(360,300)


if __name__=='__main__':unittest.main()
