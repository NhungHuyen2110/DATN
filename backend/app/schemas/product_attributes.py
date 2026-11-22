from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from shared.verified_attributes import validate_attribute


class AttributeReviewRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    label: Literal['Audience','Style']
    canonical_id: str=Field(min_length=1,max_length=32)
    source_reference: str=Field(min_length=3,max_length=200)
    confirmed_review: Literal[True]

    @field_validator('source_reference',mode='before')
    @classmethod
    def trim_reference(cls,value):
        return value.strip() if isinstance(value,str) else value

    @model_validator(mode='after')
    def canonical_value(self):
        validate_attribute(self.label,self.canonical_id)
        return self


class PublicVerifiedAttribute(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    label: str
    canonical_id: str
    name: str
    source_reference_sha256: str


class AttributeReviewResponse(PublicVerifiedAttribute):
    id: int
    product_id: int
    source_reference: str
    reviewed_by: int
    reviewed_at: datetime
    active: bool
    version: int
    review_log: list
