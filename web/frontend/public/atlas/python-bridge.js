(() => {
  if (window.__holoControllerStarted) return;
  window.__holoControllerStarted = true;

  const stage = document.querySelector(".stage");
  const canvas = document.getElementById("viewport");

  if (!stage || !canvas) {
    console.error("HoloHuman3D: Atlas stage not found.");
    return;
  }

  document.querySelector("#pythonCameraFeed")?.remove();
  document.querySelector("#pythonTrackingStatus")?.remove();
  document.querySelector("#holoAirMouse")?.remove();

  const camera = document.createElement("img");
  camera.id = "pythonCameraFeed";
  camera.alt = "Live hand tracking camera";
  stage.insertBefore(camera, canvas);

  const status = document.createElement("div");
  status.id = "pythonTrackingStatus";
  status.textContent = "TRACKER · CONNECTING";
  stage.appendChild(status);

  const cursor = document.createElement("div");
  cursor.id = "holoAirMouse";
  cursor.innerHTML = '<div class="pointer"></div><span>AIR MOUSE</span>';
  document.body.appendChild(cursor);

  const css = document.createElement("style");
  css.textContent = `
    .stage #pythonCameraFeed {
      position:absolute;
      inset:0;
      width:100%;
      height:100%;
      object-fit:cover;
      z-index:0;
      opacity:.82;
      pointer-events:none;
    }

    .stage #viewport {
      position:relative;
      z-index:1;
      background:transparent;
    }

    #pythonTrackingStatus {
      position:absolute;
      top:12px;
      left:12px;
      z-index:8;
      padding:7px 11px;
      border:1px solid var(--line);
      border-radius:7px;
      background:rgba(30,37,46,.94);
      color:var(--muted);
      font-size:11px;
      pointer-events:none;
    }

    #pythonTrackingStatus[data-state="connected"] {
      color:var(--good);
      border-color:var(--good);
    }

    #holoAirMouse {
      position:fixed;
      left:50%;
      top:50%;
      z-index:100000;
      pointer-events:none;
      display:none;
      transform:translate(-50%,-50%);
      will-change:left,top;
    }

    #holoAirMouse .pointer {
      width:23px;
      height:23px;
      border:2px solid #8cc7c1;
      border-radius:50%;
      background:rgba(140,199,193,.15);
      box-shadow:0 0 14px rgba(140,199,193,.5);
    }

    #holoAirMouse span {
      position:absolute;
      left:19px;
      top:-8px;
      white-space:nowrap;
      padding:5px 8px;
      border-radius:5px;
      background:rgba(30,37,46,.96);
      color:#8cc7c1;
      font:10px Arial;
      letter-spacing:1px;
    }

    #holoAirMouse.pinching .pointer {
      background:#8cc7c1;
      transform:scale(.72);
    }

    #holoAirMouse.pinching span {
      color:white;
    }
  `;
  document.head.appendChild(css);

  let socket = null;
  let retryTimer = null;
  let lastFrame = "";

  let cursorX = innerWidth / 2;
  let cursorY = innerHeight / 2;
  let targetX = cursorX;
  let targetY = cursorY;

  let filteredX = null;
  let filteredY = null;
  let previousLeft = null;
  let previousZoom = null;

  let pinchWasActive = false;
  let pinchFrames = 0;
  let releaseFrames = 0;
  let stablePinch = false;
  let pinchStartTime = 0;
  let lastSelectionTime = 0;
  let lastZoomTime = 0;

  const clamp = (v, min, max) =>
    Math.max(min, Math.min(max, v));

  const debug = () => window.__atlasDebug;
  const renderer = () => debug()?.renderer;

  function updateStatus(message, connected = false) {
    status.textContent = message;
    status.dataset.state = connected ? "connected" : "disconnected";
  }

  // Smooth air mouse with adaptive response.
  function updateCursor(hand) {
    if (!hand?.index_tip) {
      cursor.style.display = "none";
      filteredX = null;
      filteredY = null;
      pinchFrames = 0;
      releaseFrames = 0;
      stablePinch = false;
      pinchWasActive = false;
      return;
    }

    const p = hand.index_tip;
    const nx = clamp((p.x - 0.18) / 0.64, 0, 1);
    const ny = clamp((p.y - 0.16) / 0.68, 0, 1);

    const rawX = nx * innerWidth;
    const rawY = ny * innerHeight;

    if (filteredX === null) {
      filteredX = rawX;
      filteredY = rawY;
    } else {
      const dx = rawX - filteredX;
      const dy = rawY - filteredY;
      const deadZone = 2;

      const alpha = Math.max(Math.abs(dx), Math.abs(dy)) > 35
        ? 0.58 : 0.38;

      filteredX += (Math.abs(dx) < deadZone ? 0 : dx) * alpha;
      filteredY += (Math.abs(dy) < deadZone ? 0 : dy) * alpha;
    }

    cursorX = filteredX;
    cursorY = filteredY;

    cursor.style.left = cursorX + "px";
    cursor.style.top = cursorY + "px";
    cursor.style.display = "block";

    // Require both the Python gesture and a reliable pinch ratio.
    const ratio = Number(hand.pinch_ratio);
    const pinchCandidate =
      hand.gesture === "PINCH" &&
      Number.isFinite(ratio) &&
      ratio > 0 &&
      ratio < 0.80;

    if (pinchCandidate) {
      pinchFrames++;
      releaseFrames = 0;
    } else {
      releaseFrames++;
      pinchFrames = 0;
    }

    if (!stablePinch && pinchFrames >= 3) {
      stablePinch = true;
      const now = performance.now();

      if (now - lastSelectionTime > 650) {
        const target = document.elementFromPoint(cursorX, cursorY);

        if (target && !canvas.contains(target)) {
          const control = target.closest(
            'button, a, [role="button"], input, select, [data-action]'
          );

          if (control && !control.disabled) {
            control.click();
            lastSelectionTime = now;
          }
        } else {
          const rect = canvas.getBoundingClientRect();

          if (
            cursorX >= rect.left && cursorX <= rect.right &&
            cursorY >= rect.top && cursorY <= rect.bottom
          ) {
            try {
              const r = renderer();
              const a = debug()?.atlas;

              if (r && a?.concepts) {
                const picked = r.pick(cursorX, cursorY);

                if (picked >= 0) {
                  const ci = a.conceptOf(picked);

                  if (Number.isInteger(ci) && ci >= 0 &&
                      ci < a.concepts.length) {
                    debug().select(ci);
                    lastSelectionTime = now;
                  }
                }
              }
            } catch (e) {
              console.warn("Atlas selection:", e);
            }
          }
        }
      }
    }

    if (stablePinch && releaseFrames >= 3) {
      stablePinch = false;
    }

    cursor.classList.toggle("pinching", stablePinch);
    cursor.querySelector("span").textContent =
      stablePinch ? "PINCH" : "AIR MOUSE";

    pinchWasActive = stablePinch;
  }
  // Left physical hand: horizontal rotation and vertical movement.
  function updateLeftHand(hand) {
    const r = renderer();

    if (!hand?.palm || !r) {
      previousLeft = null;
      return;
    }

    const p = hand.palm;

    if (hand.gesture !== "OPEN PALM") {
      previousLeft = { x: p.x, y: p.y };
      return;
    }

    if (previousLeft) {
      const dx = p.x - previousLeft.x;
      const dy = p.y - previousLeft.y;

      if (Math.abs(dx) + Math.abs(dy) > 0.004) {
        r.orbit(
          clamp(dx * 650, -12, 12),
          0
        );

        r.pan(
          0,
          clamp(-dy * 550, -12, 12)
        );
      }
    }

    previousLeft = { x: p.x, y: p.y };
  }

  // Two-hand zoom with noise filtering and rate limiting.
  function updateZoom(right, left) {
    const r = renderer();

    if (!right?.palm || !left?.palm || !r) {
      previousZoom = null;
      return;
    }

    const dx = right.palm.x - left.palm.x;
    const dy = right.palm.y - left.palm.y;
    const separation = Math.hypot(dx, dy);

    if (!Number.isFinite(separation)) return;

    if (previousZoom === null) {
      previousZoom = separation;
      return;
    }

    const change = separation - previousZoom;
    previousZoom += change * 0.18;

    const now = performance.now();

    if (now - lastZoomTime < 45) return;

    if (Math.abs(change) > 0.003) {
      const factor = Math.exp(
        clamp(change * 1.5, -0.035, 0.035)
      );

      r.zoom(factor);
      lastZoomTime = now;
    }
  }

  function handleTracking(data) {
    const hands = data.hands || {};

    // Mirrored webcam label mapping.
    const right = hands.Left;
    const left = hands.Right;

    updateStatus(
      `TRACKER · ${Number(data.fps || 0).toFixed(0)} FPS · ${Object.keys(hands).length} HANDS`,
      true
    );

    if (data.frame && data.frame !== lastFrame) {
      camera.onload = () => {
        camera.dataset.loaded = "true";
        updateStatus("TRACKER · CAMERA LIVE · " +
          Number(data.fps || 0).toFixed(0) + " FPS", true);
      };

      camera.onerror = () => {
        updateStatus("TRACKER · CAMERA FRAME ERROR");
      };

      camera.src = data.frame.startsWith("data:image")
        ? data.frame
        : "data:image/jpeg;base64," + data.frame;

      lastFrame = data.frame;
    }

    updateCursor(right);
    updateLeftHand(left);
    updateZoom(right, left);
  }

  function connect() {
    if (
      socket &&
      (
        socket.readyState === WebSocket.OPEN ||
        socket.readyState === WebSocket.CONNECTING
      )
    ) return;

    updateStatus("TRACKER · CONNECTING");

    try {
      socket = new WebSocket("ws://127.0.0.1:8765");

      socket.onopen = () => {
        updateStatus("TRACKER · CONNECTED", true);
      };

      socket.onmessage = event => {
        let data;

        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

        if (data.type === "status") {
          if (data.status === "error") {
            updateStatus("TRACKER ERROR · " + data.message);
          }
          return;
        }

        if (data.type === "tracking") {
          handleTracking(data);
        }
      };

      socket.onclose = () => {
        socket = null;
        updateStatus("TRACKER · RECONNECTING");
        clearTimeout(retryTimer);
        retryTimer = setTimeout(connect, 1500);
      };

      socket.onerror = () => socket?.close();

    } catch (error) {
      updateStatus("TRACKER · CONNECTION FAILED");
      retryTimer = setTimeout(connect, 1500);
    }
  }


  connect();

  console.log("HoloHuman3D stable gesture controller loaded.");
})();
