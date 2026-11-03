
import cv2
import time
import mediapipe as mp
from collections import deque

# ==========================================
# CONFIGURATION
# ==========================================

MODEL_PATH = "pose_landmarker_lite.task"

JUMP_THRESHOLD = 0.025
SQUAT_THRESHOLD = 0.045
SIDE_THRESHOLD = 0.07

JUMP_COOLDOWN = 1.0
ACTION_COOLDOWN = 0.8

# ==========================================
# MEDIAPIPE SETUP
# ==========================================

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = PoseLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=MODEL_PATH
    ),
    running_mode=RunningMode.VIDEO,
    num_poses=1
)

connections = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (27, 29), (27, 31),
    (28, 30), (30, 32)
]

# ==========================================
# CAMERA
# ==========================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Webcam could not be opened.")
    raise SystemExit

# ==========================================
# HISTORY
# ==========================================

hip_history = deque(maxlen=20)
ankle_history = deque(maxlen=20)
center_history = deque(maxlen=15)

last_action = "WAITING"
last_action_time = 0
jump_cooldown_until = 0

start_time = time.time()

print("\nMotionPlay started!")
print("Stand where your upper body and legs are visible.")
print("Try a small vertical jump.")
print("Press Q to quit.\n")


def avg(values):
    return sum(values) / len(values) if values else 0


def draw_text(frame, text, position, color=(255, 255, 255), scale=0.65):
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        2,
        cv2.LINE_AA
    )


# ==========================================
# MAIN LOOP
# ==========================================

try:
    with PoseLandmarker.create_from_options(options) as landmarker:

        while True:

            success, frame = cap.read()

            if not success:
                print("Unable to read webcam.")
                break

            frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            timestamp = int((time.time() - start_time) * 1000)

            result = landmarker.detect_for_video(
                image,
                timestamp
            )

            action = "NO BODY DETECTED"
            color = (0, 0, 255)

            ankle_rise = 0.0
            hip_rise = 0.0

            if result.pose_landmarks:

                lm = result.pose_landmarks[0]

                def point(i):
                    return lm[i]

                # Draw skeleton.
                for a, b in connections:

                    p1 = point(a)
                    p2 = point(b)

                    cv2.line(
                        frame,
                        (int(p1.x * width), int(p1.y * height)),
                        (int(p2.x * width), int(p2.y * height)),
                        (0, 255, 0),
                        2
                    )

                for p in lm:

                    cv2.circle(
                        frame,
                        (int(p.x * width), int(p.y * height)),
                        3,
                        (0, 200, 255),
                        -1
                    )

                # Extract body landmarks.
                hip_y = (point(23).y + point(24).y) / 2

                ankle_y = (point(27).y + point(28).y) / 2

                center_x = (point(23).x + point(24).x) / 2

                hip_history.append(hip_y)
                ankle_history.append(ankle_y)
                center_history.append(center_x)

                action = "TRACKING"

                # ==================================
                # JUMP DETECTION
                # ==================================

                if len(hip_history) >= 10:

                    hips = list(hip_history)
                    ankles = list(ankle_history)

                    # Compare the earlier part of the window
                    # with the most recent frames.
                    old_hip = avg(hips[-10:-6])
                    new_hip = avg(hips[-3:])

                    old_ankle = avg(ankles[-10:-6])
                    new_ankle = avg(ankles[-3:])

                    hip_rise = old_hip - new_hip
                    ankle_rise = old_ankle - new_ankle

                    # Positive rise means movement upward
                    # in the webcam image.
                    #
                    # Hip movement is the primary signal.
                    # Ankle movement is additional evidence.
                    if time.time() > jump_cooldown_until:

                        if (
                            hip_rise > JUMP_THRESHOLD
                            and ankle_rise > 0.005
                        ):

                            action = "JUMP"

                            jump_cooldown_until = (
                                time.time() + JUMP_COOLDOWN
                            )

                # ==================================
                # SQUAT DETECTION
                # ==================================

                if action == "TRACKING" and len(hip_history) >= 10:

                    hips = list(hip_history)

                    old_hip = avg(hips[-10:-6])
                    new_hip = avg(hips[-3:])

                    hip_drop = new_hip - old_hip

                    if hip_drop > SQUAT_THRESHOLD:

                        action = "ROLL / SQUAT"

                # ==================================
                # LEFT / RIGHT DETECTION
                # ==================================

                if action == "TRACKING" and len(center_history) >= 10:

                    centers = list(center_history)

                    old_center = avg(centers[-10:-6])
                    new_center = avg(centers[-3:])

                    movement = new_center - old_center

                    if movement > SIDE_THRESHOLD:

                        action = "RIGHT"

                    elif movement < -SIDE_THRESHOLD:

                        action = "LEFT"

                # ==================================
                # DEBUG PANEL
                # ==================================

                draw_text(
                    frame,
                    f"Hip rise: {hip_rise:.3f}",
                    (20, 105)
                )

                draw_text(
                    frame,
                    f"Ankle rise: {ankle_rise:.3f}",
                    (20, 135)
                )

                draw_text(
                    frame,
                    f"Hip Y: {hip_y:.3f}",
                    (20, 165)
                )

                color = (0, 255, 0)

            else:

                hip_history.clear()
                ankle_history.clear()
                center_history.clear()

            # ==================================
            # LOGGING
            # ==================================

            now = time.time()

            if action in ("JUMP", "ROLL / SQUAT", "LEFT", "RIGHT"):

                if (
                    action != last_action
                    and now - last_action_time >= ACTION_COOLDOWN
                ):

                    print("Movement detected:", action)

                    last_action = action
                    last_action_time = now

            elif action == "TRACKING":

                last_action = "TRACKING"

            # ==================================
            # DISPLAY
            # ==================================

            cv2.rectangle(
                frame,
                (10, 10),
                (460, 70),
                (25, 25, 25),
                -1
            )

            draw_text(
                frame,
                f"MotionPlay: {action}",
                (20, 48),
                color,
                0.85
            )

            draw_text(
                frame,
                "Press Q to quit",
                (20, height - 20)
            )

            cv2.imshow(
                "MotionPlay - Jump Debugger",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

finally:

    cap.release()
    cv2.destroyAllWindows()

    print("\nMotionPlay stopped.")
