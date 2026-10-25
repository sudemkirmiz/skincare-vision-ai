# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Long-lived services for the API process (models load once, shared by all requests)."""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from functools import cached_property
from typing import Any

from analysis.service import AnalysisService
from config import Settings
from detection.face_detector import OpenCVFaceDetector
from detection.face_landmarks import FaceLandmarkAnalyzer, mediapipe_available
from detection.skin_finding_detector import SkinFindingDetector
from history.store import HistoryStore
from preprocessing.quality_checker import ImageQualityChecker
from recommendation.catalog import Catalog, load_catalog
from services.weather import WeatherService

logger = logging.getLogger("skincare.api")
ANALYSIS_TTL_SECONDS = 60 * 60
MAX_CACHED_ANALYSES = 64


class AnalysisCache:
    """Recent analysis payloads by id, so reports, routines and saving don't re-run the models.

    In memory only: face images live here for at most an hour and are never written to disk.
    """

    def __init__(self, ttl: float = ANALYSIS_TTL_SECONDS, max_items: int = MAX_CACHED_ANALYSES, clock=time.monotonic) -> None:
        self._items: OrderedDict[str, tuple[float, str, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._ttl, self._max_items, self._clock = ttl, max_items, clock

    def put(self, profile_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._items[payload["analysis_id"]] = (self._clock(), profile_id, payload)
            self._items.move_to_end(payload["analysis_id"])
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)

    def get(self, analysis_id: str, profile_id: str) -> dict[str, Any] | None:
        """Only the profile that created an analysis can read it back."""
        with self._lock:
            entry = self._items.get(analysis_id)
            if entry is None:
                return None
            stored_at, owner, payload = entry
            if self._clock() - stored_at > self._ttl:
                del self._items[analysis_id]
                return None
            return payload if owner == profile_id else None


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.analyses = AnalysisCache()
        self._yolo_lock = threading.Lock()
        self._yolo: SkinFindingDetector | None = None
        self._catalog: tuple[float, Catalog] | None = None

    def skin_detector(self) -> SkinFindingDetector:
        with self._yolo_lock:
            if self._yolo is None:
                logger.info("Loading YOLO model from %s", self.settings.yolo_model_path)
                self._yolo = SkinFindingDetector(self.settings.yolo_model_path, self.settings.yolo_image_size, self.settings.yolo_confidence)
            return self._yolo

    @cached_property
    def landmarks(self) -> FaceLandmarkAnalyzer | None:
        if not (mediapipe_available() and self.settings.face_landmarker_path.exists()):
            logger.warning("Face landmarker unavailable; using Haar face detection")
            return None
        return FaceLandmarkAnalyzer(self.settings.face_landmarker_path)

    @cached_property
    def service(self) -> AnalysisService:
        return AnalysisService(self.settings, OpenCVFaceDetector(), ImageQualityChecker(), self.skin_detector, self.landmarks)

    @cached_property
    def store(self) -> HistoryStore:
        return HistoryStore(self.settings.history_db_path)

    @cached_property
    def weather(self) -> WeatherService:
        return WeatherService(trust_env=self.settings.vlm_trust_env_proxy)

    def catalog(self) -> Catalog:
        """Reloaded when data/products.json changes on disk."""
        path = self.settings.product_catalog_path
        mtime = path.stat().st_mtime if path.exists() else 0.0
        if self._catalog is None or self._catalog[0] != mtime:
            self._catalog = (mtime, load_catalog(path))
        return self._catalog[1]

    def close(self) -> None:
        if "landmarks" in self.__dict__ and self.landmarks is not None:
            self.landmarks.close()
