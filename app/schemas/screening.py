"""Pydantic schemas for the Screening resource."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Sex(str, Enum):
    M = "M"
    F = "F"


class ScreeningCreate(BaseModel):
    """Request body for creating a new screening."""

    site_id: str = Field(..., examples=["SITE-001"])
    candidate_initials: str = Field(..., min_length=1, max_length=4)
    age: int = Field(..., ge=0, le=50)
    sex: Sex
    diagnosis: str = Field(..., examples=["Type 2 Diabetes"])
    medications: list[str] = Field(default_factory=list)
    is_pregnant: bool = False
    has_liver_disease: bool = False
    in_other_trial: bool = False


class ScreeningResponse(BaseModel):
    """What we return after creating or fetching a screening."""

    id: UUID
    site_id: str
    candidate_initials: str
    age: int
    sex: Sex
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class EligibilityUpdate(BaseModel):
    eligible: bool
    failed_criteria: list[str] = Field(default_factory=list)
