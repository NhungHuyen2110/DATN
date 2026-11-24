"""Discuss previous ranked cards with fresh catalog facts, never new candidates."""
from decimal import Decimal
import re
from shared.retrieval_limits import SourceGate
from jewelry_agents.entity_linking import normalize
from jewelry_agents.business_catalog import fetch_catalog
from jewelry_agents.intent_router import classify_query

_gate=SourceGate('product-discussion',timeout=4,cooldown=10)
_ORDINAL={'mot':1,'nhat':1,'hai':2,'ba':3,'tu':4,'bon':4,'nam':5}
_REFERENCE=re.compile(r'\b(?:mau|san pham)\s+(?:thu\s+|so\s+)?(\d+|mot|nhat|hai|ba|tu|bon|nam)\b')


def discussion_reply(message,previous):
    text=normalize(message)
    if classify_query(message) in {'restricted_request','shipping_policy','unverified_policy','customer_order_guidance'}:
        return None
    from jewelry_agents.query_reference import reference_request
    if reference_request(message)['active']:
        # A catalog product ID is not an ordinal card position. Related-product
        # requests must reach graph retrieval even without earlier chat cards.
        return None
    # Never reinterpret shopping, account or policy operations as card discussion.
    if any(word in text for word in ('mat khau','doanh thu','don hang','bao hanh','doi tra',
                                     'mua ngay','dat hang','giong','tuong tu','tim them','goi y them')):
        return None
    products=(previous or {}).get('products',[])
    compare='so sanh' in text
    positions=[]
    for match in _REFERENCE.finditer(text):
        value=match.group(1)
        position=int(value) if value.isdigit() else _ORDINAL[value]
        if position not in positions:positions.append(position)
    if compare and not positions and re.search(r'\b(?:hai|2) mau (?:dau|vua)\b',text):positions=[1,2]
    if 'mau dau' in text and 1 not in positions:positions.append(1)
    if 'mau cuoi' in text and products and len(products) not in positions:positions.append(len(products))
    referring=bool(positions or any(term in text for term in ('mau nay','mau do','hai mau','2 mau')))
    if not referring or not (compare or any(term in text for term in
            ('tai sao','vi sao','chat lieu','loai da','gia bao nhieu','con hang','khac nhau','noi ro','giai thich'))):
        return None
    result={'success':True,'intent':'product_discussion','products':[],'referenced_product_ids':[],
            'status':'clarification_required','response_mode':'grounded_product_discussion'}
    if not products:
        return {**result,'answer':'Mình chưa có danh sách mẫu trong cuộc trò chuyện này. Bạn gửi mã sản phẩm hoặc yêu cầu tìm mẫu trước nhé.'}
    if not positions and len(products)==1:positions=[1]
    if not positions or (compare and len(positions)<2):
        return {**result,'answer':'Bạn muốn nói đến những mẫu nào trong danh sách vừa rồi? Ví dụ: “so sánh mẫu thứ nhất và mẫu thứ hai”.'}
    if len(positions)>3 or any(not 1<=i<=len(products) for i in positions):
        return {**result,'answer':'Số thứ tự bạn nêu chưa khớp danh sách vừa rồi. Bạn chọn lại số thứ tự hoặc gửi mã sản phẩm nhé.'}
    selected=[products[i-1] for i in positions]
    ids=[item['ProductID'] for item in selected]
    result['referenced_product_ids']=ids
    try:
        catalog=_gate.call(fetch_catalog)
        current=[catalog[pid] for pid in ids]
        lines=[]
        prices=[]
        for item in current:
            price=Decimal(str(item['Price']))
            if not price.is_finite() or price<0:raise ValueError('Invalid price')
            prices.append(price)
            amount=f'{price:,.0f}'.replace(',','.')
            lines.append(f"• {item['ProductName']} (mã {item['ProductID']}): {item['Material']}; đá {item['Gemstone']}; {amount} ₫; tồn kho {item['Stock']}.")
        if compare:
            difference=max(prices)-min(prices)
            detail=('Các mẫu đang có cùng giá.' if difference==0 else
                    'Chênh lệch giữa giá cao nhất và thấp nhất là '+f'{difference:,.0f}'.replace(',','.')+' ₫.')
            answer='Mình so sánh đúng các mẫu bạn chọn, với giá và tồn kho vừa kiểm tra:\n'+'\n'.join(lines)+'\n'+detail
        else:
            answer='Đây là thông tin hiện tại của mẫu bạn đang hỏi:\n'+'\n'.join(lines)
            if 'tai sao' in text or 'vi sao' in text:
                answer+='\nMẫu này có trong danh sách tham khảo cho yêu cầu trước. Giá và tồn kho là dữ liệu kiểm tra được; chúng chưa chứng minh mẫu hợp sở thích hoặc có nhãn phong cách bạn muốn.'
        return {**result,'status':'ok','answer':answer,'verified_source':'business_api'}
    except Exception:
        # Do not use the old card price as though it were a current observation.
        return {**result,'status':'catalog_unavailable',
                'answer':'Mình hiểu bạn đang hỏi các mẫu vừa xem, nhưng chưa đối chiếu được thông tin hiện tại. Mình giữ nguyên các mã đã chọn và không thay bằng sản phẩm khác.'}
