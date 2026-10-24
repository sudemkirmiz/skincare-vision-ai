"""Request bodies. Responses are plain dicts built from the existing domain objects."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    """Reject unknown fields and normalise surrounding whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkinProfileIn(RequestModel):
    skin_type: str | None = Field(default=None, max_length=24)
    sensitivity: str | None = Field(default=None, max_length=24)
    age_group: str | None = Field(default=None, max_length=24)
    pregnancy: str | None = Field(default=None, max_length=24)  # "no" | "yes" | "undisclosed"
    concerns: list[str] = Field(default_factory=list, max_length=20)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    current_actives: list[str] = Field(default_factory=list, max_length=20)
    budget: str = Field(default="mid", max_length=24)
    routine_size: str = Field(default="standard", max_length=24)
    makeup: str = Field(default="unknown", max_length=24)
    sun_exposure: str = Field(default="unknown", max_length=24)


class ProfileIn(RequestModel):
    display_name: str = Field(default="", max_length=80)
    last_name: str = Field(default="", max_length=80)
    gender: str | None = Field(default=None, max_length=24)
    address_form: str = Field(default="siz", max_length=12)
    consent: bool = False
    answered: list[str] = Field(default_factory=list, max_length=20)
    skin: SkinProfileIn = Field(default_factory=SkinProfileIn)


class QuizIn(RequestModel):
    t_zone: str | None = Field(default=None, max_length=16)
    cheeks: str | None = Field(default=None, max_length=16)
    blotting: str | None = Field(default=None, max_length=16)


class SaveAnalysisIn(RequestModel):
    profile_id: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)
    keep_thumbnail: bool = True


class EventIn(RequestModel):
    kind: str = Field(min_length=1, max_length=32)
    date: str | None = Field(default=None, max_length=10)
    note: str = Field(default="", max_length=200)


class ProductCheckIn(RequestModel):
    profile_id: str = Field(min_length=1, max_length=64)
    inci_text: str = Field(min_length=1, max_length=8000)
    analysis_id: str | None = Field(default=None, max_length=64)


class JournalIn(RequestModel):
    am_done: bool | None = None
    pm_done: bool | None = None
    skin_feel: int | None = Field(default=None, ge=1, le=5)
    triggers: list[str] = Field(default_factory=list, max_length=20)
    symptoms: list[str] = Field(default_factory=list, max_length=10)
    actives: list[str] = Field(default_factory=list, max_length=8)
    note: str = Field(default="", max_length=200)


class ShelfItemIn(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    usage: str = Field(min_length=1, max_length=40)
    inci: str = Field(default="", max_length=8000)
    opened_at: str | None = Field(default=None, max_length=10)
    pao_months: int | None = Field(default=None, ge=1, le=60)


class ChatMessage(RequestModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class CoachWeather(RequestModel):
    uv_max: float | None = Field(default=None, ge=0, le=20)
    temperature: float | None = Field(default=None, ge=-60, le=60)
    humidity: float | None = Field(default=None, ge=0, le=100)


class CoachIn(RequestModel):
    profile_id: str = Field(min_length=1, max_length=64)
    provider: str = Field(default="Gemini", max_length=32)
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    weather: CoachWeather | None = None
