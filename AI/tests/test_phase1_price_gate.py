"""Provider calls are mocked; no feature is enabled on a running service."""
import json
import threading
import unittest
from unittest.mock import Mock, MagicMock, patch

from jewelry_agents.dialogue_state import ShoppingState
from jewelry_agents.dialogue_state_controller import prepare_semantic_refinement, prepare_refinement
from jewelry_agents.semantic_price_intent import infer_price_preference
from jewelry_agents.price_intent_router import resolve_price_preference
from jewelry_agents.retrieval import extract_price_filter
from jewelry_agents.semantic_planner import plan_query
from jewelry_agents.dialogue_plan import request_plan


class Phase1PriceGateTests(unittest.TestCase):
    def test_false_price_gate_blocks_all_price_paths_while_dst_is_enabled(self):
        state = ShoppingState(category='ring', max_price=5000000)
        with patch.dict('os.environ', {'LUMIERE_SEMANTIC_PRICE_ENABLED': 'false',
                                      'LUMIERE_SEMANTIC_DST_ENABLED': 'true'}), \
                patch('jewelry_agents.retrieval._model_warming', threading.Event()), \
                patch('jewelry_agents.dialogue_state_controller.semantic_entity_refinement', return_value=None), \
                patch('jewelry_agents.semantic_price_intent._GATE.call') as gate, \
                patch('jewelry_agents.semantic_price_intent._GATE.call_with_timeout') as timed_gate, \
                patch('jewelry_agents.semantic_price_intent.urllib.request.build_opener') as provider:
            for message in ('còn vòng đeo tay', 'chọn kiểu khác giúp mình', 'mình đang cân nhắc lại'):
                with self.subTest(message=message):
                    self.assertEqual(infer_price_preference(message), 'neutral')
                    self.assertEqual(resolve_price_preference(message, allow_semantic=True), 'neutral')
                    self.assertIsNone(prepare_semantic_refinement(message, state))
                    refinement = prepare_refinement(message, state, extract_price_filter)
                    if message == 'còn vòng đeo tay':
                        # Phase 3 adds an ontology alias; deterministic category
                        # refinement must still make zero price-provider calls.
                        self.assertEqual(refinement[0], ShoppingState(category='bracelet', max_price=5000000))
                    else:
                        self.assertIsNone(refinement)
                    self.assertEqual(state, ShoppingState(category='ring', max_price=5000000))
        gate.assert_not_called()
        timed_gate.assert_not_called()
        provider.assert_not_called()

    def test_minilm_refinement_is_independent_of_price_gate(self):
        state = ShoppingState(category='ring', max_price=5000000)
        updated = ShoppingState(category='bracelet', max_price=5000000)
        with patch.dict('os.environ', {'LUMIERE_SEMANTIC_PRICE_ENABLED': 'false',
                                      'LUMIERE_SEMANTIC_DST_ENABLED': 'true'}), \
                patch('jewelry_agents.dialogue_state_controller.semantic_entity_refinement', return_value=(updated, 'vòng tay')) as mini, \
                patch('jewelry_agents.dialogue_state_controller.infer_price_preference') as price:
            result = prepare_semantic_refinement('món ôm quanh cổ tay', state)
        self.assertEqual(result[0], updated)
        mini.assert_called_once()
        price.assert_not_called()

    def test_timeout_and_invalid_json_do_not_patch_state(self):
        state = ShoppingState(category='ring', material='silver', max_price=5000000)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{invalid'
        # True applies only to this isolated, fully mocked provider call.
        with patch.dict('os.environ', {'LUMIERE_SEMANTIC_PRICE_ENABLED': 'true',
                                      'LUMIERE_SEMANTIC_DST_ENABLED': 'true'}), \
                patch('jewelry_agents.retrieval._model_warming', threading.Event()), \
                patch('jewelry_agents.dialogue_state_controller.semantic_entity_refinement', return_value=None), \
                patch('jewelry_agents.semantic_price_intent.urllib.request.build_opener', return_value=opener):
            for behavior in (lambda timeout, fn: fn(), Mock(side_effect=TimeoutError)):
                with patch('jewelry_agents.semantic_price_intent._GATE.call_with_timeout', side_effect=behavior):
                    self.assertIsNone(prepare_semantic_refinement('mình đang cân nhắc lại', state))
                    self.assertEqual((state.category, state.material, state.max_price), ('ring', 'silver', 5000000))

    def test_planner_gates_are_separate_and_not_overridable(self):
        with patch.dict('os.environ', {'LUMIERE_SEMANTIC_PRICE_ENABLED': 'false',
                                      'LUMIERE_HYBRID_NLU_ENABLED': 'false',
                                      'LUMIERE_SEMANTIC_PLANNER_ENABLED': 'false'}), \
                patch('jewelry_agents.dialogue_plan.urllib.request.build_opener') as provider:
            self.assertIsNone(request_plan('Tìm trang sức', enabled=True))
            self.assertIsNone(plan_query('Tìm trang sức'))
        provider.assert_not_called()
        opener = MagicMock()
        wire = {'done': True, 'message': {'content': json.dumps({'i': 'knowledge', 'a': []})}}
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(wire).encode()
        with patch.dict('os.environ', {'LUMIERE_SEMANTIC_PRICE_ENABLED': 'false',
                                      'LUMIERE_HYBRID_NLU_ENABLED': 'true',
                                      'LUMIERE_SEMANTIC_PRICE_URL': 'http://ollama/api/chat'}), \
                patch('jewelry_agents.dialogue_plan.urllib.request.build_opener', return_value=opener), \
                patch('jewelry_agents.dialogue_plan._gate.call_with_timeout', side_effect=lambda timeout, fn: fn()):
            self.assertEqual(request_plan('Giải thích về trang sức').intent, 'knowledge')
        opener.open.assert_called_once()
