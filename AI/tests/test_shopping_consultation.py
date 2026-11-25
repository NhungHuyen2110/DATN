import hashlib
import unittest
from unittest.mock import patch

from jewelry_agents.entity_linking import link_query
from jewelry_agents.shopping_advice import advisory_request, followup_query, budget_text
from jewelry_agents.search_service import search
from rag.rag_service import answer_jewelry_question
from test_search_service import product, parse_price


def item(pid, price=1_000_000, category=2, stock=2):
    row=product(pid, price=price, category=category, stock=stock)
    row['Category']={1:'Nhẫn',2:'Dây chuyền',3:'Bông tai'}[category]
    return row


def fact(label, canonical, name):
    return {'label':label,'canonical_id':canonical,'name':name,
            'source_reference_sha256':hashlib.sha256((label+canonical).encode()).hexdigest()}


class ConsultationTests(unittest.TestCase):
    def test_short_style_budget_variants_and_fresh_session_route_to_search(self):
        import api
        from shared.conversation import ConversationStore
        from jewelry_agents.shopping_advice import standalone_budget
        for message in ('dưới 3tr','dưới 3 triệu','3 triệu'):
            self.assertEqual(parse_price(standalone_budget(message))['max_price'],3_000_000)
            queries=[]
            def answer(query,top_k):
                queries.append(query)
                return {'success':True,'intent':'shopping_advice','advice_intent':'style_advice',
                        'products':[],'answer':'Tư vấn'}
            with patch('shared.conversation.STORE',ConversationStore()),patch('api.answer_jewelry_question',side_effect=answer):
                first=api.chat(api.ChatRequest(query='thanh lịch'))
                api.chat(api.ChatRequest(query=message,conversation_id=first['conversation_id']))
                api.chat(api.ChatRequest(query=message))
            self.assertTrue(advisory_request(queries[1]),queries[1])
            self.assertEqual(parse_price(queries[1])['max_price'],3_000_000)
            self.assertTrue(queries[2].startswith('Tìm trang sức'))

    def test_domain_answers_use_no_catalog_and_keep_knowledge_history(self):
        import api
        from shared.conversation import ConversationStore
        with patch('shared.conversation.STORE',ConversationStore()),patch('api.answer_jewelry_question') as search:
            first=api.chat(api.ChatRequest(query='Moissanite là gì?'))
            second=api.chat(api.ChatRequest(query='nói ngắn gọn hơn',conversation_id=first['conversation_id']))
            search.assert_not_called()
        self.assertEqual(first['response_mode'],'reviewed_domain_answer')
        self.assertIn('không phải kim cương nuôi cấy',first['answer'])
        self.assertEqual(first['products'],[])
        self.assertLess(len(second['answer']),len(first['answer']))

    def test_domain_topics_and_limits(self):
        from rag.domain_dialogue import domain_answer
        for query in ('CZ là gì?','Cách bảo quản ngọc trai','Thanh lịch là gì?',
                      'Cỡ nhẫn đo sao?','Viết lời chúc sinh nhật'):
            self.assertTrue(domain_answer(query),query)
        self.assertIsNone(domain_answer('Đơn hàng hôm nay bao nhiêu?'))
        self.assertIsNone(domain_answer('Giá kim cương bảo hành thế nào?'))
        self.assertIsNone(domain_answer('Ai thắng bóng đá hôm nay?'))
        previous={'user':'Moissanite là gì?','answer':'old'}
        self.assertLess(len(domain_answer('nói ngắn gọn hơn',[previous])['answer']),len(domain_answer(previous['user'])['answer']))

    def test_category_refinement_retains_budget_and_replaces_old_category(self):
        from jewelry_agents.shopping_advice import next_question
        merged=followup_query('mình thích bông tai','nữ thanh lịch chọn gì nhẫn dưới 3 triệu')
        self.assertEqual(parse_price(merged)['max_price'],3_000_000)
        self.assertEqual([e['canonical_id'] for e in link_query(merged)['entities'] if e['label']=='Category'],['earring'])
        self.assertIn('thanh lịch',merged)
        self.assertNotIn('Bạn thích nhẫn',next_question(merged))

    def test_shorthand_budgets_do_not_change_gold_karat_or_product_identity(self):
        self.assertEqual(parse_price(budget_text('dưới 3tr'))['max_price'],3_000_000)
        self.assertEqual(parse_price(budget_text('dưới 500k'))['max_price'],500_000)
        self.assertEqual(parse_price(budget_text('duoi3tr'))['max_price'],3_000_000)
        self.assertIn('18K',budget_text('nhẫn vàng 18K dưới 3tr'))
        self.assertEqual(budget_text('SKU 3TR'),'SKU 3TR')

    def test_short_budget_followup_retains_style_and_karat(self):
        merged=followup_query('500k','nữ thanh lịch chọn gì vàng 18K dưới 3tr')
        self.assertIn('18K',merged);self.assertIn('thanh lịch',merged)
        self.assertNotIn('3tr',merged)
        self.assertEqual(parse_price(merged)['max_price'],500_000)
        self.assertEqual(parse_price(followup_query('em chỉ có 3tr','nữ thanh lịch chọn gì'))['max_price'],3_000_000)

    def run_search(self, query, catalog, mode='advisory', dense=None):
        return search(query,3,dense or (lambda *a,**k:[{'ProductID':pid} for pid in reversed(k['eligible_ids'])]),
                      lambda:catalog,parse_price,preference_mode=mode)

    def test_leading_female_subject_is_not_generic_jewelry_or_product_name(self):
        self.assertIn('female',[e['canonical_id'] for e in link_query('nữ thanh lịch chọn gì')['entities']])
        for query in ('nữ trang thanh lịch','nữ hoàng thanh lịch','nữ thần'):
            self.assertFalse(any(e['label']=='Audience' for e in link_query(query)['entities']))

    def test_broad_audience_search_is_advice_without_fake_verified_gender(self):
        for query in ('Tìm trang sức dành cho phái nữ.',
                      'Có mẫu trang sức nào dành cho con gái không?',
                      'Tôi muốn mua trang sức cho phụ nữ.',
                      'Tìm trang sức dành cho nữ giới.'):
            with self.subTest(query=query):
                self.assertTrue(advisory_request(query))
                result=self.run_search(query, {1:item(1), 2:item(2,category=3)})
                self.assertEqual(result['status'],'ok')
                self.assertEqual(len(result['products']),2)
                self.assertEqual(result['understanding']['unverified_preferences'],
                                 [{'label':'Audience','canonical_id':'female'}])
                self.assertTrue(all('Audience' not in
                                    [e['label'] for e in p['matched_entities']]
                                    for p in result['products']))

    def test_explicit_or_specific_audience_filters_are_not_silently_relaxed(self):
        for query in ('Top 3 trang sức dành cho phái nữ',
                      'chỉ tìm trang sức dành cho phái nữ',
                      'Tìm nhẫn dành cho phái nữ',
                      'Có mẫu trang sức nào cho bé gái 8 tuổi không?'):
            with self.subTest(query=query):
                self.assertFalse(advisory_request(query))
        self.assertEqual(self.run_search('Top 3 trang sức dành cho phái nữ',
                                        {1:item(1)},mode='strict')['status'],
                         'missing_verified_attributes')
        self.assertEqual(self.run_search('Có mẫu trang sức nào cho bé gái 8 tuổi không?',
                                        {1:item(1)},mode='strict')['status'],
                         'clarification_required')

    def test_consultation_is_distinct_from_strict_filter_and_child_request(self):
        for query in ('nữ thanh lịch chọn gì','Tư vấn nhẫn cho nữ thanh lịch dưới 3 triệu',
                      'nữ thanh lịch chọn gì em chỉ có 2 triệu'):
            self.assertTrue(advisory_request(query),query)
        for query in ('Top 3 nhẫn cho nữ thanh lịch','chỉ chọn nhẫn cho nữ thanh lịch',
                      'bé gái 5 tuổi nên chọn gì','sản phẩm cùng phong cách với sản phẩm 2'):
            self.assertFalse(advisory_request(query),query)

    def test_soft_preferences_return_real_reference_products_without_false_entity_matches(self):
        live={1:item(1),2:item(2,category=3)}
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('nữ thanh lịch chọn gì',live)
        self.assertEqual(len(result['products']),2)
        self.assertEqual({e['label'] for e in result['understanding']['unverified_preferences']},{'Audience','Style'})
        self.assertTrue(all(not any(e['label'] in {'Audience','Style'} for e in p['matched_entities']) for p in result['products']))
        self.assertTrue(all('đã được xác nhận' not in p['reason'] for p in result['products']))

    def test_known_conflicting_labels_do_not_become_reference_products(self):
        live={1:item(1),2:item(2)}
        live[1]['verified_attributes']=[fact('Audience','male','Phái nam')]
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('nữ thanh lịch chọn gì',live)
        self.assertEqual([p['ProductID'] for p in result['products']],[2])

    def test_available_approved_facts_are_still_required(self):
        live={1:item(1),2:item(2)}
        live[1]['verified_attributes']=[fact('Audience','female','Phái nữ'),fact('Style','elegant','Thanh lịch')]
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('nữ thanh lịch chọn gì',live)
        self.assertEqual([p['ProductID'] for p in result['products']],[1])
        self.assertNotIn('unverified_preferences',result['understanding'])

    def test_price_stock_and_category_remain_hard_constraints(self):
        live={1:item(1,category=1),2:item(2,3_000_000,category=1),
              3:item(3,category=3),4:item(4,category=1,stock=0)}
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('Tư vấn nhẫn cho nữ thanh lịch dưới 3 triệu',live)
        self.assertEqual([p['ProductID'] for p in result['products']],[1])

    def test_default_strict_search_never_relaxes_the_same_preferences(self):
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('Top 3 nhẫn cho nữ thanh lịch',{1:item(1,category=1)},mode='strict')
        self.assertEqual(result['products'],[])
        self.assertEqual(result['status'],'missing_verified_attributes')

    def test_dense_failure_still_offers_category_references_without_semantic_score(self):
        def unavailable(*a,**k):raise TimeoutError('synthetic source outage')
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=self.run_search('nữ thanh lịch chọn gì',{1:item(1),2:item(2,category=3)},dense=unavailable)
        self.assertEqual(result['status'],'degraded')
        self.assertEqual(len(result['products']),2)
        self.assertTrue(all(p['retrieval_sources']==['lexical'] and 'semantic_score' not in p for p in result['products']))

    def test_budget_followup_replaces_previous_budget_without_hijacking_new_topic(self):
        previous='nữ thanh lịch chọn gì dưới 3 triệu'
        merged=followup_query('tầm 2 triệu thôi',previous)
        self.assertIn('thanh lịch',merged)
        self.assertEqual(parse_price(merged)['max_price'],2_000_000)
        self.assertNotIn('3 triệu',merged)
        for message in ('mua máy tính 20 triệu','doanh thu 3 triệu','Đá Ruby là gì?'):
            self.assertEqual(followup_query(message,previous),message)

    def test_rag_advises_instead_of_blocking_or_loading_gift_classifier(self):
        result={'status':'ok','products':[item(1)],'requested_k':3,
                'understanding':{'unverified_preferences':[{'label':'Style','canonical_id':'elegant'}]}}
        with patch.dict('os.environ',{'LUMIERE_SHOPPING_ADVICE_ENABLED':'true'}), \
             patch('rag.rag_service.search',return_value=result) as retrieval, \
             patch('jewelry_agents.retrieval.plan_shopping_advice') as classifier:
            response=answer_jewelry_question('nữ thanh lịch chọn gì')
        self.assertEqual(retrieval.call_args.kwargs['preference_mode'],'advisory')
        classifier.assert_not_called()
        self.assertEqual(response['products'],[item(1)])
        self.assertIn('Bạn muốn chi khoảng bao nhiêu',response['answer'])
        self.assertNotIn('Yêu cầu đã được nhận diện',response['answer'])
        self.assertEqual(response['recommendation_scope'],'advisory_unverified_preferences')

    def test_unavailable_sources_still_get_useful_advice_not_a_false_empty_catalog(self):
        result={'status':'degraded','products':[],'requested_k':3,'understanding':{}}
        with patch('rag.rag_service.search',return_value=result):
            response=answer_jewelry_question('nữ thanh lịch chọn gì')
        self.assertIn('gu thanh lịch',response['answer'])
        self.assertIn('chưa kiểm tra được',response['answer'])
        self.assertNotIn('Không tìm thấy sản phẩm',response['answer'])

    def test_budget_followup_and_why_use_same_private_conversation(self):
        import api
        from shared.conversation import ConversationStore
        queries=[]
        def answer(query,top_k):
            queries.append(query)
            return {'success':True,'intent':'shopping_advice','advice_intent':'style_advice',
                'recommendation_scope':'advisory_unverified_preferences','products':[item(1)],'answer':'Tham khảo mẫu này.'}
        with patch('shared.conversation.STORE',ConversationStore()),patch('api.answer_jewelry_question',side_effect=answer):
            first=api.chat(api.ChatRequest(query='nữ thanh lịch chọn gì'))
            second=api.chat(api.ChatRequest(query='dưới 3 triệu',conversation_id=first['conversation_id']))
            why=api.chat(api.ChatRequest(query='tại sao lại gợi ý sản phẩm đó',conversation_id=first['conversation_id']))
        self.assertEqual(len(queries),2)
        self.assertIn('thanh lịch',queries[1]);self.assertIn('3 triệu',queries[1])
        self.assertEqual(why['referenced_product_ids'],[1]);self.assertEqual(why['products'],[])
        self.assertNotIn('shopping_context',second)
