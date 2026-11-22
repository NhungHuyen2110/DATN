import unittest
from unittest.mock import patch
from rag.rag_service import answer_jewelry_question
from jewelry_agents.advice_planner import RequestEmbedding
import json


class AdviceRagContractTests(unittest.TestCase):
    def test_request_embedding_and_encoder_never_enter_public_response(self):
        context = RequestEmbedding('sinh nhật tặng gì', object(), (1., 0.))
        with patch.dict('os.environ', {'LUMIERE_SHOPPING_ADVICE_ENABLED':'true'}), \
             patch('jewelry_agents.retrieval.plan_shopping_advice', return_value={
                 'intent':'gift_advice', '_request_embedding':context}), \
             patch('rag.rag_service.search', return_value={'status':'ok','products':[],'requested_k':3}):
            result = answer_jewelry_question('sinh nhật tặng gì')
        self.assertNotIn('_request_embedding', json.dumps(result))
        self.assertEqual(result['advice_intent'], 'gift_advice')

    def test_unavailable_sources_do_not_claim_catalog_has_no_matching_products(self):
        with patch.dict('os.environ',{'LUMIERE_SHOPPING_ADVICE_ENABLED':'false'}), \
             patch('rag.rag_service.search',return_value={'status':'degraded','products':[],'requested_k':3}):
            response=answer_jewelry_question('Top 3 nhẫn')
        self.assertIn('chưa sẵn sàng',response['answer'])
        self.assertNotIn('Không tìm thấy sản phẩm',response['answer'])

    def test_gift_planner_cannot_rewrite_budget_products_or_rank(self):
        product={'ProductID':17,'ProductName':'QA necklace','Price':1200000,'Stock':2,
                 'Material':'Bạc 925','Gemstone':'CZ','reason':'giá và tồn kho đã kiểm tra'}
        result={'status':'ok','products':[product],'requested_k':3}
        query='Tặng người thương một món trang sức dưới 2 triệu'
        with patch.dict('os.environ',{'LUMIERE_SHOPPING_ADVICE_ENABLED':'true'}), \
             patch('jewelry_agents.retrieval.plan_shopping_advice',return_value={'intent':'gift_advice'}), \
             patch('rag.rag_service.search',return_value=result) as search:
            response=answer_jewelry_question(query)
        self.assertEqual(search.call_args.args[0],query)
        self.assertEqual(response['products'],[product])
        self.assertEqual(response['advice_intent'],'gift_advice')
        self.assertIn('QA necklace',response['answer'])
        self.assertIn('chỉ có 1',response['answer'])

    def test_advice_model_failure_keeps_verified_retrieval(self):
        result={'status':'ok','products':[],'requested_k':3}
        with patch.dict('os.environ',{'LUMIERE_SHOPPING_ADVICE_ENABLED':'true'}), \
             patch('jewelry_agents.retrieval.plan_shopping_advice',side_effect=TimeoutError), \
             patch('rag.rag_service.search',return_value=result):
            response=answer_jewelry_question('Lễ tình nhân tặng gì?')
        self.assertTrue(response['success'])
        self.assertEqual(response['products'],[])
        self.assertIsNone(response['advice_intent'])
