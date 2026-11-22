import json
import unittest
from unittest.mock import MagicMock,patch
from shared.local_dialogue import answer_general


class LocalDialogueTests(unittest.TestCase):
    def test_disabled_and_cloud_urls_do_not_send_any_request(self):
        with patch('urllib.request.build_opener') as opener:
            with patch.dict('os.environ',{'LUMIERE_DIALOGUE_LLM_ENABLED':'false'}):
                self.assertIsNone(answer_general('question'))
            with patch.dict('os.environ',{'LUMIERE_DIALOGUE_LLM_ENABLED':'true',
                                        'LUMIERE_DIALOGUE_URL':'https://example.com/api/chat'}):
                self.assertIsNone(answer_general('question'))
            opener.assert_not_called()

    def test_local_model_receives_bounded_history_and_server_role(self):
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=json.dumps(
            {'message':{'content':'Natural answer'}}).encode()
        with patch.dict('os.environ',{'LUMIERE_DIALOGUE_LLM_ENABLED':'true',
                                     'LUMIERE_DIALOGUE_URL':'http://ollama:11434/api/chat'}), \
             patch('urllib.request.build_opener',return_value=opener), \
             patch('shared.local_dialogue._gate.call',side_effect=lambda fn:fn()):
            result=answer_general('Tại sao?', [{'user':'question','answer':'prior answer'}]*8,'staff')
        self.assertEqual(result,'Natural answer')
        request=opener.open.call_args.args[0]
        payload=json.loads(request.data)
        self.assertEqual(len(payload['messages']),8)
        self.assertIn('staff',payload['messages'][0]['content'])
        self.assertEqual(payload['keep_alive'],'0')
        self.assertFalse(payload['stream'])

    def test_bad_model_output_fails_without_exposing_raw_error(self):
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=b'{"message":{"content":12}}'
        with patch.dict('os.environ',{'LUMIERE_DIALOGUE_LLM_ENABLED':'true',
                                     'LUMIERE_DIALOGUE_URL':'http://ollama:11434/api/chat'}), \
             patch('urllib.request.build_opener',return_value=opener), \
             patch('shared.local_dialogue._gate.call',side_effect=lambda fn:fn()):
            self.assertIsNone(answer_general('question'))
