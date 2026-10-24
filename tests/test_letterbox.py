import numpy as np

from detection.skin_finding_detector import letterbox_image, map_letterbox_box_to_original, xyxy_to_xywh


def test_letterbox_preserves_aspect_and_pads():
    image = np.zeros((300, 600, 3), dtype=np.uint8)
    boxed, info = letterbox_image(image, target_size=640)
    assert boxed.shape == (640, 640, 3)
    assert info.resized_width == 640 and info.resized_height == 320
    assert info.pad_left == 0 and info.pad_top == 160


def test_box_round_trip_to_original():
    image = np.zeros((300, 600, 3), dtype=np.uint8)
    _, info = letterbox_image(image, target_size=640)
    s = info.scale
    box_640 = [round(60 * s), round(30 * s + info.pad_top), round(120 * s), round(90 * s + info.pad_top)]
    mapped = map_letterbox_box_to_original(box_640, info)
    assert all(abs(a - b) <= 1 for a, b in zip(mapped, [60, 30, 120, 90], strict=True))


def test_box_is_clamped_inside_image():
    image = np.zeros((300, 600, 3), dtype=np.uint8)
    _, info = letterbox_image(image, target_size=640)
    assert map_letterbox_box_to_original([-50, 0, 700, 640], info) == [0, 0, 600, 300]


def test_xyxy_to_xywh():
    assert xyxy_to_xywh([10, 20, 30, 50]) == [10, 20, 20, 30]
