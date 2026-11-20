"""
Face Tracker & Motion Smoother Module
Detects face positions, tracks active speakers, and applies temporal smoothing (EMA)
to generate stable pan-and-scan camera trajectories for 9:16 vertical reframing.
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FaceBox:
    frame_idx: int
    timestamp: float
    x: int
    y: int
    w: int
    h: int
    center_x: float
    center_y: float
    confidence: float


class FaceTracker:
    """Detects faces in video frames and computes smooth horizontal pan positions."""

    def __init__(self, sample_interval: int = 4, smoothing_alpha: float = 0.15):
        self.sample_interval = sample_interval
        self.smoothing_alpha = smoothing_alpha
        self.cascade = self._load_cascade()

    def _load_cascade(self):
        try:
            import cv2
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if os.path.exists(cascade_path):
                return cv2.CascadeClassifier(cascade_path)
        except Exception:
            pass
        return None

    def track_video_crop_center(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        source_width: int,
        source_height: int,
        crop_width: int
    ) -> List[Tuple[float, int]]:
        """
        Samples video frames within [start_time, end_time], detects faces,
        and returns a smoothed trajectory of crop X-coordinates over time [(time, crop_x), ...].
        """
        default_x = int((source_width - crop_width) / 2)
        if self.cascade is None or not os.path.isfile(video_path):
            return [(start_time, default_x), (end_time, default_x)]

        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return [(start_time, default_x), (end_time, default_x)]

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps)

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            raw_positions: List[Tuple[float, float]] = []
            current_frame = start_frame
            smoothed_x = float(source_width / 2.0)

            while current_frame <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    break

                if (current_frame - start_frame) % self.sample_interval == 0:
                    t = current_frame / fps
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    small = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
                    faces = self.cascade.detectMultiScale(
                        small,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(30, 30)
                    )

                    if len(faces) > 0:
                        best_face = max(faces, key=lambda f: f[2] * f[3])
                        bx, by, bw, bh = [coord * 2 for coord in best_face]
                        face_center_x = bx + (bw / 2.0)
                        raw_positions.append((t, face_center_x))
                    else:
                        raw_positions.append((t, smoothed_x))

                current_frame += 1

            cap.release()

            if not raw_positions:
                return [(start_time, default_x), (end_time, default_x)]

            smoothed_trajectory: List[Tuple[float, int]] = []
            cur_smooth = raw_positions[0][1]

            for t, raw_x in raw_positions:
                cur_smooth = (self.smoothing_alpha * raw_x) + ((1.0 - self.smoothing_alpha) * cur_smooth)
                crop_x = int(cur_smooth - (crop_width / 2.0))
                crop_x = max(0, min(source_width - crop_width, crop_x))
                smoothed_trajectory.append((t, crop_x))

            return smoothed_trajectory

        except Exception as e:
            logger.warning(f"Face tracking error: {e}. Using center crop.")
            return [(start_time, default_x), (end_time, default_x)]
