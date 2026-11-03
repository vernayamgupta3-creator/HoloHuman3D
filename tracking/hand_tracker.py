import time
from pathlib import Path

import cv2
import mediapipe as mp


class HandTracker:

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17)
    ]

    def __init__(self):

        self.model_path = (
            Path(__file__).parent.parent
            / "assets"
            / "hand_landmarker.task"
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Hand model not found: {self.model_path}"
            )

        self.BaseOptions = mp.tasks.BaseOptions
        self.HandLandmarker = mp.tasks.vision.HandLandmarker
        self.HandLandmarkerOptions = (
            mp.tasks.vision.HandLandmarkerOptions
        )
        self.RunningMode = mp.tasks.vision.RunningMode

        options = self.HandLandmarkerOptions(
            base_options=self.BaseOptions(
                model_asset_path=str(self.model_path)
            ),
            running_mode=self.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6
        )

        self.tracker = (
            self.HandLandmarker.create_from_options(options)
        )

        self.start_time = time.monotonic()
        self.last_timestamp = -1

        # Separate pinch state for each hand.
        self.pinch_states = {
            "Left": False,
            "Right": False
        }

        # Per-hand pinch stabilization state.
        self.pinch_ratios = {"Left": None, "Right": None}
        self.pinch_candidates = {"Left": 0, "Right": 0}


    def distance(self, p1, p2):

        return (
            (p1.x - p2.x) ** 2
            + (p1.y - p2.y) ** 2
        ) ** 0.5

    def get_palm_center(self, landmarks):

        points = [
            landmarks[0],
            landmarks[5],
            landmarks[9],
            landmarks[13],
            landmarks[17]
        ]

        return {
            "x": sum(p.x for p in points) / len(points),
            "y": sum(p.y for p in points) / len(points)
        }

    def get_hand_measurements(self, landmarks):

        # Measure finger separation relative to palm size.
        # This makes zoom less dependent on camera distance.

        palm_width = self.distance(
            landmarks[5],
            landmarks[17]
        )

        pinch_distance = self.distance(
            landmarks[4],
            landmarks[8]
        )

        if palm_width < 0.001:
            palm_width = 0.001

        pinch_ratio = pinch_distance / palm_width

        return {
            "pinch_distance": pinch_distance,
            "palm_width": palm_width,
            "pinch_ratio": pinch_ratio
        }

    def classify_gesture(self, landmarks, side):

        measurements = self.get_hand_measurements(
            landmarks
        )

        ratio = measurements["pinch_ratio"]

        # Hysteresis prevents rapid PINCH/OPEN switching.
        currently_pinching = self.pinch_states[side]

        # More forgiving pinch thresholds.
        # Enter pinch at 55%; release at 70%.
        # Hysteresis prevents rapid PINCH / RELEASE flickering.
        if currently_pinching:
            pinching = ratio < 0.85
        else:
            pinching = ratio < 0.70

        self.pinch_states[side] = pinching

        if pinching:
            return "PINCH"

        fingers_up = [
            landmarks[8].y < landmarks[6].y,
            landmarks[12].y < landmarks[10].y,
            landmarks[16].y < landmarks[14].y,
            landmarks[20].y < landmarks[18].y
        ]

        if all(fingers_up):
            return "OPEN PALM"

        if not any(fingers_up):
            return "FIST"

        if (
            fingers_up[0]
            and not fingers_up[1]
            and not fingers_up[2]
            and not fingers_up[3]
        ):
            return "POINTING"

        return "NEUTRAL"

    def process(self, frame):

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp = int(
            (time.monotonic() - self.start_time) * 1000
        )

        timestamp = max(
            timestamp,
            self.last_timestamp + 1
        )

        self.last_timestamp = timestamp

        result = self.tracker.detect_for_video(
            image,
            timestamp
        )

        detected_hands = {}

        if not result.hand_landmarks:
            self.pinch_states = {
                "Left": False,
                "Right": False
            }
            self.pinch_ratios = {"Left": None, "Right": None}
            self.pinch_candidates = {"Left": 0, "Right": 0}
            return detected_hands

        for index, landmarks in enumerate(
            result.hand_landmarks
        ):

            if (
                not result.handedness
                or index >= len(result.handedness)
                or not result.handedness[index]
            ):
                continue

            side = (
                result.handedness[index][0].category_name
            )

            if side not in ("Left", "Right"):
                continue

            palm = self.get_palm_center(landmarks)
            measurements = self.get_hand_measurements(
                landmarks
            )

            detected_hands[side] = {
                "landmarks": landmarks,
                "palm": palm,
                "index_tip": {
                    "x": landmarks[8].x,
                    "y": landmarks[8].y
                },
                "gesture": self.classify_gesture(
                    landmarks,
                    side
                ),
                **measurements
            }

        for side in ("Left", "Right"):
            if side not in detected_hands:
                self.pinch_states[side] = False

        return detected_hands

    def draw(self, frame, detected_hands):

        height, width = frame.shape[:2]

        for side, hand_data in detected_hands.items():

            landmarks = hand_data["landmarks"]
            palm = hand_data["palm"]

            # Restrained medical ivory palette (BGR).
            bone_color = (205, 211, 198)
            highlight = (232, 228, 211)
            shadow = (75, 78, 72)

            # Draw subtle depth beneath the fine connections.
            for start, end in self.HAND_CONNECTIONS:

                p1 = landmarks[start]
                p2 = landmarks[end]

                a = (int(p1.x * width), int(p1.y * height))
                b = (int(p2.x * width), int(p2.y * height))

                cv2.line(
                    frame, a, b, shadow, 3, cv2.LINE_AA
                )

                cv2.line(
                    frame, a, b, bone_color, 1, cv2.LINE_AA
                )

            # Refined joint markers.
            for index, point in enumerate(landmarks):

                pos = (
                    int(point.x * width),
                    int(point.y * height)
                )

                radius = 3 if index in (0, 4, 8, 12, 16, 20) else 2

                cv2.circle(
                    frame, pos, radius + 1,
                    shadow, 1, cv2.LINE_AA
                )

                cv2.circle(
                    frame, pos, radius,
                    highlight, 1, cv2.LINE_AA
                )

                cv2.circle(
                    frame, pos, 1,
                    bone_color, -1, cv2.LINE_AA
                )

            # Discreet palm reference.
            palm_pos = (
                int(palm["x"] * width),
                int(palm["y"] * height)
            )

            cv2.circle(
                frame, palm_pos, 5,
                shadow, 1, cv2.LINE_AA
            )

            cv2.circle(
                frame, palm_pos, 2,
                highlight, -1, cv2.LINE_AA
            )

            # Place labels toward the outer edges to keep the
            # centre of the camera view clear.
            label = f"{side.upper()}  /  {hand_data['gesture']}"

            label_width = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                1
            )[0][0]

            if side == "Left":
                label_x = palm_pos[0] - label_width - 18
            else:
                label_x = palm_pos[0] + 18

            label_x = max(8, min(width - label_width - 8, label_x))
            label_y = max(22, min(height - 10, palm_pos[1] - 18))

            cv2.putText(
                frame,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                highlight,
                1,
                cv2.LINE_AA
            )

        return frame

    def close(self):

        if self.tracker:
            self.tracker.close()
            self.tracker = None