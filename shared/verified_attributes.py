"""Canonical query vocabulary, never an inference that a product has a fact."""
ATTRIBUTE_NAMES = {
    'Audience': {'female': 'Phái nữ', 'male': 'Phái nam', 'child_female': 'Bé gái'},
    'Style': {'elegant': 'Thanh lịch', 'minimalist': 'Tối giản', 'refined': 'Tinh tế'},
}
ATTRIBUTE_RELATIONSHIPS = {'Audience': 'SUITABLE_FOR', 'Style': 'HAS_STYLE'}
REVIEW_OWNER = 'lumiere-reviewed-attributes-v1'


def validate_attribute(label, canonical_id):
    if label not in ATTRIBUTE_NAMES or canonical_id not in ATTRIBUTE_NAMES[label]:
        raise ValueError('Unknown reviewed attribute')
    return ATTRIBUTE_NAMES[label][canonical_id]
