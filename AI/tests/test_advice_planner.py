import unittest
from unittest.mock import patch
from jewelry_agents.advice_planner import plan_advice,PROTOTYPES


class AdvicePlannerTests(unittest.TestCase):
    def test_uses_encoder_and_preserves_query_without_keyword_trigger(self):
        class Encoder:
            def encode(self,texts,**kwargs):
                self.texts=texts
                non_gift=PROTOTYPES['product_search']+PROTOTYPES['other']
                return [[0.,1.] if text in non_gift else [1.,0.] for text in texts]
        encoder=Encoder()
        result=plan_advice('Một món dành tặng người thương?',encoder)
        self.assertEqual(result['intent'],'gift_advice')
        self.assertEqual(encoder.texts[0],'Một món dành tặng người thương?')

    def test_ambiguous_embeddings_do_not_force_gift_intent(self):
        class Encoder:
            def encode(self,texts,**kwargs): return [[1.,0.] for _ in texts]
        self.assertFalse(plan_advice('một món',Encoder())['accepted'])

    def test_bad_encoder_output_is_rejected(self):
        class Encoder:
            def encode(self,texts,**kwargs): return []
        with self.assertRaises(ValueError): plan_advice('quà',Encoder())

    def test_fixed_prototypes_are_encoded_once_and_queries_are_not_cached(self):
        class Encoder:
            def __init__(self): self.calls=[]
            def encode(self,texts,**kwargs):
                self.calls.append(list(texts))
                return [[1.,0.] for _ in texts]
        encoder=Encoder()
        plan_advice('first private question',encoder)
        plan_advice('second private question',encoder)
        self.assertEqual([len(call) for call in encoder.calls],[8,1,1])
        self.assertNotIn('first private question',encoder.calls[0])
