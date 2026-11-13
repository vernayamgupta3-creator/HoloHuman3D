import asyncio
import json
import time
import cv2
import websockets
import sys
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracking.hand_tracker import HandTracker

HOST = "127.0.0.1"
PORT = 8765

clients = set()
running = True


def serialize_hand(hand):
    landmarks = []

    for point in hand.get("landmarks", []):
        landmarks.append({
            "x": float(point.x),
            "y": float(point.y),
            "z": float(point.z)
        })

    return {
        "gesture": str(hand.get("gesture", "NEUTRAL")),
        "palm": hand.get("palm", {}),
        "index_tip": hand.get("index_tip", {}),
        "pinch_distance": float(hand.get("pinch_distance", 0)),
        "pinch_ratio": float(hand.get("pinch_ratio", 0)),
        "landmarks": landmarks
    }


async def websocket_handler(websocket):
    clients.add(websocket)
    print("[CONNECTED] Website connected.")

    try:
        await websocket.send(json.dumps({
            "type": "status",
            "status": "connected",
            "message": "Python Companion connected"
        }))

        await websocket.wait_closed()

    finally:
        clients.discard(websocket)
        print("[DISCONNECTED] Website disconnected.")


async def broadcast(message):
    if not clients:
        return

    payload = json.dumps(message)

    current_clients = list(clients)

    results = await asyncio.gather(
        *(client.send(payload) for client in current_clients),
        return_exceptions=True
    )

    for client, result in zip(current_clients, results):
        if isinstance(result, Exception):
            clients.discard(client)


async def camera_loop():
    global running

    tracker = None
    camera = None

    try:
        print("[STARTING] Loading original Python hand tracker...")

        tracker = HandTracker()

        camera = cv2.VideoCapture(0)

        if not camera.isOpened():
            raise RuntimeError("Could not open webcam.")

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)

        print("[READY] Camera and tracker running.")

        previous_time = time.time()
        fps = 0.0
        frame_count = 0
        latest_frame = ""

        while running:
            success, frame = camera.read()

            if not success:
                await asyncio.sleep(0.02)
                continue

            # Mirror camera image.
            frame = cv2.flip(frame, 1)

            # Detect both hands.
            detected_hands = tracker.process(frame)

            # Draw the 21-point skeleton on the actual camera image.
            frame = tracker.draw(frame, detected_hands)

            # Serialize tracking information for the website.
            hands = {}

            for side, hand in detected_hands.items():
                hands[side] = serialize_hand(hand)

            # Calculate FPS.
            current_time = time.time()
            delta = current_time - previous_time
            previous_time = current_time

            if delta > 0:
                instant_fps = 1.0 / delta
                fps = instant_fps if fps == 0 else (
                    0.9 * fps + 0.1 * instant_fps
                )

            # Encode the already-annotated image.
            frame_count += 1

            if frame_count % 2 == 0:
                encoded, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 75]
                )

                if encoded:
                    latest_frame = base64.b64encode(
                        buffer
                    ).decode("ascii")

            # Send tracking and camera data.
            await broadcast({
                "type": "tracking",
                "timestamp": current_time,
                "fps": round(fps, 1),
                "hands": hands,
                "frame": latest_frame
            })

            await asyncio.sleep(0.01)

    except Exception as error:
        print("[ERROR]", error)

        try:
            await broadcast({
                "type": "status",
                "status": "error",
                "message": str(error)
            })
        except Exception:
            pass

    finally:
        running = False

        if camera is not None:
            camera.release()

        if tracker is not None:
            tracker.close()

        print("[STOPPED] Camera released.")


async def main():
    global running
    running = True

    print("=" * 55)
    print("          HOLOHUMAN3D PYTHON COMPANION")
    print("=" * 55)

    async with websockets.serve(
        websocket_handler,
        HOST,
        PORT,
        max_size=8 * 1024 * 1024
    ):
        print(f"[SERVER] ws://{HOST}:{PORT}")
        await camera_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        running = False
        print("[EXIT] Companion stopped.")
