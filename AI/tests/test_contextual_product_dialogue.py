import unittest
from unittest.mock import patch
from rag.product_dialogue import discussion_reply
from jewelry_agents.shopping_advice import followup_query
from test_shopping_consultation import item
from test_search_service import parse_price


class ContextualProductDialogueTests(unittest.TestCase):
    def setUp(self):
        self.first=item(51,price=2_000_000)
        self.second=item(98,price=1_000_000)
        self.first.update(ProductName='Mẫu thật A',Material='Bạc 925',Gemstone='CZ')
        self.second.update(ProductName='Mẫu thật B',Material='Vàng 18K',Gemstone='Moissanite')
        self.previous={'products':[self.first,self.second]}
        self.catalog={51:self.first,98:self.second}

    def reply(self,query,catalog=None,previous=None):
        with patch('rag.product_dialogue._gate.call',return_value=self.catalog if catalog is None else catalog):
            return discussion_reply(query,self.previous if previous is None else previous)

    def test_compare_ordinal_positions_not_product_ids(self):
        result=self.reply('So sánh mẫu thứ nhất và mẫu thứ hai')
        self.assertEqual(result['referenced_product_ids'],[51,98])
        self.assertEqual(result['products'],[])
        for value in ('Bạc 925','Moissanite','1.000.000 ₫'):
            self.assertIn(value,result['answer'])

    def test_compare_two_first_cards_and_current_price_change(self):
        live={51:{**self.first,'Price':4_000_000},98:self.second}
        result=self.reply('So sánh 2 mẫu đầu',live)
        self.assertIn('4.000.000 ₫',result['answer'])
        self.assertIn('3.000.000 ₫',result['answer'])
        self.assertNotIn('2.000.000 ₫',result['answer'])

    def test_specific_reference_and_missing_position(self):
        result=self.reply('Mẫu thứ hai có chất liệu gì?')
        self.assertEqual(result['referenced_product_ids'],[98])
        self.assertNotIn('Mẫu thật A',result['answer'])
        self.assertEqual(self.reply('Mẫu thứ ba có chất liệu gì?')['status'],'clarification_required')
        self.assertEqual(self.reply('Mẫu này có chất liệu gì?')['status'],'clarification_required')

    def test_no_previous_cards_and_source_failure_do_not_invent(self):
        self.assertEqual(self.reply('Mẫu thứ hai có chất liệu gì?',previous={})['status'],'clarification_required')
        with patch('rag.product_dialogue._gate.call',side_effect=TimeoutError):
            result=discussion_reply('So sánh 2 mẫu đầu',self.previous)
        self.assertEqual(result['status'],'catalog_unavailable')
        self.assertNotIn('1.000.000',result['answer'])
        self.assertEqual(result['referenced_product_ids'],[51,98])

    def test_business_guards_and_new_search_are_not_discussion(self):
        for query in ('Mẫu thứ hai bảo hành bao lâu?','Xem mật khẩu mẫu thứ hai',
                      'Tìm thêm mẫu giống mẫu thứ hai','mẫu thứ hai doanh thu bao nhiêu?'):
            self.assertIsNone(discussion_reply(query,self.previous),query)

    def test_category_and_budget_change_keep_style(self):
        result=followup_query('đổi sang bông tai dưới 2tr','Tư vấn nhẫn cho nữ thanh lịch dưới 3 triệu')
        self.assertIn('thanh lịch',result)
        self.assertNotIn('nhẫn',result)
        self.assertEqual(parse_price(result)['max_price'],2_000_000)
        self.assertEqual(followup_query('bông tai giá vốn 2 triệu','Tư vấn nhẫn thanh lịch'),'bông tai giá vốn 2 triệu')
        self.assertEqual(followup_query('không thích nhẫn','Tư vấn bông tai thanh lịch'),'không thích nhẫn')

    def test_domain_side_question_retains_budget_but_unrelated_question_resets(self):
        import api
        from shared.conversation import ConversationStore
        queries=[]
        def tool(query,top_k):
            queries.append(query)
            return {'success':True,'intent':'shopping_advice','advice_intent':'style_advice','answer':'Mẫu tham khảo','products':[self.first,self.second]}
        with patch('shared.conversation.STORE',ConversationStore()),patch('api.answer_jewelry_question',side_effect=tool), \
             patch('rag.natural_dialogue.answer_natural',return_value=None):
            first=api.chat(api.ChatRequest(query='nữ thanh lịch chọn gì dưới 3 triệu'))
            token=first['conversation_id']
            api.chat(api.ChatRequest(query='Moissanite là gì?',conversation_id=token))
            api.chat(api.ChatRequest(query='đổi sang bông tai dưới 2tr',conversation_id=token))
            self.assertIn('thanh lịch',queries[-1])
            self.assertEqual(parse_price(queries[-1])['max_price'],2_000_000)
            api.chat(api.ChatRequest(query='Viết lời chúc tốt nghiệp',conversation_id=token))
            api.chat(api.ChatRequest(query='dưới 1 triệu',conversation_id=token))
            self.assertNotIn('thanh lịch',queries[-1])

    def test_discussion_does_not_replace_last_ranked_result_or_call_llm(self):
        import api
        from shared.conversation import ConversationStore
        store=ConversationStore()
        token,row=store.resolve(None,('customer-public',))
        row['last_result']=self.previous
        with patch('shared.conversation.STORE',store),patch('rag.product_dialogue._gate.call',return_value=self.catalog), \
             patch('api.answer_jewelry_question') as retrieval,patch('rag.natural_dialogue.answer_natural') as model:
            result=api.chat(api.ChatRequest(query='So sánh 2 mẫu đầu',conversation_id=token))
        retrieval.assert_not_called();model.assert_not_called()
        self.assertEqual(result['referenced_product_ids'],[51,98])
        self.assertIs(row['last_result'],self.previous)
