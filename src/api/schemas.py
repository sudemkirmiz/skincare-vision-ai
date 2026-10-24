"""Request bodies. Responses are plain dicts built from the existing domain objects."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SkinProfileIn(BaseModel):
    skin_type: str | None = None
    sensitivity: str | None = None
    age_group: str | None = None
    pregnancy: str | None = None  # "no" | "yes" | "undisclosed"
    concerns: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    current_actives: list[str] = Field(default_factory=list)
    budget: str = "mid"
    routine_size: str = "standard"
    makeup: str = "unknown"
    sun_exposure: str = "unknown"


class ProfileIn(BaseModel):
    display_name: str = ""
    last_name: str = ""
    gender: str | None = None
    address_form: str = "siz"
    consent: bool = False
    answered: list[str] = Field(default_factory=list)
    skin: SkinProfileIn = Field(default_factory=SkinProfileIn)


class QuizIn(BaseModel):
    t_zone: str | None = None
    cheeks: str | None = None
    blotting: str | None = None


class SaveAnalysisIn(BaseModel):
    profile_id: str
    note: str = ""
    keep_thumbnail: bool = True


class EventIn(BaseModel):
    kind: str
    date: str | None = None
    note: str = ""


class ProductCheckIn(BaseModel):
    profile_id: str
    inci_text: str = Field(min_length=1, max_length=8000)
    analysis_id: str | None = None


class JournalIn(BaseModel):
    am_done: bool | None = None
    pm_done: bool | None = None
    skin_feel: int | None = Field(default=None, ge=1, le=5)
    triggers: list[str] = Field(default_factory=list, max_length=20)
    symptoms: list[str] = Field(default_factory=list, max_length=10)
    actives: list[str] = Field(default_factory=list, max_length=8)
    note: str = Field(default="", max_length=200)


class ShelfItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str
    usage: str
    inci: str = Field(default="", max_length=8000)
    opened_at: str | None = None
    pao_months: int | None = Field(default=None, ge=1, le=60)


class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class CoachWeather(BaseModel):
    uv_max: float | None = Field(default=None, ge=0, le=20)
    temperature: float | None = Field(default=None, ge=-60, le=60)
    humidity: float | None = Field(default=None, ge=0, le=100)


class CoachIn(BaseModel):
    profile_id: str
    provider: str = "Gemini"
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    weather: CoachWeather | None = None
