import base64
from io import BytesIO

import pytest
from PIL import Image

pypdf = pytest.importorskip("pypdf")

from recommendation.engine import build_routine  # noqa: E402
from recommendation.profile import SkinProfile  # noqa: E402
from report.pdf_report import _text, build_pdf_report  # noqa: E402
from users.profile import UserProfile  # noqa: E402


def data_uri(color=(200, 160, 140), size=(300, 380)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def payload(observations=None, metrics=True):
    scores = {"spots": 75, "redness": 62, "tone": 63, "shine": 80, "texture": None}
    return {
        "analysis_id": "abc123",
        "created_at": "2026-10-24 22:00",
        "original_uri": data_uri(),
        "marked_uri": data_uri((180, 140, 120)),
        "result": {
            "image_quality": {"status": "good", "notes": "Fotoğraf uygun görünüyor."},
            "visible_observations": observations if observations is not None else ["Ayşe, sağ yanağınızda hafif kızarıklık var."],
            "care_suggestions": ["Nazik bir temizleyici kullanın."],
            "disclaimer": "Bu çıktı tıbbi tanı değildir.",
        },
        "skin_metrics": {
            "available": True, "overall_score": 67, "scores": scores,
            "score_labels": {"spots": "Nokta yoğunluğu", "redness": "Kızarıklık dengesi", "tone": "Ton eşitliği", "shine": "Parlama kontrolü", "texture": "Doku pürüzsüzlüğü"},
            "skin_tone": {"ita": 46.7, "category": "Açık"}, "spot_counts": {"total": 11}, "regions": {"forehead": {"redness": 65, "tone": 75}},
        } if metrics else {"available": False},
        "region_summary": {"most_affected_name": "Sağ yanak", "regions": [
            {"key": "forehead", "name": "Alın", "count": 3, "density": 0.81, "visible": True},
            {"key": "chin", "name": "Çene", "count": 0, "density": None, "visible": False},
        ]},
        "vlm_output": {"provider": "Gemini", "model": "gemini-3.5-flash"},
    }


def extract(pdf: bytes) -> tuple[str, pypdf.PdfReader]:
    reader = pypdf.PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages), reader


def test_full_report_has_turkish_text_two_pages_and_embedded_font():
    profile = UserProfile(display_name="Ayşe", last_name="Yılmaz", skin=SkinProfile(skin_type="dry", concerns=["spots"]))
    routine = build_routine(payload()["skin_metrics"], profile.skin)
    comparison = {"summary": ["Genel skor 41 puan yükseldi (26 → 67)."], "scores": [
        {"label": "Nokta yoğunluğu", "before": 19, "after": 75, "delta": 56, "direction": "better"}], "comparability_notes": ["Benzer ışık önerilir."]}
    pdf = build_pdf_report(payload(), profile, routine, ["Profilinizde kuru cilt seçtiniz."], comparison, "24.10.2026 18:30")
    text, reader = extract(pdf)
    assert pdf.startswith(b"%PDF") and len(reader.pages) == 2
    for needle in ("Ayşe Yılmaz", "Cilt Skoru", "Bölgesel Dağılım", "Kişisel Bakım Rutini", "Haftalık akşam planı", "Önceki Kayda Göre Değişim", "ölçülmedi", "Sayfa 2"):
        assert needle in text, needle
    assert "26 » 67" in text and "→" not in text
    fonts = {str(font) for page in reader.pages for font in page["/Resources"]["/Font"].values() for font in [font.get_object()["/BaseFont"]]}
    assert any("Poppins" in font for font in fonts)
    assert reader.metadata.title == "Cilt Raporu - Ayşe Yılmaz"


def test_untrusted_text_cannot_break_layout():
    pdf = build_pdf_report(payload(observations=["<b>kalın</b> & <script>alert(1)</script> 💡 ▲"]), None, None)
    text, _ = extract(pdf)
    assert "<script>alert(1)</script>" in text and "💡" not in text


def test_report_without_metrics_or_images_still_builds():
    data = payload(observations=[], metrics=False)
    data["result"]["care_suggestions"] = []
    data["original_uri"] = None
    data.pop("region_summary")
    text, reader = extract(build_pdf_report(data))
    assert "hesaplanamadı" in text and "yorumu üretilmedi" in text and len(reader.pages) >= 1


def test_text_sanitiser():
    assert _text("a → b") == "a » b"
    assert _text("x < y & z") == "x &lt; y &amp; z"
    assert _text(None) == "–"


def test_report_filename_is_readable_and_portable():
    from report.filenames import report_filename, safe_part

    assert report_filename("Ayşe Yılmaz", "2026-10-24 22:01", "pdf") == "Cilt_Raporu_Ayse_Yilmaz_24-10-2026.pdf"
    assert report_filename("Çağrı Öztürk-Işık", "2026-10-24T09:00:00", ".json") == "Cilt_Raporu_Cagri_Ozturk_Isik_24-10-2026.json"
    assert report_filename("", "2026-01-02 10:00", "txt") == "Cilt_Raporu_02-01-2026.txt"
    assert report_filename("Ali", None, "csv", prefix="Cilt_Gecmisi").startswith("Cilt_Gecmisi_Ali_")
    assert safe_part('../../etc/passwd "x"') == "etc_passwd_x"
