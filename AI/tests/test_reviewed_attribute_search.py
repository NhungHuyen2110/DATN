import hashlib
import unittest
from unittest.mock import patch
from test_search_service import product, parse_price
from jewelry_agents.search_service import search, verified_paths


def fact(label='Style', canonical='elegant', evidence='fixture'):
    return {'label':label,'canonical_id':canonical,
            'name': 'Thanh lịch' if label=='Style' else 'Phái nữ',
            'source_reference_sha256':hashlib.sha256(evidence.encode()).hexdigest()}


class ReviewedAttributeSearchTests(unittest.TestCase):
    def test_combined_audience_style_budget_use_only_approved_live_products(self):
        live={i:product(i) for i in range(1,5)}
        live[1]['verified_attributes']=[fact(),fact('Audience','female')]
        live[2]['verified_attributes']=[fact()]
        live[3]['verified_attributes']=[fact(),fact('Audience','female')]
        live[3]['Price']=9_000_000
        live[4]['verified_attributes']=[{**fact(),'source_reference_sha256':'unverified'}]
        received=[]
        def dense(query,top_k,eligible_ids):
            received.extend(eligible_ids)
            return [{'ProductID':pid} for pid in eligible_ids]
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=search('Top 3 nhẫn cho nữ thanh lịch dưới 8 triệu',3,dense,
                          lambda:live,parse_price)
        self.assertEqual(received,[1])
        self.assertEqual([p['ProductID'] for p in result['products']],[1])
        self.assertIn('Phái nữ',result['products'][0]['reason'])
        self.assertIn('Thanh lịch',result['products'][0]['reason'])

    def test_revoked_fact_during_retrieval_cannot_survive_finalization(self):
        first={1:{**product(1),'verified_attributes':[fact()]}}
        second={1:{**product(1),'verified_attributes':[]}}
        states=iter([first,second])
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            result=search('nhẫn thanh lịch',3,lambda *a,**k:[{'ProductID':1}],
                          lambda:next(states),parse_price)
        self.assertEqual(result['products'],[])

    def test_style_reference_requires_current_evidence_on_both_products(self):
        source={**product(1),'verified_attributes':[fact(evidence='source')]}
        candidate={**product(2),'verified_attributes':[fact(evidence='target')]}
        path={'relationship':'HAS_STYLE','target_label':'Style','target_id':'elegant',
              'source_product_id':1,'candidate_product_id':2,
              'evidence_sha256':fact(evidence='target')['source_reference_sha256'],
              'anchor_evidence_sha256':fact(evidence='source')['source_reference_sha256']}
        with patch.dict('os.environ',{'LUMIERE_ATTRIBUTE_REVIEWS_ENABLED':'true'}):
            self.assertEqual(len(verified_paths([path],candidate,source)),1)
            self.assertEqual(verified_paths([{**path,'anchor_evidence_sha256':'0'*64}],candidate,source),[])
            result=search('Top 3 sản phẩm cùng phong cách với sản phẩm 1',3,
                lambda *a,**k:[{'ProductID':2}],lambda:{1:source,2:candidate},parse_price,
                graph=lambda *a:[{'ProductID':2,'paths':[path]}])
        self.assertEqual([p['ProductID'] for p in result['products']],[2])
        self.assertIn('cùng phong cách Thanh lịch',result['products'][0]['reason'])
