import unittest
from unittest.mock import MagicMock
from jewelry_agents.semantic_category import category_links,merge_category_links,CategoryLink
from jewelry_agents.entity_linking import link_query,load_entities
from jewelry_agents.advice_planner import RequestEmbedding
from jewelry_agents.search_service import search
from test_search_service import product,parse_price


class DefinitionEncoder:
    def __init__(self):self.calls=[]
    def encode(self,texts,**kwargs):
        self.calls.append((list(texts),kwargs))
        ring=next(e['definition'] for e in load_entities()['entities'] if e['canonical_id']=='ring')
        return [[1.,0.] if text==ring else [0.,1.] for text in texts]


class SemanticCategoryTests(unittest.TestCase):
    def test_vector_link_uses_definitions_and_cached_public_embeddings(self):
        model=DefinitionEncoder()
        links=category_links('Một món ôm lấy ngón tay',model,[1.,0.])
        self.assertEqual(links[0].canonical_id,'ring')
        self.assertEqual(links[0].similarity,1.)
        category_links('Cách diễn đạt mới',model,[1.,0.])
        self.assertEqual(len(model.calls),1)
        self.assertEqual(model.calls[0][1]['batch_size'],1)
        self.assertNotIn('Một món ôm lấy ngón tay',model.calls[0][0])

    def test_ambiguous_low_scores_and_negated_desire_abstain(self):
        model=DefinitionEncoder()
        self.assertEqual(category_links('Một món',model,[1.,1.]),())
        self.assertEqual(category_links('không đeo trên ngón tay',model,[1.,0.]),())
        self.assertEqual(category_links('bông tai',model,[1.,0.]),())

    def test_exact_request_binding_and_explicit_filters_cannot_be_overridden(self):
        query='Món ôm lấy ngón tay dưới 3 triệu'
        context=RequestEmbedding(query,object(),(1.,0.),(CategoryLink('ring',1,.9,.4),))
        merged=merge_category_links(link_query(query),context,query)
        self.assertEqual(merged['entities'][0]['graph_id'],1)
        with self.assertRaises(ValueError):merge_category_links(link_query('khác'),context,'khác')
        explicit=merge_category_links(link_query('bông tai'),RequestEmbedding('bông tai',object(),(1.,0.),context.entity_links),'bông tai')
        self.assertEqual(explicit['entities'][0]['canonical_id'],'earring')

    def test_filter_precedes_dense_and_graph_candidate_limit(self):
        query='Món ôm lấy ngón tay dưới 3 triệu'
        context=RequestEmbedding(query,object(),(1.,0.),(CategoryLink('ring',1,.9,.4),))
        live={1:product(1,price=1_000_000),2:product(2,price=4_000_000),3:product(3,price=1_000_000,category=2)}
        dense=MagicMock(return_value=[{'ProductID':1,'score':.72}])
        expander=MagicMock(return_value=[])
        result=search(query,3,dense,lambda:live,parse_price,graph=lambda *a:[],graph_expander=expander,entity_context=context)
        self.assertEqual(dense.call_args.kwargs['eligible_ids'],[1])
        self.assertEqual(expander.call_args.kwargs['eligible_ids'],[1])
        self.assertEqual([p['ProductID'] for p in result['products']],[1])
        self.assertEqual(result['products'][0]['semantic_score'],.72)
        self.assertNotEqual(result['products'][0]['final_score'],.72)
