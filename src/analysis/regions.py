"""Facial region masks from MediaPipe's 478-point mesh.

Regions are derived geometrically in a roll-aligned face frame instead of from
hand-picked mesh polygons, so they stay sensible on tilted or partially cropped faces.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

# Landmark index sets from mediapipe FaceLandmarksConnections (copied so this module has no mediapipe import).
FACE_OVAL_PATH = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
                  152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
LEFT_EYE = [249, 263, 362, 373, 374, 380, 381, 382, 384, 385, 386, 387, 388, 390, 398, 466]
RIGHT_EYE = [7, 33, 133, 144, 145, 153, 154, 155, 157, 158, 159, 160, 161, 163, 173, 246]
LEFT_EYEBROW = [276, 282, 283, 285, 293, 295, 296, 300, 334, 336]
RIGHT_EYEBROW = [46, 52, 53, 55, 63, 65, 66, 70, 105, 107]
LIPS = [0, 13, 14, 17, 37, 39, 40, 61, 78, 80, 81, 82, 84, 87, 88, 91, 95, 146, 178, 181, 185, 191,
        267, 269, 270, 291, 308, 310, 311, 312, 314, 317, 318, 321, 324, 375, 402, 405, 409, 415]
NOSE = [1, 2, 4, 5, 6, 19, 45, 48, 64, 94, 97, 98, 115, 168, 195, 197, 220, 275, 278, 294, 326, 327, 344, 440]
NOSE_BRIDGE = 168
CHIN_TIP = 152

# id -> (key, Turkish name, BGR colour). Left/right are as seen in the photo.
REGIONS: dict[int, tuple[str, str, tuple[int, int, int]]] = {
    1: ("forehead", "Alın", (214, 160, 92)),
    2: ("nose", "Burun", (92, 184, 236)),
    3: ("left_cheek", "Sol yanak", (126, 196, 120)),
    4: ("right_cheek", "Sağ yanak", (176, 132, 206)),
    5: ("chin", "Çene", (108, 128, 230)),
}
REGION_NAMES = {key: name for key, name, _ in REGIONS.values()}
REGION_KEYS = {region_id: key for region_id, (key, _, _) in REGIONS.items()}
ZONES = {"t_zone": ("T-bölgesi", ("forehead", "nose")), "u_zone": ("U-bölgesi", ("left_cheek", "right_cheek", "chin"))}
MIN_VISIBLE_RATIO = 0.03
FOREHEAD_EXTENSION = 1.3


@dataclass
class RegionMap:
    labels: np.ndarray  # int8 (H, W): 0 = not analysed skin, otherwise a REGIONS id
    face_mask: np.ndarray  # bool (H, W): inside the face oval

    def mask(self, key: str) -> np.ndarray:
        region_id = next(i for i, (k, _, _) in REGIONS.items() if k == key)
        return self.labels == region_id

    def region_at(self, x: float, y: float) -> str | None:
        height, width = self.labels.shape
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < width and 0 <= yi < height):
            return None
        region_id = int(self.labels[yi, xi])
        if region_id:
            return REGION_KEYS[region_id]
        # Spots right on an excluded edge (brow, lip line) snap to the nearest region nearby.
        radius = max(3, int(min(height, width) * 0.02))
        window = self.labels[max(0, yi - radius): yi + radius + 1, max(0, xi - radius): xi + radius + 1]
        values, counts = np.unique(window[window > 0], return_counts=True)
        return REGION_KEYS[int(values[np.argmax(counts)])] if len(values) else None


def _hull_mask(points: np.ndarray, shape: tuple[int, int], dilate: int = 0) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    hull = cv2.convexHull(np.round(points).astype(np.int32))
    cv2.fillConvexPoly(mask, hull, 1)
    if dilate > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate + 1, 2 * dilate + 1))
        mask = cv2.dilate(mask, kernel)
    return mask.astype(bool)


def build_region_map(landmarks: np.ndarray, shape: tuple[int, int]) -> RegionMap:
    """landmarks: (478, 2) pixel coordinates in the same frame as `shape` (H, W)."""
    height, width = shape[:2]
    points = np.asarray(landmarks, dtype=np.float32)

    left_eye_center = points[LEFT_EYE].mean(axis=0)
    right_eye_center = points[RIGHT_EYE].mean(axis=0)
    eye_distance = float(np.linalg.norm(left_eye_center - right_eye_center)) or 1.0

    excluded = np.zeros((height, width), dtype=bool)
    for indices, factor in ((LEFT_EYE, 0.14), (RIGHT_EYE, 0.14), (LEFT_EYEBROW, 0.06), (RIGHT_EYEBROW, 0.06), (LIPS, 0.06)):
        excluded |= _hull_mask(points[indices], (height, width), dilate=max(1, int(eye_distance * factor)))

    # Roll-aligned coordinates: x' along the eye line, y' downwards perpendicular to it.
    vector = left_eye_center - right_eye_center
    if vector[0] < 0:
        vector = -vector
    angle = math.atan2(float(vector[1]), float(vector[0]))
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    center = (left_eye_center + right_eye_center) / 2

    def align(xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dx, dy = xy[..., 0] - center[0], xy[..., 1] - center[1]
        return dx * cos_a + dy * sin_a, -dx * sin_a + dy * cos_a

    def unalign(x_aligned: np.ndarray, y_aligned: np.ndarray) -> np.ndarray:
        return np.stack([center[0] + x_aligned * cos_a - y_aligned * sin_a, center[1] + x_aligned * sin_a + y_aligned * cos_a], axis=-1)

    # MediaPipe's face oval stops well below the hairline; stretch its upper half (above the
    # eye line) so the whole forehead is analysed.
    oval_x, oval_y = align(points[FACE_OVAL_PATH])
    oval_y = np.where(oval_y < 0, oval_y * FOREHEAD_EXTENSION, oval_y)
    face_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(face_mask, [np.round(unalign(oval_x, oval_y)).astype(np.int32)], 1)
    face_mask = face_mask.astype(bool)

    grid_x, grid_y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    pixel_x, pixel_y = align(np.stack([grid_x, grid_y], axis=-1))

    _, brow_y = align(points[LEFT_EYEBROW + RIGHT_EYEBROW])
    _, lip_y = align(points[LIPS])
    forehead_limit = float(brow_y.max())
    chin_limit = float(lip_y.max()) + 0.05 * eye_distance

    # Facial midline from the nose bridge to the chin tip, as x' = a * y' + b.
    bridge_x, bridge_y = align(points[NOSE_BRIDGE])
    chin_x, chin_y = align(points[CHIN_TIP])
    slope = float((chin_x - bridge_x) / (chin_y - bridge_y)) if abs(float(chin_y - bridge_y)) > 1e-3 else 0.0
    midline_x = bridge_x + slope * (pixel_y - bridge_y)

    nose_mask = _hull_mask(points[NOSE], (height, width), dilate=max(1, int(eye_distance * 0.04)))

    skin = face_mask & ~excluded
    labels = np.zeros((height, width), dtype=np.int8)
    forehead = skin & (pixel_y < forehead_limit)
    chin = skin & (pixel_y > chin_limit)
    nose = skin & nose_mask & ~forehead & ~chin
    cheeks = skin & ~forehead & ~chin & ~nose
    # Left/right as seen in the image (x grows to the right in the aligned frame too).
    labels[forehead] = 1
    labels[nose] = 2
    labels[cheeks & (pixel_x < midline_x)] = 3
    labels[cheeks & (pixel_x >= midline_x)] = 4
    labels[chin] = 5
    return RegionMap(labels=labels, face_mask=face_mask)


def summarize_regions(region_map: RegionMap, finding_boxes: list[list[int]]) -> dict:
    """Count findings per region and express density relative to visible skin area."""
    total_area = int((region_map.labels > 0).sum()) or 1
    assignments = [region_map.region_at((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in finding_boxes]

    regions = []
    for region_id, (key, name, color) in REGIONS.items():
        area_ratio = float((region_map.labels == region_id).sum()) / total_area
        count = sum(1 for assigned in assignments if assigned == key)
        visible = area_ratio >= MIN_VISIBLE_RATIO
        regions.append({
            "key": key,
            "name": name,
            "color": f"#{color[2]:02X}{color[1]:02X}{color[0]:02X}",
            "count": count,
            "area_ratio": round(area_ratio, 3),
            # spots per 10% of visible skin: comparable between regions of different size
            "density": round(count / (area_ratio * 10), 2) if visible else None,
            "visible": visible,
        })

    by_key = {region["key"]: region for region in regions}
    zones = {}
    for zone_key, (zone_name, members) in ZONES.items():
        count = sum(by_key[member]["count"] for member in members)
        area_ratio = sum(by_key[member]["area_ratio"] for member in members)
        zones[zone_key] = {
            "name": zone_name,
            "count": count,
            "density": round(count / (area_ratio * 10), 2) if area_ratio >= MIN_VISIBLE_RATIO else None,
        }

    ranked = [region for region in regions if region["visible"] and region["count"] > 0]
    ranked.sort(key=lambda region: (region["density"] or 0, region["count"]), reverse=True)
    return {
        "regions": regions,
        "zones": zones,
        "unassigned": sum(1 for assigned in assignments if assigned is None),
        "most_affected": ranked[0]["key"] if ranked else None,
        "finding_regions": assignments,
    }


def draw_region_overlay(image: np.ndarray, region_map: RegionMap, alpha: float = 0.07) -> np.ndarray:
    output = image.copy()
    tint = image.copy()
    for region_id, (_, _, color) in REGIONS.items():
        tint[region_map.labels == region_id] = color
    analysed = region_map.labels > 0
    output[analysed] = cv2.addWeighted(image, 1 - alpha, tint, alpha, 0)[analysed]

    # Very light tint + contours: a strong fill hid the redness the user actually wants to see.
    thickness = max(2, round(min(image.shape[:2]) / 300))
    for region_id, (_, _, color) in REGIONS.items():
        mask = (region_map.labels == region_id).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(output, contours, -1, color, thickness, cv2.LINE_AA)
    return output
