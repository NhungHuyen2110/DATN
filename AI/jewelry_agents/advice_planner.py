"""Semantic shopping intent, using the same local pinned encoder as retrieval.

Occasion describes the customer's request, never a verified product attribute.
No names, prices, gender, product occasions or ranking are generated here.
"""
from .entity_linking import cosine
import threading
from weakref import WeakKeyDictionary
from dataclasses import dataclass, field


@dataclass(frozen=True, repr=False)
class RequestEmbedding:
    """One-request vector, bound to the exact text and encoder; never cached."""
    query: str = field(repr=False)
    encoder: object = field(repr=False)
    vector: tuple = field(repr=False)

    def matches(self, query, encoder):
        return self.query == query and self.encoder is encoder

_anchors=WeakKeyDictionary()
_anchor_lock=threading.Lock()

PROTOTYPES = {
    'gift_advice': [
        'Lễ tình nhân nên tặng món trang sức gì cho người yêu?',
        'Tôi muốn chọn quà trang sức cho một dịp đặc biệt, hãy tư vấn giúp tôi.',
        'Mua quà sinh nhật hoặc kỷ niệm cho người thương nên chọn thế nào?',
    ],
    'product_search': [
        'Tìm nhẫn kim cương theo mức giá và tồn kho.',
        'Cho tôi top sản phẩm cùng loại đá hoặc cùng chất liệu.',
        'Tra cứu sản phẩm theo mã SKU và tên.',
    ],
    'other': ['Xin chào, cảm ơn bạn.', 'Tra cứu đơn hàng, doanh thu và thanh toán.'],
}

GIFT_INTRO = (
    'Nếu chọn trang sức làm quà, bạn có thể cân nhắc sở thích của người nhận, '
    'ngân sách và kích cỡ. Dây chuyền hoặc bông tai là những lựa chọn để tham khảo '
    'khi chưa biết cỡ nhẫn; với nhẫn, nên xác nhận kích cỡ trước. '
    'Các sản phẩm bên dưới được tìm theo ý nghĩa yêu cầu và kiểm tra giá, tồn kho hiện tại. '
    'Đây là gợi ý lựa chọn quà, không phải chứng nhận sản phẩm dành riêng cho một dịp hay đối tượng. '
    'Bạn cho tôi biết ngân sách, loại trang sức hoặc chất liệu người nhận thích để thu hẹp nhé.'
)


def plan_advice(query, encoder, threshold=.45, margin=.04, *, include_embedding=False):
    texts=[text for group in PROTOTYPES.values() for text in group]
    # Only public fixed prototypes are cached, never user messages/vectors.
    # The same pinned encoder stays the cache key; replacing it invalidates data.
    with _anchor_lock:
        cached=_anchors.get(encoder)
        if cached is None or cached[0]!=tuple(texts):
            anchors=encoder.encode(texts)
            if len(anchors)!=len(texts):
                raise ValueError('Invalid prototype encoder output')
            _anchors[encoder]=(tuple(texts),anchors)
        else:
            anchors=cached[1]
    query_vectors=encoder.encode([query])
    if len(query_vectors)!=1:
        raise ValueError('Invalid query encoder output')
    vectors=[query_vectors[0],*anchors]
    offset=1
    scores={}
    for label,group in PROTOTYPES.items():
        scores[label]=max(cosine(vectors[0],vector) for vector in vectors[offset:offset+len(group)])
        offset+=len(group)
    ranked=sorted(scores,key=lambda label:(-scores[label],label))
    winner=ranked[0]
    accepted=scores[winner]>=threshold and scores[winner]-scores[ranked[1]]>=margin
    result = {'intent':winner if accepted else 'product_search',
              'method':'local_embedding_prototypes','accepted':accepted,'scores':scores}
    if include_embedding:
        result['_request_embedding'] = RequestEmbedding(query, encoder, tuple(float(x) for x in vectors[0]))
    return result
