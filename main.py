import sys
import subprocess
import socket
import atexit
import time
from pathlib import Path

import cv2

from PySide6.QtCore import Qt, QTimer, QUrl, QPoint
from PySide6.QtGui import QImage, QPixmap, QCursor
from PySide6.QtTest import QTest

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QScrollArea
)

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from tracking.hand_tracker import HandTracker


class HoloHuman(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("HoloHuman 3D")

        # ==========================================
        # WINDOW
        # ==========================================

        screen = QApplication.primaryScreen().availableGeometry()

        window_width = min(1500, int(screen.width() * 0.95))
        window_height = min(850, int(screen.height() * 0.88))

        x = screen.x() + (screen.width() - window_width) // 2
        y = screen.y() + (screen.height() - window_height) // 2

        self.setGeometry(x, y, window_width, window_height)
        self.setMinimumSize(800, 550)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #050a12;
                color: white;
                font-family: Segoe UI;
            }

            QLabel {
                background: transparent;
                border: none;
            }

            QPushButton {
                background: rgba(5, 22, 38, 185);
                color: #a7efff;
                border: none;
                border-radius: 5px;
                padding: 7px 11px;
                text-align: left;
                font-size: 11px;
            }

            QPushButton:hover {
                background: rgba(20, 75, 105, 220);
                color: white;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 5px;
            }

            QScrollBar::handle:vertical {
                background: #24536b;
                border-radius: 2px;
            }
        """)

        # ==========================================
        # MAIN CANVAS
        # ==========================================

        self.canvas = QWidget()
        self.setCentralWidget(self.canvas)

        # ==========================================
        # CAMERA
        # ==========================================

        self.camera = cv2.VideoCapture(0)

        self.camera_label = QLabel(self.canvas)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("background: #050a12;")

        # ==========================================
        # TRANSPARENT 3D VIEWER
        # ==========================================

        self.viewer = QWebEngineView(self.canvas)

        self.viewer.setAttribute(
            Qt.WA_TranslucentBackground,
            True
        )

        self.viewer.setStyleSheet("background: transparent;")

        self.viewer.page().setBackgroundColor(Qt.transparent)

        self.viewer.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            True
        )

        # Locate Open Anatomy Atlas without relying on a user-specific path.
        atlas_dir = Path(
            __import__("os").environ.get(
                "HOLOHUMAN_ATLAS_DIR",
                str(Path(__file__).resolve().parent.parent / "open-anatomy-atlas")
            )
        ).expanduser().resolve()

        if not atlas_dir.is_dir():
            raise FileNotFoundError(
                f"Open Anatomy Atlas not found at: {atlas_dir}. "
                "Set the HOLOHUMAN_ATLAS_DIR environment variable."
            )

        print("[HoloHuman] Starting anatomy server...")

        self.atlas_process = subprocess.Popen(
            ["cmd", "/c", "npm", "run", "web"],
            cwd=str(atlas_dir),
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        atexit.register(
            lambda: self.atlas_process.terminate()
            if self.atlas_process and self.atlas_process.poll() is None
            else None
        )

        server_ready = False

        for attempt in range(30):
            try:
                with socket.create_connection(("127.0.0.1", 8080), timeout=1):
                    server_ready = True
                    break
            except OSError:
                time.sleep(1)

        if server_ready:
            self.viewer.load(QUrl("http://127.0.0.1:8080"))
            print("[HoloHuman] Anatomy atlas connected.")
        else:
            print("[HoloHuman] ERROR: Anatomy server did not start.")

        # ==========================================
        # HAND TRACKING
        # ==========================================

        self.hand_tracker = None
        self.tracking_error = None

        try:
            self.hand_tracker = HandTracker()
            print("[HoloHuman] Hand tracking initialized.")

        except Exception as error:
            import traceback

            self.tracking_error = str(error)

            print("\n[HAND TRACKING INITIALIZATION ERROR]")
            traceback.print_exc()

        self.fps = 0
        self.previous_frame_time = time.monotonic()

        # HAND CONTROLLED VIRTUAL CURSOR
        self.cursor_x = None
        self.cursor_y = None
        self.cursor_smoothing = 0.35
        self.previous_pinch = False
        self.cursor_enabled = True
        self.last_cursor_click = 0

        # LEFT HAND 3D CONTROL
        self.left_previous_x = None
        self.left_previous_y = None
        self.left_previous_pinch = None
        self.left_control_time = 0
        self.zoom_previous_distance = None
        self.zoom_smoothed_distance = None
        self.zoom_control_time = 0
        self.two_hand_previous_y = None
        self.two_hand_smoothed_y = None

        self.rotation_smoothing = 0.35
        self.rotation_x = None
        self.rotation_y = None



        # ==========================================
        # HEADER
        # ==========================================

        self.header = QWidget(self.canvas)
        self.header.setStyleSheet(
            "background: rgba(3, 12, 24, 175);"
        )

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 5, 15, 5)

        logo = QLabel("HOLOHUMAN 3D")
        logo.setStyleSheet(
            "font-size: 21px; font-weight: bold; color: #50dcff;"
        )

        status = QLabel("● SYSTEM ONLINE")
        status.setStyleSheet(
            "color: #65f5bb; font-size: 11px;"
        )

        self.fps_label = QLabel("CAMERA INITIALIZING")
        self.fps_label.setStyleSheet(
            "color: #a9c9dd; font-size: 11px;"
        )

        header_layout.addWidget(logo)
        header_layout.addStretch()
        header_layout.addWidget(status)
        header_layout.addSpacing(15)
        header_layout.addWidget(self.fps_label)

        # ==========================================
        # LEFT NAVIGATION
        # ==========================================

        self.navigation = QWidget(self.canvas)
        self.navigation.setStyleSheet(
            "background: rgba(3, 13, 26, 175);"
        )

        nav_layout = QVBoxLayout(self.navigation)
        nav_layout.setContentsMargins(9, 9, 9, 9)
        nav_layout.setSpacing(5)

        nav_title = QLabel("ANATOMY")
        nav_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #50dcff;"
        )

        nav_layout.addWidget(nav_title)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        nav_content = QWidget()

        nav_content_layout = QVBoxLayout(nav_content)
        nav_content_layout.setContentsMargins(0, 0, 0, 0)
        nav_content_layout.setSpacing(5)

        systems = [
            "◉  Human Overview",
            "◉  Skeletal System",
            "◉  Muscular System",
            "◉  Nervous System",
            "◉  Cardiovascular",
            "◉  Respiratory",
            "◉  Digestive",
            "◉  Urinary",
            "◉  Endocrine",
            "◉  Reproductive",
            "◉  Lymphatic",
            "◉  Integumentary"
        ]

        for system in systems:
            button = QPushButton(system)

            button.clicked.connect(
                lambda checked=False, name=system:
                self.select_system(name)
            )

            nav_content_layout.addWidget(button)

        nav_content_layout.addStretch()

        self.nav_scroll.setWidget(nav_content)
        nav_layout.addWidget(self.nav_scroll)

        # ==========================================
        # RIGHT INFORMATION PANEL
        # ==========================================

        self.information = QWidget(self.canvas)

        self.information.setStyleSheet(
            "background: rgba(3, 13, 26, 175);"
        )

        info_layout = QVBoxLayout(self.information)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        info_title = QLabel("STRUCTURE DETAILS")

        info_title.setStyleSheet(
            "color: #50dcff; font-size: 13px; font-weight: bold;"
        )

        self.selected = QLabel("Human Body")

        self.selected.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: white;"
        )

        self.details = QLabel(
            "Select an anatomical system to explore.\n\n"
            "Detailed anatomical information will appear here."
        )

        self.details.setWordWrap(True)

        self.details.setStyleSheet(
            "color: #a9c5d8; font-size: 11px;"
        )

        gesture_title = QLabel("GESTURE STUDIO")

        gesture_title.setStyleSheet(
            "color: #50dcff; font-size: 13px; font-weight: bold;"
        )

        self.gesture_status = QLabel(
            "LEFT HAND     WAITING\n\n"
            "RIGHT HAND    WAITING\n\n"
            "GESTURE       NONE"
        )

        self.gesture_status.setWordWrap(True)

        self.gesture_status.setStyleSheet(
            "color: #b2d6e8; font-size: 11px;"
        )

        info_layout.addWidget(info_title)
        info_layout.addSpacing(8)
        info_layout.addWidget(self.selected)
        info_layout.addWidget(self.details)
        info_layout.addStretch()

        # ==========================================
        # BOTTOM CONTROLS
        # ==========================================

        self.bottom = QWidget(self.canvas)

        self.bottom.setStyleSheet(
            "background: rgba(3, 13, 26, 190);"
        )

        bottom_layout = QHBoxLayout(self.bottom)
        bottom_layout.setContentsMargins(8, 4, 8, 4)
        bottom_layout.setSpacing(7)

        controls = [
            "ROTATE",
            "ZOOM",
            "SELECT",
            "ISOLATE",
            "RESET"
        ]

        for name in controls:
            button = QPushButton(name)
            button.setMinimumWidth(65)
            bottom_layout.addWidget(button)

        # ==========================================
        # CAMERA TIMER
        # ==========================================

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_camera)

        if self.camera.isOpened():
            self.timer.start(30)
        else:
            self.fps_label.setText("CAMERA UNAVAILABLE")
            print("[HoloHuman] Camera could not be opened.")

        self.position_overlays()

    # ==============================================
    # POSITION FLOATING INTERFACE
    # ==============================================

    def position_overlays(self):

        width = self.canvas.width()
        height = self.canvas.height()

        if width <= 0 or height <= 0:
            return

        margin = 12
        header_height = 55
        bottom_height = 48

        self.camera_label.setGeometry(
            0, 0, width, height
        )

        # FULL-SCREEN TRANSPARENT 3D VIEWER

        self.viewer.setGeometry(
            0,
            0,
            width,
            height
        )

        # HEADER

        self.header.setGeometry(
            0, 0, width, header_height
        )

        available_height = max(
            200,
            height - header_height - bottom_height - 3 * margin
        )

        # LEFT PANEL

        self.navigation.hide()
        self.navigation.setGeometry(
            margin,
            header_height + margin,
            195,
            available_height
        )

        # RIGHT PANEL

        self.information.hide()
        self.information.setGeometry(
            width - 245,
            header_height + margin,
            233,
            available_height
        )

        # BOTTOM PANEL

        bottom_width = min(440, width - 30)

        self.bottom.setGeometry(
            (width - bottom_width) // 2,
            height - bottom_height - margin,
            bottom_width,
            bottom_height
        )

        # WIDGET STACKING

        self.camera_label.lower()
        self.viewer.raise_()

        self.header.raise_()
        self.bottom.raise_()

    # ==============================================
    # ANATOMY NAVIGATION
    # ==============================================

    def select_system(self, name):

        selected_name = name.replace("◉", "").strip()

        self.selected.setText(selected_name)

        self.details.setText(
            "Selected system:\n"
            + selected_name
            + "\n\nDetailed structures, functions, "
            "clinical information and 3D exploration "
            "will be integrated here."
        )

    # ==============================================
    # GESTURE STUDIO
    # ==============================================

    def update_gesture_panel(self, hands):

        left = hands.get("Left")
        right = hands.get("Right")

        left_status = (
            left["gesture"] if left else "WAITING"
        )

        right_status = (
            right["gesture"] if right else "WAITING"
        )

        if left and right:
            overall = "BOTH HANDS TRACKED"

        elif left or right:
            overall = "ONE HAND TRACKED"

        else:
            overall = "NO HAND DETECTED"

        self.gesture_status.setText(
            f"LEFT HAND     {left_status}\n\n"
            f"RIGHT HAND    {right_status}\n\n"
            f"STATUS        {overall}"
        )

    # ==============================================
    # HAND CONTROLLED APPLICATION CURSOR
    # ==============================================

    def update_virtual_cursor(self, hands):

        if not self.cursor_enabled:
            return

        # Two open palms have priority over cursor control.
        left_hand = hands.get("Right")
        right_hand = hands.get("Left")

        if (
            left_hand is not None
            and right_hand is not None
            and left_hand["gesture"] == "OPEN PALM"
            and right_hand["gesture"] == "OPEN PALM"
        ):
            self.previous_pinch = False
            return

        # MediaPipe labels are reversed for the current
        # camera setup based on the observed hand behaviour.
        # Physical RIGHT hand controls the cursor.
        hand = hands.get("Left")

        if hand is None:
            self.previous_pinch = False
            self.cursor_x = None
            self.cursor_y = None
            return

        point = hand["index_tip"]

        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()

        target_x = max(0, min(
            canvas_width - 1,
            int(point["x"] * canvas_width)
        ))

        target_y = max(0, min(
            canvas_height - 1,
            int(point["y"] * canvas_height)
        ))

        # Adaptive cursor stabilization:
        # filter tiny tremors while keeping larger movements responsive.
        if self.cursor_x is None:
            self.cursor_x = float(target_x)
            self.cursor_y = float(target_y)
        else:
            dx = target_x - self.cursor_x
            dy = target_y - self.cursor_y
            movement = max(abs(dx), abs(dy))

            if movement < 3:
                alpha = 0.12
            elif movement < 18:
                alpha = 0.22
            else:
                alpha = 0.42

            # Ignore tiny tracking fluctuations.
            if abs(dx) >= 1.5:
                self.cursor_x += alpha * dx

            if abs(dy) >= 1.5:
                self.cursor_y += alpha * dy

        x = int(self.cursor_x)
        y = int(self.cursor_y)

        global_position = self.canvas.mapToGlobal(
            QPoint(x, y)
        )

        QCursor.setPos(global_position)

        # Pinch-to-click with edge detection.
        pinching = hand["gesture"] == "PINCH"

        if pinching and not self.previous_pinch:

            now = time.monotonic()

            if now - self.last_cursor_click > 0.45:

                target = QApplication.widgetAt(
                    global_position
                )

                if target is not None:

                    local_position = target.mapFromGlobal(
                        global_position
                    )

                    QTest.mouseClick(
                        target,
                        Qt.LeftButton,
                        Qt.NoModifier,
                        local_position,
                        30
                    )

                    self.last_cursor_click = now

        self.previous_pinch = pinching

    # ==============================================
    # CAMERA + HAND TRACKING
    # ==============================================

    def update_left_hand_controls(self, hands):

        physical_left = hands.get("Right")
        physical_right = hands.get("Left")
        now = time.monotonic()

        # BOTH HANDS OPEN: vertical movement + zoom
        if (
            physical_left is not None
            and physical_right is not None
            and physical_left["gesture"] == "OPEN PALM"
            and physical_right["gesture"] == "OPEN PALM"
        ):
            lp = physical_left["palm"]
            rp = physical_right["palm"]

            # Average vertical position of both palms.
            center_y = (lp["y"] + rp["y"]) / 2

            if self.two_hand_smoothed_y is None:
                self.two_hand_smoothed_y = center_y

            old_y = self.two_hand_smoothed_y
            self.two_hand_smoothed_y = (
                0.75 * old_y + 0.25 * center_y
            )

            if self.two_hand_previous_y is not None:
                movement_y = (
                    self.two_hand_smoothed_y
                    - self.two_hand_previous_y
                )

                # Convert normalized hand movement to Atlas pixels.
                pan_dy = movement_y * self.canvas.height() * 2.0

                if abs(pan_dy) > 0.5:
                    js = (
                        "if(window.__atlasDebug?.renderer) "
                        f"window.__atlasDebug.renderer.pan(0,{pan_dy:.3f});"
                    )
                    self.viewer.page().runJavaScript(js)

            self.two_hand_previous_y = self.two_hand_smoothed_y

            # Actual palm-to-palm distance controls zoom.
            # This remains stable when both hands move vertically.
            distance = (
                (lp["x"] - rp["x"]) ** 2
                + (lp["y"] - rp["y"]) ** 2
            ) ** 0.5

            if self.zoom_smoothed_distance is None:
                self.zoom_smoothed_distance = distance

            self.zoom_smoothed_distance = (
                0.75 * self.zoom_smoothed_distance
                + 0.25 * distance
            )

            if self.zoom_previous_distance is not None:
                change = (
                    self.zoom_smoothed_distance
                    - self.zoom_previous_distance
                )

                if now - self.zoom_control_time >= 0.04:
                    if abs(change) > 0.0015:
                        # Stronger but bounded zoom response.
                        factor = max(
                            0.94,
                            min(1.06, 1.0 + change * 4.0)
                        )

                        js = (
                            "if(window.__atlasDebug?.renderer) "
                            f"window.__atlasDebug.renderer.zoom({factor:.5f});"
                        )
                        self.viewer.page().runJavaScript(js)
                        self.zoom_control_time = now

            self.zoom_previous_distance = self.zoom_smoothed_distance

            self.rotation_x = None
            self.rotation_y = None
            self.left_previous_x = None
            self.left_previous_y = None
            return

        # Reset two-hand movement when either hand is released.
        self.two_hand_previous_y = None
        self.two_hand_smoothed_y = None
        self.zoom_previous_distance = None
        self.zoom_smoothed_distance = None

        # LEFT HAND PINCH: rotate model.
        if physical_left is None:
            self.rotation_x = None
            self.rotation_y = None
            return

        if physical_left["gesture"] != "PINCH":
            self.rotation_x = None
            self.rotation_y = None
            return

        if now - self.left_control_time < 0.025:
            return

        self.left_control_time = now

        palm = physical_left["palm"]
        x, y = palm["x"], palm["y"]

        if self.rotation_x is None:
            self.rotation_x = x
            self.rotation_y = y
            return

        dx = (x - self.rotation_x) * 700
        dy = (y - self.rotation_y) * 700

        self.rotation_x += 0.35 * (x - self.rotation_x)
        self.rotation_y += 0.35 * (y - self.rotation_y)

        dx = max(-12, min(12, dx))
        dy = max(-12, min(12, dy))

        if abs(dx) > 0.8 or abs(dy) > 0.8:
            js = (
                "if(window.__atlasDebug?.renderer) "
                f"window.__atlasDebug.renderer.orbit({dx:.3f},{dy:.3f});"
            )
            self.viewer.page().runJavaScript(js)

    def update_camera(self):

        if not self.camera.isOpened():
            return

        success, frame = self.camera.read()

        if not success:
            return

        frame = cv2.flip(frame, 1)

        hands = {}

        if self.hand_tracker is not None:

            try:
                hands = self.hand_tracker.process(frame)


                self.update_gesture_panel(hands)

                self.update_virtual_cursor(hands)
                self.update_left_hand_controls(hands)

            except Exception as error:
                print("[Tracking Error]", error)

        else:
            self.gesture_status.setText(
                "HAND TRACKING UNAVAILABLE\n\n"
                + str(self.tracking_error)
            )

        # NATURAL CAMERA ENHANCEMENT
        # Correct lighting gently without changing the background or anatomy.

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=1.5,
            tileGridSize=(8, 8)
        )

        l_channel = clahe.apply(l_channel)

        enhanced_lab = cv2.merge((
            l_channel,
            a_channel,
            b_channel
        ))

        frame = cv2.cvtColor(
            enhanced_lab,
            cv2.COLOR_LAB2BGR
        )

        # Very subtle sharpening for camera clarity.
        soft = cv2.GaussianBlur(frame, (0, 0), 1.0)
        frame = cv2.addWeighted(frame, 1.12, soft, -0.12, 0)

        # Draw tracking overlay after image enhancement.
        if self.hand_tracker is not None:
            frame = self.hand_tracker.draw(frame, hands)

        # FPS CALCULATION

        now = time.monotonic()
        elapsed = now - self.previous_frame_time

        if elapsed > 0:

            instant_fps = 1.0 / elapsed

            if self.fps == 0:
                self.fps = instant_fps

            else:
                self.fps = (
                    0.85 * self.fps
                    + 0.15 * instant_fps
                )

        self.previous_frame_time = now

        self.fps_label.setText(
            f"CAMERA ACTIVE  |  {self.fps:.1f} FPS"
        )

        # CONVERT CAMERA FRAME TO QT IMAGE

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = rgb.shape

        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format_RGB888
        ).copy()

        pixmap = QPixmap.fromImage(image)

        self.camera_label.setPixmap(
            pixmap.scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    # ==============================================
    # RESIZE
    # ==============================================

    def resizeEvent(self, event):

        self.position_overlays()

        super().resizeEvent(event)

    # ==============================================
    # CLEAN SHUTDOWN
    # ==============================================

    def closeEvent(self, event):

        self.timer.stop()

        if self.hand_tracker is not None:
            self.hand_tracker.close()

        if self.camera.isOpened():
            self.camera.release()

        self.viewer.close()

        event.accept()


# ==============================================
# APPLICATION START
# ==============================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = HoloHuman()
    window.show()

    sys.exit(app.exec())