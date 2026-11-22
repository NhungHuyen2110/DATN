import unittest
from unittest.mock import patch
from jewelry_agents.advice_planner import plan_advice,PROTOTYPES


class AdvicePlannerTests(unittest.TestCase):
    def test_uses_encoder_and_preserves_query_without_keyword_trigger(self):
        class Encoder:
            def encode(self,texts):
                self.texts=texts
                return [[1.,0.]]+[[1.,0.] for _ in PROTOTYPES['gift_advice']]+[[0.,1.] for _ in range(5)]
        encoder=Encoder()
        result=plan_advice('Một món dành tặng người thương?',encoder)
        self.assertEqual(result['intent'],'gift_advice')
        self.assertEqual(encoder.texts[0],'Một món dành tặng người thương?')

    def test_ambiguous_embeddings_do_not_force_gift_intent(self):
        class Encoder:
            def encode(self,texts): return [[1.,0.] for _ in texts]
        self.assertFalse(plan_advice('một món',Encoder())['accepted'])

    def test_bad_encoder_output_is_rejected(self):
        class Encoder:
            def encode(self,texts): return []
        with self.assertRaises(ValueError): plan_advice('quà',Encoder())
