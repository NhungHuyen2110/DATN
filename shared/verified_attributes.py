"""Canonical query vocabulary, never an inference that a product has a fact."""
from datetime import datetime
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
ATTRIBUTE_NAMES = {
    'Audience': {'female': 'Phái nữ', 'male': 'Phái nam', 'child_female': 'Bé gái'},
    'Style': {'elegant': 'Thanh lịch', 'minimalist': 'Tối giản', 'refined': 'Tinh tế'},
}
ATTRIBUTE_RELATIONSHIPS = {'Audience': 'SUITABLE_FOR', 'Style': 'HAS_STYLE'}
REVIEW_OWNER = 'lumiere-reviewed-attributes-v1'
CATALOG_OWNER = 'lumiere-products-v1'


def reviews_enabled():
    return os.getenv('LUMIERE_ATTRIBUTE_REVIEWS_ENABLED', 'false').lower() == 'true'


def validate_attribute(label, canonical_id):
    if label not in ATTRIBUTE_NAMES or canonical_id not in ATTRIBUTE_NAMES[label]:
        raise ValueError('Unknown reviewed attribute')
    return ATTRIBUTE_NAMES[label][canonical_id]


class PublicAttribute(BaseModel):
    """Public approval evidence excludes reviewer identity and source text."""
    model_config = ConfigDict(extra='forbid', strict=True)
    label: Literal['Audience', 'Style']
    canonical_id: str
    name: str
    source_reference_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    @model_validator(mode='after')
    def canonical_name(self):
        if self.name != validate_attribute(self.label, self.canonical_id):
            raise ValueError('Reviewed attribute name differs from canonical vocabulary')
        return self


class ProjectedAttribute(PublicAttribute):
    """Projection metadata is supplied by the active review store only."""
    review_id: StrictInt = Field(ge=1)
    review_version: StrictInt = Field(ge=1)
    reviewed_at: str = Field(max_length=64)

    @field_validator('reviewed_at')
    @classmethod
    def timestamp(cls, value):
        datetime.fromisoformat(value)
        return value


def normalize_projected_attributes(values):
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError('A bounded list of active reviewed attributes is required')
    result = [ProjectedAttribute.model_validate(value).model_dump() for value in values]
    keys = {(value['label'], value['canonical_id']) for value in result}
    if len(keys) != len(result):
        raise ValueError('Duplicate reviewed attribute')
    return sorted(result, key=lambda value: (value['label'], value['canonical_id']))
