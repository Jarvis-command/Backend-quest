"""Pydantic schemas for Site resource"""

from pydantic import BaseModel


class SiteResponse(BaseModel):
    id: str
    name: str
    active: bool

    model_config = {"from_attributes": True}
