import numpy as np
import pytest

from analysis.capture_guide import assess_frame
from detection.face_landmarks import FaceLandmarkResult, HeadPose

WIDTH, HEIGHT = 360, 480


class FakeLandmarks:
    def __init__(self, box=None, pose=(0, 0, 0), faces=1):
        self.box, self.pose, self.faces = box, pose, faces

    def detect(self, _image):
        if self.box is None:
            return None
        return FaceLandmarkResult(np.zeros((478, 2), np.float32), self.box, HeadPose(*self.pose), self.faces)


def frame(level=140, noise=30):
    rng = np.random.default_rng(1)
    return np.clip(level + rng.normal(0, noise, (HEIGHT, WIDTH, 3)), 0, 255).astype(np.uint8)


CENTERED = (90, 120, 180, 240)  # half the frame width, centred


def test_good_front_frame_is_ready():
    result = assess_frame(frame(), FakeLandmarks(CENTERED))
    assert result["ok"] and result["face"] and result["box"] == [0.25, 0.25, 0.5, 0.5]


@pytest.mark.parametrize(("landmarks", "image", "message"), [
    (FakeLandmarks(None), frame(), "çerçevenin içine"),
    (FakeLandmarks(CENTERED, faces=2), frame(), "yalnızca bir yüz"),
    (FakeLandmarks((150, 200, 60, 80)), frame(), "yaklaşın"),
    (FakeLandmarks((5, 5, 350, 470)), frame(), "uzaklaşın"),
    (FakeLandmarks((0, 120, 180, 240)), frame(), "ortasına"),
    (FakeLandmarks(CENTERED, pose=(20, 0, 0)), frame(), "kameraya bakın"),
    (FakeLandmarks(CENTERED, pose=(0, 0, 15)), frame(), "dik tutun"),
    (FakeLandmarks(CENTERED), frame(level=40, noise=10), "karanlık"),
    (FakeLandmarks(CENTERED), frame(level=140, noise=0), "bulanık"),
])
def test_first_problem_is_reported(landmarks, image, message):
    result = assess_frame(image, landmarks)
    assert not result["ok"] and message in result["message"]


def test_side_view_needs_a_turn_to_the_other_side():
    assert assess_frame(frame(), FakeLandmarks(CENTERED, pose=(25, 0, 0)), "side")["ok"]
    assert "bir yana" in assess_frame(frame(), FakeLandmarks(CENTERED, pose=(4, 0, 0)), "side")["message"]
    assert "diğer yana" in assess_frame(frame(), FakeLandmarks(CENTERED, pose=(25, 0, 0)), "side", avoid_sign=1)["message"]
    assert assess_frame(frame(), FakeLandmarks(CENTERED, pose=(-25, 0, 0)), "side", avoid_sign=1)["ok"]


def test_without_face_model_only_lighting_is_checked():
    result = assess_frame(frame(), None)
    assert result["ok"] and not result["guide_available"]
    assert not assess_frame(frame(level=30, noise=5), None)["ok"]
