import unittest
from unittest.mock import patch
from shared.conversation import ConversationStore,converse


class ConversationTests(unittest.TestCase):
    def test_busy_conversation_does_not_queue_or_run_another_tool(self):
        store=ConversationStore()
        token,row=store.resolve(None,('customer-public',))
        row['lock'].acquire()
        try:
            with patch('shared.conversation.STORE',store):
                response=converse('question',token,('customer-public',),
                                  lambda q:self.fail('No queued tool is permitted'))
            self.assertEqual(response['status'],'conversation_busy')
        finally:
            row['lock'].release()
    def test_reported_three_turn_sequence_does_not_search_again(self):
        products=[{'ProductID':31,'ProductName':'QA previous earring'},
                  {'ProductID':486,'ProductName':'QA previous necklace'}]
        with patch('shared.conversation.STORE',ConversationStore()):
            calls=[]
            def tool(question):
                calls.append(question)
                return {'answer':'Verified first response','products':products,'success':True}
            first=converse('sinh nhật tặng gì',None,('customer-public',),tool)
            second=converse('tại sao lại gợi ý sản phẩm đó',first['conversation_id'],('customer-public',),tool)
            third=converse('có hỏi sản phẩm đâu mà trả lời',first['conversation_id'],('customer-public',),tool)
        self.assertEqual(len(calls),1)
        self.assertEqual(second['referenced_product_ids'],[31,486])
        self.assertIn('QA previous earring',second['answer'])
        self.assertEqual(second['products'],[])
        self.assertEqual(third['products'],[])
        self.assertEqual(third['intent'],'conversation_correction')

    def test_private_role_context_cannot_be_reused_by_other_user_or_role(self):
        with patch('shared.conversation.STORE',ConversationStore()):
            tool=lambda q:{'answer':'private aggregate','products':[{'ProductID':7,'ProductName':'PRIVATE_CANARY'}]}
            first=converse('inventory',None,('admin',1),tool)
            for scope in [('admin',2),('staff',1),('customer-public',)]:
                other=converse('tại sao',first['conversation_id'],scope,tool)
                self.assertNotIn('PRIVATE_CANARY',other['answer'])
                self.assertNotEqual(other['conversation_id'],first['conversation_id'])

    def test_store_is_bounded_and_expires_history(self):
        now=[10]
        store=ConversationStore(limit=2,ttl=3,clock=lambda:now[0])
        first,_=store.resolve(None,('a',))
        store.resolve(None,('a',));store.resolve(None,('a',))
        self.assertEqual(len(store.rows),2)
        self.assertNotIn(first,store.rows)
        now[0]=20
        store.resolve(None,('a',))
        self.assertEqual(len(store.rows),1)

    def test_general_question_never_falls_through_to_product_search(self):
        from jewelry_agents.intent_router import classify_query
        self.assertEqual(classify_query('Bạn đang nói chuyện gì vậy?'),'general_question')
        self.assertEqual(classify_query('Tại sao nhẫn kim cương đắt?'),'general_question')
        from shared.conversation import followup_kind
        self.assertIsNone(followup_kind('Tại sao vàng không bị gỉ?'))
