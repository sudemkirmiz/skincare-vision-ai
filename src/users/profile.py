"""User profile collected at onboarding: identity, consent and the skin profile.

Data minimisation: only the display name (can be a nickname) and the address form are
ever sent to a VLM. Surname, age, pregnancy and allergies stay local.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from recommendation.profile import SkinProfile

# Only used to decide whether the pregnancy question applies; never sent to a VLM.
GENDERS = {"female": "Kadın", "male": "Erkek", "other": "Diğer / belirtmek istemiyorum"}
ADDRESS_FORMS = {"siz": "Siz (resmi)", "sen": "Sen (samimi)"}
MAX_NAME_LENGTH = 40

# Mini quiz for users who don't know their skin type.
QUIZ = {
    "t_zone": ("Yüzünüzü yıkadıktan 2-3 saat sonra alnınız ve burnunuz nasıl?", {"oily": "Parlak / yağlı", "normal": "Normal", "dry": "Gergin / kuru"}),
    "cheeks": ("Aynı anda yanaklarınız nasıl?", {"oily": "Parlak / yağlı", "normal": "Normal", "dry": "Gergin / pul pul"}),
    "blotting": ("Gün içinde yüzünüzdeki yağı silme ihtiyacı duyar mısınız?", {"often": "Sık sık", "sometimes": "Bazen", "never": "Hiç"}),
}

CONSENT_TEXT = (
    "Yüklediğim yüz fotoğrafının yalnızca cilt bakımı ön değerlendirmesi için işlenmesini kabul ediyorum. "
    "Fotoğraf analizden sonra saklanmaz; yorum için seçili yapay zekâ servisine (ör. Google Gemini) yüz kırpımı ve "
    "sadece hitap adım gönderilir. Bu bir tıbbi teşhis değildir."
)
REQUIRED_FIELDS = ("display_name", "age_group", "gender", "skin_type", "sensitivity", "pregnancy", "consent")
OPTIONAL_FIELDS = ("last_name", "address_form", "concerns", "current_actives", "allergies", "budget", "routine_size", "makeup", "sun_exposure")


@dataclass
class UserProfile:
    display_name: str
    skin: SkinProfile = field(default_factory=SkinProfile)
    last_name: str = ""
    address_form: str = "siz"
    gender: str = "other"
    consent_at: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = ""
    # Which optional questions the user actually answered (defaults alone don't count as answers).
    answered: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.display_name = clean_name(self.display_name)
        self.last_name = clean_name(self.last_name)
        if self.gender not in GENDERS:
            self.gender = "other"
        if self.address_form not in ADDRESS_FORMS:
            self.address_form = "siz"
        if isinstance(self.skin, dict):
            self.skin = SkinProfile(**self.skin)
        self.answered = [a for a in dict.fromkeys(self.answered) if a in OPTIONAL_FIELDS]

    @property
    def full_name(self) -> str:
        return f"{self.display_name} {self.last_name}".strip()

    @property
    def has_consent(self) -> bool:
        return bool(self.consent_at)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        known = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        return cls(**known)

    def vlm_personalization(self) -> dict[str, str]:
        return {"hitap_adi": self.display_name, "hitap": self.address_form}


def clean_name(value: str) -> str:
    """Letters, spaces, apostrophes and hyphens only; collapses whitespace."""
    value = unicodedata.normalize("NFC", value or "")
    value = re.sub(r"[^\w\s'\-]|[\d_]", "", value)
    return " ".join(value.split())[:MAX_NAME_LENGTH]


def pregnancy_question_applies(gender: str | None) -> bool:
    return gender in {"female", "other"}


def validate_required(display_name: str, age_group: str | None, skin_type: str | None, sensitivity: str | None,
                      pregnancy: str | None, consent: bool, gender: str | None = "other") -> list[str]:
    errors = []
    if len(clean_name(display_name)) < 2:
        errors.append("Adınızı (veya takma adınızı) yazın; en az 2 harf.")
    if not age_group:
        errors.append("Yaş aralığınızı seçin.")
    if not skin_type:
        errors.append("Cilt tipinizi seçin ya da “Bilmiyorum” deyip kısa testi doldurun.")
    if not sensitivity:
        errors.append("Cildinizin hassasiyet durumunu seçin.")
    if not gender:
        errors.append("Cinsiyetinizi seçin (“Diğer / belirtmek istemiyorum” da seçebilirsiniz).")
    if pregnancy_question_applies(gender) and not pregnancy:
        errors.append("Hamilelik/emzirme sorusunu yanıtlayın (“Belirtmek istemiyorum” da seçebilirsiniz).")
    if not consent:
        errors.append("Devam etmek için fotoğraf işleme onayını işaretleyin.")
    return errors


def infer_skin_type(t_zone: str | None, cheeks: str | None, blotting: str | None) -> str | None:
    """Simple, explainable mapping from the three quiz answers; None until all are answered."""
    if not (t_zone and cheeks and blotting):
        return None
    if t_zone == "oily" and cheeks == "oily":
        return "oily"
    if t_zone == "oily":
        return "combination"
    if t_zone == "dry" or cheeks == "dry":
        # Frequent blotting with dry cheeks still points to combination skin.
        return "combination" if blotting == "often" and t_zone != "dry" else "dry"
    if blotting == "often":
        return "combination"
    return "normal"


def completeness(profile: UserProfile) -> float:
    """Share of all questions answered (required ones always count once saved)."""
    answered = len(REQUIRED_FIELDS) + len(profile.answered)
    return round(answered / (len(REQUIRED_FIELDS) + len(OPTIONAL_FIELDS)), 2)


def profile_photo_mismatches(profile: SkinProfile, skin_metrics: dict[str, Any] | None) -> list[str]:
    """Gentle hints when the photo contradicts the questionnaire (people often misjudge their skin type)."""
    if not skin_metrics or not skin_metrics.get("available"):
        return []
    scores = skin_metrics.get("scores", {})
    regions = skin_metrics.get("regions", {})
    t_zone_shine = [regions[key]["shine"] for key in ("forehead", "nose") if key in regions]
    hints = []
    shine = scores.get("shine")
    if profile.skin_type in {"dry", "normal"} and shine is not None and (shine < 45 or (t_zone_shine and min(t_zone_shine) < 35)):
        hints.append("Profilinizde kuru/normal cilt seçtiniz ama fotoğrafta T-bölgesinde belirgin parlama var; cildiniz karma olabilir. "
                     "Işık da etkili olabilir; emin değilseniz profilinizdeki mini testi doldurun.")
    if profile.skin_type == "oily" and shine is not None and shine >= 92 and (not t_zone_shine or min(t_zone_shine) >= 90):
        hints.append("Profilinizde yağlı cilt seçtiniz ama fotoğrafta parlama görünmüyor. Yüzünüzü yeni yıkadıysanız normaldir; "
                     "gün ortasında çekilen bir fotoğraf daha doğru sonuç verir.")
    redness = scores.get("redness")
    if profile.sensitivity == "no" and redness is not None and redness < 35:
        hints.append("Fotoğrafta yaygın kızarıklık görünüyor; cildiniz düşündüğünüzden daha hassas olabilir. "
                     "Yeni aktiflere yavaş başlamanız iyi olur.")
    return hints
