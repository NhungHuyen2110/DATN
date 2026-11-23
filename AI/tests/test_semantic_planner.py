import json
import unittest
from unittest.mock import MagicMock,patch
from pydantic import ValidationError
from jewelry_agents.semantic_planner import QueryPlan,Mention,plan_query,resolve_mentions,merge_understanding
from jewelry_agents.entity_linking import link_query
from jewelry_agents.search_service import search
from test_search_service import product,parse_price
from jewelry_agents.shopping_advice import budget_text


QUERY='Một món ôm quanh ngón tay, đừng quá 3 triệu.'


def ring_plan():
    return QueryPlan(intent='shop',entities=[Mention(label='Category',canonical_id='ring',quote='ôm quanh ngón tay')])


class SemanticPlannerTests(unittest.TestCase):
    def test_budget_normalization_preserves_quote_source_and_numeric_limit(self):
        normalized=budget_text(QUERY)
        self.assertEqual(parse_price(normalized)['max_price'],3_000_000)
        result=search(normalized,3,lambda *a,**k:[{'ProductID':1},{'ProductID':2}],
                      lambda:{1:product(1,price=1_000_000),2:product(2,price=4_000_000)},parse_price,
                      semantic_plan=ring_plan(),semantic_source_query=QUERY)
        self.assertEqual([p['ProductID'] for p in result['products']],[1])

    def test_resolution_uses_ontology_id_not_a_model_generated_graph_id(self):
        resolved=resolve_mentions(ring_plan(),QUERY)
        self.assertEqual(resolved[0]['graph_id'],1)
        self.assertEqual(resolved[0]['method'],'local_llm_semantic')
        with self.assertRaises(ValidationError):
            QueryPlan.model_validate({'intent':'shop','entities':[],'cypher':'MATCH (n) DELETE n'})

    def test_invalid_quote_or_wrong_label_canonical_pair_is_rejected(self):
        for mention in (Mention(label='Category',canonical_id='ruby',quote='ngón tay'),
                        Mention(label='Category',canonical_id='ring',quote='text not in query')):
            with self.assertRaises(ValueError):resolve_mentions(QueryPlan(intent='shop',entities=[mention]),QUERY)

    def test_explicit_category_wins_and_child_is_never_adult_catalog(self):
        explicit=merge_understanding(link_query('bông tai '+QUERY),ring_plan(),'bông tai '+QUERY)
        self.assertEqual([e['canonical_id'] for e in explicit['entities'] if e['label']=='Category'],['earring'])
        result=merge_understanding(link_query(QUERY+' bé 8 tuổi'),ring_plan(),QUERY+' bé 8 tuổi')
        self.assertTrue(result['needs_clarification'])

    def test_conflicting_inferred_entities_require_clarification(self):
        plan=QueryPlan(intent='shop',entities=[*ring_plan().entities,Mention(label='Category',canonical_id='earring',quote='ngón tay')])
        self.assertTrue(merge_understanding(link_query(QUERY),plan,QUERY)['needs_clarification'])

    def test_original_query_goes_to_dense_then_graph_uses_resolved_entity(self):
        live={1:product(1,price=1_000_000),2:product(2,price=1_000_000,category=2)}
        dense=MagicMock(return_value=[{'ProductID':1,'score':0.7},{'ProductID':2,'score':0.8}])
        graph=MagicMock(return_value=[{'ProductID':1,'paths':[{'relationship':'BELONGS_TO','target_id':1}]}])
        expansion=MagicMock(return_value=[])
        result=search(QUERY,3,dense,lambda:live,parse_price,graph,graph_expander=expansion,semantic_plan=ring_plan())
        self.assertEqual(dense.call_args.args[0],QUERY)
        self.assertEqual(graph.call_args.args[1]['entities'][0]['canonical_id'],'ring')
        self.assertEqual(expansion.call_args.args[0],[1])
        self.assertEqual([p['ProductID'] for p in result['products']],[1])
        self.assertIn('graph',result['retrieval_sources_used'])
        self.assertTrue(result['products'][0]['graph_paths'])

    def test_planner_has_no_network_when_disabled_and_no_retry_on_failure(self):
        with patch.dict('os.environ',{'LUMIERE_SEMANTIC_PLANNER_ENABLED':'false'}),patch('jewelry_agents.semantic_planner._gate.call') as gate:
            self.assertIsNone(plan_query(QUERY));gate.assert_not_called()
        with patch.dict('os.environ',{'LUMIERE_SEMANTIC_PLANNER_ENABLED':'true'}),patch('jewelry_agents.semantic_planner._gate.call',side_effect=TimeoutError) as gate:
            self.assertIsNone(plan_query(QUERY));self.assertEqual(gate.call_count,1)

    def test_json_schema_output_is_validated_and_prices_are_not_generated(self):
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=json.dumps(
            {'done':True,'message':{'content':json.dumps({'intent':'shop','entity':'ring','quote':'ngón tay'})}}).encode()
        with patch.dict('os.environ',{'LUMIERE_SEMANTIC_PLANNER_ENABLED':'true'}), \
             patch('jewelry_agents.semantic_planner.urllib.request.build_opener',return_value=opener), \
             patch('jewelry_agents.semantic_planner._gate.call',side_effect=lambda f:f()):
            plan=plan_query(QUERY)
        self.assertEqual(plan.intent,'shop')
        request=json.loads(opener.open.call_args.args[0].data)
        self.assertIn('format',request);self.assertNotIn('tools',request)
        self.assertNotIn('price',request['format']['properties'])

    def test_unknown_question_is_routed_by_model_without_a_sample_phrase(self):
        import api
        from shared.conversation import ConversationStore
        with patch('shared.conversation.STORE',ConversationStore()), \
             patch('jewelry_agents.semantic_planner.plan_query',return_value=ring_plan()), \
             patch('api.answer_jewelry_question',return_value={'success':True,'products':[],'answer':'result'}) as tool:
            api.chat(api.ChatRequest(query=QUERY))
        self.assertEqual(tool.call_args.kwargs['semantic_plan'].entities[0].canonical_id,'ring')

    def test_off_topic_response_redirects_without_product_cards(self):
        import api
        from shared.conversation import ConversationStore
        with patch('shared.conversation.STORE',ConversationStore()), \
             patch('jewelry_agents.semantic_planner.plan_query',return_value=QueryPlan(intent='off_topic')), \
             patch('rag.natural_dialogue.answer_natural',return_value='Mình không có dữ liệu trực tiếp cho chủ đề này.'), \
             patch('api.answer_jewelry_question') as tool:
            result=api.chat(api.ChatRequest(query='Kể về việc trồng rau trên sao Hỏa'))
        tool.assert_not_called()
        self.assertEqual(result['products'],[])
        self.assertIn('Bạn đang chọn cho dịp nào',result['answer'])

    def test_grounded_generation_never_changes_ranked_products(self):
        import api
        from shared.conversation import ConversationStore
        products=[product(3),product(1)]
        with patch.dict('os.environ',{'LUMIERE_GROUNDED_NARRATIVE_ENABLED':'true'}), \
             patch('shared.conversation.STORE',ConversationStore()), \
             patch('jewelry_agents.semantic_planner.plan_query',return_value=ring_plan()), \
             patch('api.answer_jewelry_question',return_value={'success':True,'products':products,'answer':'Facts','retrieval_sources_used':['dense','graph']}), \
             patch('rag.natural_dialogue.answer_natural',return_value='Tư vấn từ bằng chứng.') as generator:
            result=api.chat(api.ChatRequest(query=QUERY))
        self.assertEqual([p['ProductID'] for p in result['products']],[3,1])
        self.assertEqual(result['response_mode'],'grounded_llm_rag')
        self.assertLessEqual(generator.call_args.kwargs['time_budget'],16)
        self.assertNotIn('Price',generator.call_args.kwargs['evidence']['verified_product_attributes'][0])

    def test_semantic_product_intent_is_not_discarded_when_query_has_no_alias(self):
        from rag.rag_service import answer_jewelry_question
        with patch.dict('os.environ',{'LUMIERE_SHOPPING_ADVICE_ENABLED':'true'}), \
             patch('jewelry_agents.retrieval.plan_shopping_advice',return_value={'accepted':True,'intent':'product_search'}) as planner, \
             patch('rag.rag_service.search',return_value={'products':[product(1)],'status':'ok','requested_k':3,'understanding':{}}) as retriever:
            result=answer_jewelry_question(QUERY)
        self.assertTrue(result['products'])
        self.assertEqual(planner.call_count,1)
        self.assertEqual(retriever.call_args.args[0],budget_text(QUERY))

    def test_off_domain_bridge_is_only_appended_once(self):
        import api
        from shared.conversation import ConversationStore
        with patch('shared.conversation.STORE',ConversationStore()), \
             patch('jewelry_agents.semantic_planner.plan_query',return_value=None), \
             patch('rag.natural_dialogue.answer_natural',return_value='Mình chủ yếu hỗ trợ về trang sức.'), \
             patch('api.answer_jewelry_question',side_effect=lambda *a,**k:{'success':True,'intent':'general_question','products':[]}):
            first=api.chat(api.ChatRequest(query='Kể về cuộc sống trên sao Hỏa'))
            second=api.chat(api.ChatRequest(query='Vậy ở sao Kim thì sao?',conversation_id=first['conversation_id']))
        self.assertIn('Bạn đang chọn cho dịp nào',first['answer'])
        self.assertNotIn('Bạn đang chọn cho dịp nào',second['answer'])
