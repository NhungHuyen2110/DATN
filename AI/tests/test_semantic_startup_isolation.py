import threading
import unittest
from unittest.mock import patch

from jewelry_agents import retrieval
from rag.natural_dialogue import answer_natural
from shared.retrieval_limits import SourceGate, SourceUnavailable


class SemanticStartupIsolationTests(unittest.TestCase):
    def test_llm_does_not_load_while_timed_out_embedding_worker_still_runs(self):
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        gate=SourceGate('isolated-startup-test',timeout=.02,cooldown=0)
        warming,ready=threading.Event(),threading.Event()
        def slow_model():
            entered.set()
            release.wait(2)
            return None,object()
        def warm_definitions(model):finished.set()
        with patch.object(retrieval,'_model_warming',warming),patch.object(retrieval,'_semantic_intent_ready',ready), \
             patch.object(retrieval,'_warm_state',{'stage':'not_started','seconds':None}), \
             patch.object(retrieval,'get_dense_services',side_effect=slow_model), \
             patch('jewelry_agents.advice_planner.plan_advice',return_value={}), \
             patch('jewelry_agents.semantic_category.warm_category_definitions',side_effect=warm_definitions), \
             patch.object(retrieval,'_warm_graph_expansion'), \
             patch.object(retrieval._dense_gate,'call_with_timeout',side_effect=lambda timeout,fn:gate.call(fn)), \
             patch.dict('os.environ',{'LUMIERE_RETRIEVAL_LIMITS_ENABLED':'true','LUMIERE_CUSTOMER_DIALOGUE_ENABLED':'true'}), \
             patch('rag.natural_dialogue.urllib.request.build_opener') as opener:
            try:
                with self.assertRaises(SourceUnavailable):retrieval.warm_shopping_model()
                self.assertTrue(entered.is_set())
                self.assertTrue(warming.is_set())
                self.assertFalse(ready.is_set())
                self.assertIsNone(answer_natural('Any natural question'))
                opener.assert_not_called()
                release.set()
                self.assertTrue(finished.wait(2))
                gate._future.result(timeout=2)
                self.assertFalse(warming.is_set())
                self.assertTrue(ready.is_set())
                self.assertEqual(retrieval.semantic_model_status()['stage'],'ready')
            finally:
                release.set()
                gate.close()

    def test_warmup_records_individual_stage_durations_without_loading_real_models(self):
        ready=threading.Event()
        warming=threading.Event()
        phases=[]
        fake_model=object()
        def fake_plan(query,model,include_embedding=False):
            self.assertIs(model,fake_model)
            phases.append('intent')
            return {'accepted':True}
        def fake_ontology(model):
            self.assertIs(model,fake_model)
            phases.append('ontology')
        with patch.object(retrieval,'_semantic_intent_ready',ready), \
             patch.object(retrieval,'_model_warming',warming), \
             patch.object(retrieval,'_warm_state',{'stage':'not_started','seconds':None}), \
             patch.object(retrieval,'get_dense_services',return_value=(None,fake_model)), \
             patch('jewelry_agents.advice_planner.plan_advice',side_effect=fake_plan), \
             patch('jewelry_agents.semantic_category.warm_category_definitions',side_effect=fake_ontology), \
             patch.object(retrieval,'_warm_graph_expansion'), \
             patch.dict('os.environ',{'LUMIERE_RETRIEVAL_LIMITS_ENABLED':'false'}):
            result=retrieval.warm_shopping_model()
            status=retrieval.semantic_model_status()
        self.assertEqual(result,{'accepted':True})
        self.assertEqual(phases,['intent','ontology'])
        self.assertTrue(ready.is_set())
        self.assertFalse(warming.is_set())
        self.assertEqual(status['stage'],'ready')
        durations=status['stage_durations_seconds']
        self.assertEqual(set(durations),{'load_encoder','intent_vectors','ontology_vectors','graph_connection'})
        self.assertTrue(all(isinstance(n,float) and n>=0 for n in durations.values()))

    def test_semantic_health_never_loads_model_or_fetches_catalog(self):
        import api
        with patch('jewelry_agents.business_catalog.fetch_catalog') as catalog, \
             patch.object(retrieval,'get_dense_services') as model, \
             patch.object(retrieval,'semantic_model_status',return_value={'ready':False,'warming':True,'stage':'load_encoder','seconds':0}):
            result=api.semantic_readiness()
        self.assertEqual(result.status_code,503)
        catalog.assert_not_called()
        model.assert_not_called()

    def test_loaded_model_is_not_ready_while_source_is_cooling_down(self):
        ready=threading.Event();ready.set()
        with patch.object(retrieval,'_semantic_intent_ready',ready), \
             patch.object(retrieval,'_model_warming',threading.Event()), \
             patch.object(retrieval._dense_gate,'availability',return_value={'available':False,'busy':False,'cooldown_seconds':5}):
            self.assertFalse(retrieval.semantic_model_status()['ready'])

    def test_unresolved_shopping_never_becomes_random_lexical_cards_during_startup(self):
        from rag.rag_service import answer_jewelry_question
        warming=threading.Event();warming.set()
        with patch.object(retrieval,'_model_warming',warming), \
             patch('rag.rag_service.search') as search, \
             patch.dict('os.environ',{'LUMIERE_RETRIEVAL_V2_ENABLED':'true'}):
            result=answer_jewelry_question('Một món ôm quanh ngón tay, đừng quá 3 triệu.')
        self.assertEqual(result['status'],'model_warming')
        self.assertEqual(result['products'],[])
        search.assert_not_called()
