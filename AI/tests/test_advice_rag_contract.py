import unittest
from unittest.mock import patch
from rag.rag_service import answer_jewelry_question


class AdviceRagContractTests(unittest.TestCase):
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
