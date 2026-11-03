
import cv2
import time
import threading
import keyboard
import mediapipe as mp

from collections import deque
from pathlib import Path


# ============================================================
# MOTIONPLAY CONFIGURATION
# ============================================================

MODEL_PATH = Path(__file__).parent / "hand_landmarker.task"

CAMERA_INDEX = 0

# Keep this at 0.10 initially because it was working reliably.
MOVEMENT_THRESHOLD = 0.10

# Minimum time between game commands.
GESTURE_COOLDOWN = 0.65

# Time window used to measure hand movement.
MOVEMENT_WINDOW = 0.25

# Camera resolution.
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


# ============================================================
# APPLICATION STATE
# ============================================================

controls_enabled = False
running = True

state_lock = threading.Lock()

last_gesture_time = 0.0

movement_history = deque()

gesture_counts = {
    "LEFT": 0,
    "RIGHT": 0,
    "JUMP / UP": 0,
    "ROLL / DOWN": 0,
}

KEY_MAP = {
    "LEFT": "left",
    "RIGHT": "right",
    "JUMP / UP": "up",
    "ROLL / DOWN": "down",
}


# ============================================================
# GLOBAL KEYBOARD SHORTCUTS
# ============================================================

def toggle_controls():
    global controls_enabled

    with state_lock:
        controls_enabled = not controls_enabled
        status = "ENABLED" if controls_enabled else "DISABLED"

    print(f"\n[MotionPlay] Controls {status}")


def stop_program():
    global running
    running = False


keyboard.add_hotkey("f8", toggle_controls)
keyboard.add_hotkey("f9", stop_program)


# ============================================================
# SEND GAME COMMANDS
# ============================================================

def send_game_key(gesture):
    global last_gesture_time

    with state_lock:
        enabled = controls_enabled

    if not enabled:
        return

    now = time.monotonic()

    if now - last_gesture_time < GESTURE_COOLDOWN:
        return

    key = KEY_MAP.get(gesture)

    if key is None:
        return

    try:
        keyboard.press_and_release(key)

        last_gesture_time = now
        gesture_counts[gesture] += 1

        print(
            f"[MotionPlay] {gesture} -> {key} | "
            f"Count: {gesture_counts[gesture]}"
        )

    except Exception as error:
        print(f"[Keyboard Error] {error}")


# ============================================================
# MEDIAPIPE HAND LANDMARKER
# ============================================================

if not MODEL_PATH.exists():
    keyboard.unhook_all_hotkeys()

    raise FileNotFoundError(
        f"Hand model not found: {MODEL_PATH}\n"
        "Make sure hand_landmarker.task is in the MotionPlay folder."
    )


BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


options = HandLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=str(MODEL_PATH)
    ),
    running_mode=RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)


# ============================================================
# CAMERA SETUP
# ============================================================

camera = cv2.VideoCapture(CAMERA_INDEX)

camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

if not camera.isOpened():
    keyboard.unhook_all_hotkeys()
    raise RuntimeError(
        "Could not open the webcam. Check that your camera is connected "
        "and that another application is not using it."
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

print("\n" + "=" * 48)
print("             MOTIONPLAY")
print("       HAND GESTURE CONTROLLER")
print("=" * 48)
print("F8  : Enable / disable game controls")
print("F9  : Exit MotionPlay")
print("Keep the game window focused for key input.")
print("Start with controls disabled.")
print("=" * 48 + "\n")


previous_frame_time = time.monotonic()
fps = 0.0

try:
    with HandLandmarker.create_from_options(options) as landmarker:

        while running:

            success, frame = camera.read()

            if not success:
                print("[Camera Error] Could not read a frame.")
                break

            # Mirror the image for natural movement.
            frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            timestamp_ms = int(
                time.monotonic() * 1000
            )

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms
            )

            gesture = "IDLE"

            dx = 0.0
            dy = 0.0

            now = time.monotonic()

            # ------------------------------------------------
            # PROCESS HAND LANDMARKS
            # ------------------------------------------------

            if result.hand_landmarks:

                landmarks = result.hand_landmarks[0]

                # Use five palm landmarks for a stable centre.
                palm_points = [0, 5, 9, 13, 17]

                palm_x = sum(
                    landmarks[index].x
                    for index in palm_points
                ) / len(palm_points)

                palm_y = sum(
                    landmarks[index].y
                    for index in palm_points
                ) / len(palm_points)

                # Add the current palm position.
                movement_history.append(
                    (now, palm_x, palm_y)
                )

                # Remove old positions outside the time window.
                while (
                    movement_history
                    and now - movement_history[0][0]
                    > MOVEMENT_WINDOW
                ):
                    movement_history.popleft()

                # Measure movement relative to the oldest
                # position in the recent window.
                if len(movement_history) >= 2:

                    old_x = movement_history[0][1]
                    old_y = movement_history[0][2]

                    dx = palm_x - old_x
                    dy = palm_y - old_y

                    # Select the dominant direction.
                    if abs(dx) > abs(dy):

                        if dx < -MOVEMENT_THRESHOLD:
                            gesture = "LEFT"

                        elif dx > MOVEMENT_THRESHOLD:
                            gesture = "RIGHT"

                    else:

                        if dy < -MOVEMENT_THRESHOLD:
                            gesture = "JUMP / UP"

                        elif dy > MOVEMENT_THRESHOLD:
                            gesture = "ROLL / DOWN"

                    if gesture != "IDLE":

                        send_game_key(gesture)

                        # Clear the samples to avoid detecting
                        # the same movement repeatedly.
                        movement_history.clear()

                # --------------------------------------------
                # DRAW PALM CENTRE
                # --------------------------------------------

                height, width, _ = frame.shape

                cx = int(palm_x * width)
                cy = int(palm_y * height)

                cv2.circle(
                    frame,
                    (cx, cy),
                    9,
                    (0, 255, 0),
                    -1
                )

                # --------------------------------------------
                # DRAW MOVEMENT ARROW
                # --------------------------------------------

                if len(movement_history) >= 2:

                    old_x = movement_history[0][1]
                    old_y = movement_history[0][2]

                    start_point = (
                        int(old_x * width),
                        int(old_y * height)
                    )

                    end_point = (cx, cy)

                    cv2.arrowedLine(
                        frame,
                        start_point,
                        end_point,
                        (255, 255, 0),
                        2,
                        tipLength=0.25
                    )

            else:
                # Prevent an old position from causing a
                # false gesture after the hand disappears.
                movement_history.clear()

            # ------------------------------------------------
            # FPS CALCULATION
            # ------------------------------------------------

            frame_time = time.monotonic()

            elapsed = frame_time - previous_frame_time

            if elapsed > 0:
                instant_fps = 1.0 / elapsed

                if fps == 0:
                    fps = instant_fps
                else:
                    fps = (0.85 * fps) + (0.15 * instant_fps)

            previous_frame_time = frame_time

            # ------------------------------------------------
            # STATUS PANEL
            # ------------------------------------------------

            with state_lock:
                enabled = controls_enabled

            height, width, _ = frame.shape

            overlay = frame.copy()

            cv2.rectangle(
                overlay,
                (10, 10),
                (width - 10, 235),
                (25, 25, 25),
                -1
            )

            frame = cv2.addWeighted(
                overlay,
                0.55,
                frame,
                0.45,
                0
            )

            status_text = (
                "CONTROLS: ON"
                if enabled
                else "CONTROLS: OFF"
            )

            status_color = (
                (0, 255, 0)
                if enabled
                else (0, 0, 255)
            )

            cv2.putText(
                frame,
                "MOTIONPLAY",
                (25, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                status_text,
                (25, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                status_color,
                2
            )

            cv2.putText(
                frame,
                f"Gesture: {gesture}",
                (25, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Horizontal: {dx:+.3f}",
                (25, 145),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Vertical:   {dy:+.3f}",
                (25, 175),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (25, 205),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                "F8: Toggle Controls | F9: Quit",
                (25, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1
            )

            # ------------------------------------------------
            # DISPLAY
            # ------------------------------------------------

            cv2.imshow(
                "MotionPlay - Gesture Controller",
                frame
            )

            cv2.waitKey(1)

finally:

    camera.release()

    cv2.destroyAllWindows()

    keyboard.unhook_all_hotkeys()

    print("\nMotionPlay stopped.")

    print("\nGesture statistics:")

    for name, count in gesture_counts.items():
        print(f"{name}: {count}")
