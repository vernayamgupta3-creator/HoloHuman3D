(() => {
  if (window.HoloHands) return;

  const VERSION = '0.10.14';
  const WASM_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}/wasm`;
  const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

  let landmarker = null;
  let running = false;
  let busy = false;
  let raf = 0;
  let lastVideoTime = -1;
  let video, canvas, ctx, button, status, stats;

  let fps = 0;
  let frameCount = 0;
  let fpsTime = 0;

  const hands = new Map();
  const previousPinches = new Map();

  let rotationPrevious = null;
  let twoHandPreviousY = null;
  let twoHandSmoothedY = null;
  let zoomPreviousDistance = null;
  let zoomSmoothedDistance = null;
  let lastZoomTime = 0;
  let lastRotationTime = 0;

  const connections = [
    [0,1],[1,2],[2,3],[3,4],
    [0,5],[5,6],[6,7],[7,8],
    [5,9],[9,10],[10,11],[11,12],
    [9,13],[13,14],[14,15],[15,16],
    [13,17],[17,18],[18,19],[19,20],[0,17]
  ];

  const clamp = (v, min, max) =>
    Math.max(min, Math.min(max, v));

  const distance = (a, b) =>
    Math.hypot(a.x - b.x, a.y - b.y);

  function setup() {
    const tools = document.querySelector('.topbar .tools');
    if (!tools) {
      console.error('HoloHands: Atlas toolbar not found.');
      return;
    }

    canvas = document.createElement('canvas');
    canvas.id = 'holoHandsOverlay';
    canvas.setAttribute('aria-label', 'Live hand tracking landmarks');
    document.body.appendChild(canvas);
    ctx = canvas.getContext('2d');

    const style = document.createElement('style');
    style.textContent = `
      #holoHandsOverlay {
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        z-index: 2;
        pointer-events: none;
        transform: scaleX(-1);
      }
      #holoHandsToggle { border-color: #55d6be; }
      #holoHandsToggle.active {
        background: #55d6be;
        color: #071b1a;
      }
      #holoHandsStats {
        position: fixed;
        right: 16px;
        bottom: 44px;
        z-index: 5;
        padding: 10px 13px;
        border: 1px solid rgba(85,214,190,.45);
        border-radius: 9px;
        background: rgba(5,15,25,.82);
        color: #d9fff7;
        font: 12px/1.8 system-ui,sans-serif;
        pointer-events: none;
        display: none;
        backdrop-filter: blur(10px);
      }
      #holoHandsStats strong { color: #55d6be; }
      #holoHandsStatus {
        color: var(--muted);
        font-size: 12px;
      }
    `;
    document.head.appendChild(style);

    button = document.createElement('button');
    button.id = 'holoHandsToggle';
    button.type = 'button';
    button.className = 'icon-btn';
    button.textContent = 'Start Hand Tracking';
    tools.appendChild(button);

    status = document.createElement('span');
    status.id = 'holoHandsStatus';
    tools.appendChild(status);

    stats = document.createElement('div');
    stats.id = 'holoHandsStats';
    stats.innerHTML =
      '<strong>HOLO HAND TRACKING</strong><br>Hands: 0/2<br>Controls: Waiting<br>FPS: 0';
    document.body.appendChild(stats);

    button.addEventListener('click', toggle);
    resizeCanvas();
  }

  function resizeCanvas() {
    if (!canvas || !ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(innerWidth * dpr);
    canvas.height = Math.round(innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  async function loadModel() {
    if (landmarker) return;

    status.textContent = 'Loading AI model...';

    const vision = await import(
      `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}/+esm`
    );

    const files = await vision.FilesetResolver.forVisionTasks(WASM_URL);

    try {
      landmarker = await vision.HandLandmarker.createFromOptions(files, {
        baseOptions: {
          modelAssetPath: MODEL_URL,
          delegate: 'GPU'
        },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6
      });
    } catch (gpuError) {
      console.warn('GPU initialization failed; trying CPU.', gpuError);

      landmarker = await vision.HandLandmarker.createFromOptions(files, {
        baseOptions: {
          modelAssetPath: MODEL_URL,
          delegate: 'CPU'
        },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6
      });
    }
  }

  async function toggle() {
    if (running) {
      stop();
      return;
    }

    button.disabled = true;

    try {
      if (!window.HoloCamera?.isActive()) {
        await window.HoloCamera.start();
      }

      if (!window.HoloCamera?.isActive()) {
        throw new Error('Enable camera access first.');
      }

      video = document.getElementById('holoCameraBackground');

      if (!video || !video.videoWidth) {
        throw new Error('Camera video is not ready.');
      }

      await loadModel();

      resetControls();
      running = true;
      button.textContent = 'Stop Hand Tracking';
      button.classList.add('active');
      status.textContent = 'Tracking active';
      stats.style.display = 'block';

      lastVideoTime = -1;
      frameCount = 0;
      fpsTime = performance.now();

      resizeCanvas();
      loop();
    } catch (error) {
      console.error('HoloHands:', error);
      status.textContent = 'Tracking unavailable';
      alert('Hand tracking could not start: ' + error.message);
      stop();
    } finally {
      button.disabled = false;
    }
  }

  function resetControls() {
    hands.clear();
    previousPinches.clear();
    rotationPrevious = null;
    twoHandPreviousY = null;
    twoHandSmoothedY = null;
    zoomPreviousDistance = null;
    zoomSmoothedDistance = null;
  }

  function getVideoRect() {
    const vw = video.videoWidth;
    const vh = video.videoHeight;

    const scale = Math.min(innerWidth / vw, innerHeight / vh);
    const width = vw * scale;
    const height = vh * scale;

    return {
      x: (innerWidth - width) / 2,
      y: (innerHeight - height) / 2,
      width,
      height
    };
  }

  function getPalm(points) {
    const ids = [0, 5, 9, 13, 17];

    return {
      x: ids.reduce((sum, i) => sum + points[i].x, 0) / ids.length,
      y: ids.reduce((sum, i) => sum + points[i].y, 0) / ids.length
    };
  }

  function classify(points, wasPinching) {
    const palmWidth = Math.max(
      0.001,
      distance(points[5], points[17])
    );

    const pinchRatio = distance(points[4], points[8]) / palmWidth;

    const pinching = wasPinching
      ? pinchRatio < 0.85
      : pinchRatio < 0.70;

    if (pinching) return 'PINCH';

    const fingers = [
      points[8].y < points[6].y,
      points[12].y < points[10].y,
      points[16].y < points[14].y,
      points[20].y < points[18].y
    ];

    if (fingers.every(Boolean)) return 'OPEN PALM';
    if (fingers.every(v => !v)) return 'FIST';

    if (fingers[0] && !fingers[1] && !fingers[2] && !fingers[3]) {
      return 'POINTING';
    }

    return 'NEUTRAL';
  }

  function getAtlas() {
    const atlas = window.__atlasDebug;

    if (!atlas?.renderer || typeof atlas.select !== 'function') {
      return null;
    }

    return atlas;
  }

  function selectAtFinger(point, rect) {
    const atlas = getAtlas();
    const viewport = document.getElementById('viewport');

    if (!atlas || !viewport) return;

    // The camera is mirrored, so reverse the normalized X coordinate.
    const clientX = rect.x + (1 - point.x) * rect.width;
    const clientY = rect.y + point.y * rect.height;

    // Only allow selection when the fingertip is actually over the 3D viewer.
    const bounds = viewport.getBoundingClientRect();

    if (
      clientX < bounds.left || clientX > bounds.right ||
      clientY < bounds.top || clientY > bounds.bottom
    ) return;

    const element = atlas.renderer.pick(clientX, clientY);

    if (element == null || element < 0) return;

    const concept = atlas.atlas.conceptOf(element);

    if (concept != null && concept >= 0) {
      atlas.select(concept);
    }
  }

  function updateRotation(left) {
    if (!left || left.gesture !== 'PINCH') {
      rotationPrevious = null;
      return;
    }

    const now = performance.now();
    if (now - lastRotationTime < 25) return;
    lastRotationTime = now;

    const palm = left.palm;

    if (!rotationPrevious) {
      rotationPrevious = { x: palm.x, y: palm.y };
      return;
    }

    const dx = clamp((palm.x - rotationPrevious.x) * 700, -12, 12);
    const dy = clamp((palm.y - rotationPrevious.y) * 700, -12, 12);

    rotationPrevious.x += 0.35 * (palm.x - rotationPrevious.x);
    rotationPrevious.y += 0.35 * (palm.y - rotationPrevious.y);

    if (Math.abs(dx) > 0.8 || Math.abs(dy) > 0.8) {
      getAtlas()?.renderer.orbit(dx, dy);
    }
  }

  function updateTwoHandControls(left, right) {
    const bothOpen =
      left && right &&
      left.gesture === 'OPEN PALM' &&
      right.gesture === 'OPEN PALM';

    if (!bothOpen) {
      twoHandPreviousY = null;
      twoHandSmoothedY = null;
      zoomPreviousDistance = null;
      zoomSmoothedDistance = null;
      return false;
    }

    const now = performance.now();
    const centerY = (left.palm.y + right.palm.y) / 2;

    if (twoHandSmoothedY === null) {
      twoHandSmoothedY = centerY;
    }

    twoHandSmoothedY =
      0.75 * twoHandSmoothedY + 0.25 * centerY;

    if (twoHandPreviousY !== null) {
      const movement = twoHandSmoothedY - twoHandPreviousY;
      const panY = movement * innerHeight * 2;

      if (Math.abs(panY) > 0.5) {
        getAtlas()?.renderer.pan(0, panY);
      }
    }

    twoHandPreviousY = twoHandSmoothedY;

    // Distance between palms controls zoom.
    const separation = distance(left.palm, right.palm);

    if (zoomSmoothedDistance === null) {
      zoomSmoothedDistance = separation;
    }

    zoomSmoothedDistance =
      0.75 * zoomSmoothedDistance + 0.25 * separation;

    if (zoomPreviousDistance !== null && now - lastZoomTime >= 40) {
      const change = zoomSmoothedDistance - zoomPreviousDistance;

      if (Math.abs(change) > 0.0015) {
        const factor = clamp(1 + change * 4, 0.94, 1.06);
        getAtlas()?.renderer.zoom(factor);
        lastZoomTime = now;
      }
    }

    zoomPreviousDistance = zoomSmoothedDistance;
    rotationPrevious = null;

    return true;
  }

  function drawHands(result) {
    ctx.clearRect(0, 0, innerWidth, innerHeight);

    if (!video?.videoWidth) return;

    const rect = getVideoRect();
    const rawHands = result.landmarks || [];
    const classifications = result.handedness || [];

    const detected = new Map();

    rawHands.forEach((points, index) => {
      const label = classifications[index]?.[0]?.categoryName || 'Unknown';

      // Preserve the physical left/right mapping used by the Python application.
      const side = label === 'Left' ? 'right'
        : label === 'Right' ? 'left'
        : null;

      if (!side) return;

      const old = hands.get(side);
      const smoothed = points.map((p, i) => {
        if (!old) return { x: p.x, y: p.y, z: p.z || 0 };

        const previous = old.points[i];
        const movement = Math.hypot(
          p.x - previous.x,
          p.y - previous.y
        );

        const alpha = movement > 0.12 ? 0.48 : 0.22;

        return {
          x: previous.x + (p.x - previous.x) * alpha,
          y: previous.y + (p.y - previous.y) * alpha,
          z: (previous.z || 0) +
            ((p.z || 0) - (previous.z || 0)) * alpha
        };
      });

      const wasPinching = previousPinches.get(side) || false;
      const gesture = classify(smoothed, wasPinching);
      const palm = getPalm(smoothed);

      detected.set(side, {
        points: smoothed,
        palm,
        gesture
      });

      previousPinches.set(side, gesture === 'PINCH');

      const isLeft = side === 'left';
      const color = isLeft ? '#55d6be' : '#ffbf69';

      ctx.lineWidth = 2.5;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;

      for (const [a, b] of connections) {
        ctx.beginPath();
        ctx.moveTo(rect.x + smoothed[a].x * rect.width,
                   rect.y + smoothed[a].y * rect.height);
        ctx.lineTo(rect.x + smoothed[b].x * rect.width,
                   rect.y + smoothed[b].y * rect.height);
        ctx.stroke();
      }

      smoothed.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(
          rect.x + p.x * rect.width,
          rect.y + p.y * rect.height,
          i === 4 || i === 8 ? 5 : 2.5,
          0,
          Math.PI * 2
        );
        ctx.fill();
      });

      const tip = smoothed[8];

      // Cursor is controlled by the physical right hand.
      if (!isLeft) {
        const cursorX = (1 - tip.x) * innerWidth;
        const cursorY = tip.y * innerHeight;

        ctx.beginPath();
        ctx.arc(cursorX, cursorY, 17, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(cursorX, cursorY, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
      }

      const palmX = rect.x + palm.x * rect.width;
      const palmY = rect.y + palm.y * rect.height;

      ctx.fillStyle = '#ffffff';
      ctx.font = '12px system-ui';
      ctx.fillText(
        `${side.toUpperCase()} / ${gesture}`,
        clamp(palmX + (isLeft ? -105 : 18), 8, innerWidth - 130),
        clamp(palmY - 18, 18, innerHeight - 8)
      );

      // Right-hand pinch selects a structure once per pinch.
      if (!isLeft && gesture === 'PINCH' && !wasPinching) {
        selectAtFinger(tip, rect);
      }
    });

    hands.clear();
    for (const [side, hand] of detected) {
      hands.set(side, hand);
    }

    const left = hands.get('left');
    const right = hands.get('right');

    const twoHandMode = updateTwoHandControls(left, right);

    if (!twoHandMode) {
      updateRotation(left);
    }

    const leftText = left?.gesture || 'WAITING';
    const rightText = right?.gesture || 'WAITING';

    let controlText = 'Waiting for hands';

    if (twoHandMode) {
      controlText = 'Two-hand pan + zoom';
    } else if (left?.gesture === 'PINCH') {
      controlText = 'Left-hand rotation';
    } else if (right?.gesture === 'PINCH') {
      controlText = 'Right-hand selection';
    } else if (left || right) {
      controlText = 'Hand detected';
    }

    stats.innerHTML =
      `<strong>HOLO HAND TRACKING</strong><br>` +
      `Left: ${leftText}<br>` +
      `Right: ${rightText}<br>` +
      `Controls: ${controlText}<br>` +
      `FPS: ${fps}`;
  }

  function loop() {
    if (!running || busy) return;

    raf = requestAnimationFrame(loop);

    if (
      !video ||
      video.readyState < 2 ||
      video.currentTime === lastVideoTime
    ) return;

    busy = true;
    lastVideoTime = video.currentTime;

    try {
      const now = performance.now();
      frameCount++;

      if (now - fpsTime >= 1000) {
        fps = Math.round(frameCount * 1000 / (now - fpsTime));
        frameCount = 0;
        fpsTime = now;
      }

      const result = landmarker.detectForVideo(video, now);
      drawHands(result);
    } catch (error) {
      console.error('HoloHands frame error:', error);
      status.textContent = 'Tracking error';
    } finally {
      busy = false;
    }
  }

  function stop() {
    running = false;
    cancelAnimationFrame(raf);
    resetControls();

    if (ctx && canvas) {
      ctx.clearRect(0, 0, innerWidth, innerHeight);
    }

    if (button) {
      button.textContent = 'Start Hand Tracking';
      button.classList.remove('active');
    }

    if (status) status.textContent = 'Tracking stopped';
    if (stats) stats.style.display = 'none';
  }

  window.addEventListener('resize', resizeCanvas);
  window.addEventListener('beforeunload', stop);

  window.HoloHands = {
    start: toggle,
    stop,
    isRunning: () => running
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup, { once: true });
  } else {
    setup();
  }
})();
