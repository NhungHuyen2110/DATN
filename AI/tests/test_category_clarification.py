import unittest
from unittest.mock import patch
from rag.category_clarification import category_question,pending_category_reply
from test_search_service import parse_price,product


class CategoryClarificationTests(unittest.TestCase):
    def test_close_scores_ask_dynamic_options_without_lowering_threshold(self):
        result=category_question('original',{'ring':.601,'bracelet':.506,'earring':.2})
        self.assertEqual(result['products'],[])
        self.assertEqual([p['canonical_id'] for p in result['clarification_options']],['ring','bracelet'])
        self.assertIsNone(category_question('original',{'ring':.8,'bracelet':.5}))
        self.assertIsNone(category_question('original',{'ring':.3,'bracelet':.29}))

    def test_clarification_choice_keeps_original_price_and_real_category(self):
        import api
        from shared.conversation import ConversationStore
        calls=[]
        def answer(query,top_k,**kwargs):
            calls.append(query)
            if len(calls)==1:return category_question(query,{'ring':.601,'bracelet':.506})
            return {'success':True,'products':[product(2,price=2_000_000)],'answer':'Live facts'}
        with patch('shared.conversation.STORE',ConversationStore()), \
             patch('jewelry_agents.semantic_planner.plan_query',return_value=None), \
             patch('api.answer_jewelry_question',side_effect=answer):
            first=api.chat(api.ChatRequest(query='Một món trang sức nhỏ gọn, đừng quá 3 triệu.'))
            second=api.chat(api.ChatRequest(query='Loại đầu tiên',conversation_id=first['conversation_id']))
            why=api.chat(api.ChatRequest(query='Tại sao lại gợi ý sản phẩm đó?',conversation_id=first['conversation_id']))
        from jewelry_agents.shopping_advice import budget_text
        self.assertIn('nhẫn',calls[1])
        self.assertEqual(parse_price(budget_text(calls[1]))['max_price'],3_000_000)
        self.assertEqual(second['clarification_resolution']['canonical_id'],'ring')
        self.assertEqual(why['referenced_product_ids'],[2])

    # def test_semantic_reply_is_resolved_against_existing_options(self):
    #     from jewelry_agents.semantic_category import CategoryLink
    #     row={'pending_category':{'query':'dưới 3 triệu','options':[{'name':'nhẫn','canonical_id':'ring'}]}}
    #     with patch('jewelry_agents.retrieval._dense_gate.call',return_value=((CategoryLink('ring',1,.8,.3),),True)):
    #         result=pending_category_reply('Đeo trên một ngón tay',row,lambda query:{'answer':query,'products':[]})
    #     self.assertEqual(result['clarification_resolution']['method'],'ontology_reply_embedding')
    #     self.assertNotIn('pending_category',row)

# mới thêm
    def test_semantic_reply_is_resolved_against_existing_options(self):
        from jewelry_agents.semantic_category import CategoryLink

        row = {
            'pending_category': {
                'query': 'dưới 3 triệu',
                'options': [
                    {'name': 'nhẫn', 'canonical_id': 'ring'}
                ]
            }
        }

        with patch(
            'jewelry_agents.retrieval._dense_gate.call',
            return_value=((CategoryLink('ring', 1, .8, .3),), True)
        ) as dense_call:
            result = pending_category_reply(
                'Loại thường dùng để cầu hôn',
                row,
                lambda query: {'answer': query, 'products': []}
            )

        dense_call.assert_called_once()

        self.assertEqual(
            result['clarification_resolution']['method'],
            'ontology_reply_embedding'
        )

        self.assertNotIn('pending_category', row)

    def test_price_can_change_while_type_is_still_being_clarified(self):
        row={'pending_category':{'query':'Món ôm quanh ngón tay dưới 3 triệu',
                                'options':[{'name':'nhẫn','canonical_id':'ring'}]}}
        response=pending_category_reply('dưới 2tr',row,lambda query:self.fail('No product retrieval yet'))
        self.assertEqual(response['status'],'clarification_required')
        self.assertEqual(parse_price(row['pending_category']['query'])['max_price'],2_000_000)

    def test_private_requests_are_never_treated_as_a_selection(self):
        row={'pending_category':{'query':'public','options':[]}}
        self.assertIsNone(pending_category_reply('Mật khẩu là gì?',row,lambda query:self.fail('No tool')))

    # mới thêm
    def test_ontology_reply_resolves_existing_options(self):
        row = {
            'pending_category': {
                'query': 'dưới 3 triệu',
                'options': [
                    {'name': 'nhẫn', 'canonical_id': 'ring'},
                    {'name': 'charm', 'canonical_id': 'charm'}
                ]
            }
        }

        result = pending_category_reply(
            'Đeo trên một ngón tay',
            row,
            lambda query: {'answer': query, 'products': []}
        )

        self.assertEqual(
            result['clarification_resolution']['canonical_id'],
            'ring'
        )

        self.assertEqual(
            result['clarification_resolution']['method'],
            'ontology_reply_constraint'
        )

        self.assertNotIn('pending_category', row)

    def test_finger_does_not_ask_about_charm(self):
        result = category_question(
            'Tôi muốn mua trang sức đeo quanh ngón tay',
            {'ring': .6423, 'charm': .6205}
        )

        self.assertIsNone(result)

    def test_neck_does_not_ask_about_charm(self):
        result = category_question(
            'Tôi muốn mua trang sức đeo quanh cổ',
            {'necklace': .6135, 'charm': .5270}
        )

        self.assertIsNone(result)

    def test_wrist_only_offers_compatible_categories(self):
        result = category_question(
            'Tôi muốn mua trang sức đeo quanh cổ tay',
            {
                'charm': .6233,
                'necklace': .6169,
                'ring': .5620,
                'chain_bracelet': .5586,
                'bracelet': .5355
            }
        )

        actual = {
            item['canonical_id']
            for item in result['clarification_options']
        }

        self.assertEqual(
            actual,
            {'bracelet', 'chain_bracelet'}
        )

        self.assertEqual(
            result['query_planning_method'],
            'ontology_constraint_ambiguity'
        )

