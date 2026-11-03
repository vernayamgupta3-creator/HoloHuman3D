(() => {
  if (window.HoloCamera) return;

  let stream = null;
  let video = null;
  let button = null;
  let status = null;

  function setup() {
    const app = document.querySelector('#app');
    const tools = document.querySelector('.topbar .tools');

    if (!app || !tools) {
      console.error('HoloHuman3D: Atlas interface not found.');
      return;
    }

    // Camera background
    video = document.createElement('video');
    video.id = 'holoCameraBackground';
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;

    document.body.insertBefore(video, app);

    // Camera control
    button = document.createElement('button');
    button.id = 'holoCameraToggle';
    button.className = 'icon-btn';
    button.type = 'button';
    button.textContent = 'Enable Camera';
    button.setAttribute('aria-pressed', 'false');

    tools.appendChild(button);

    status = document.createElement('span');
    status.id = 'holoCameraStatus';
    status.textContent = 'Camera off';
    tools.appendChild(status);

    // Camera styling
    const style = document.createElement('style');
    style.textContent = `
      #holoCameraBackground {
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
        transform: scaleX(-1);
        z-index: 0;
        display: none;
        background: #101820;
      }

      #app {
        position: relative;
        z-index: 1;
        background: transparent !important;
      }

      #holoCameraStatus {
        color: var(--muted);
        font-size: 12px;
        white-space: nowrap;
      }

      #holoCameraToggle.camera-active {
        background: var(--film);
        color: var(--film-ink);
        border-color: var(--film);
      }

      @media (max-width: 850px) {
        #holoCameraStatus {
          display: none;
        }
      }
    `;
    document.head.appendChild(style);

    button.addEventListener('click', toggleCamera);
  }

  async function toggleCamera() {
    if (stream) {
      stopCamera();
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      status.textContent = 'Camera unavailable';
      alert('Camera access requires localhost or a secure HTTPS connection.');
      return;
    }

    button.disabled = true;
    status.textContent = 'Connecting...';

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: 'user',
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });

      video.srcObject = stream;
      await video.play();

      video.style.display = 'block';
      button.textContent = 'Disable Camera';
      button.classList.add('camera-active');
      button.setAttribute('aria-pressed', 'true');
      status.textContent = 'Camera active';

    } catch (error) {
      console.error('Camera error:', error);

      stream?.getTracks().forEach(track => track.stop());
      stream = null;

      status.textContent = 'Camera unavailable';

      alert(
        error.name === 'NotAllowedError'
          ? 'Camera permission was denied. Allow camera access in your browser.'
          : 'Could not start the camera. Check that your camera is connected and not being used by another app.'
      );
    } finally {
      button.disabled = false;
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }

    video.pause();
    video.srcObject = null;
    video.style.display = 'none';

    button.textContent = 'Enable Camera';
    button.classList.remove('camera-active');
    button.setAttribute('aria-pressed', 'false');
    status.textContent = 'Camera off';
  }

  window.addEventListener('beforeunload', stopCamera);

  window.HoloCamera = {
    start: toggleCamera,
    stop: stopCamera,
    isActive: () => !!stream
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup, { once: true });
  } else {
    setup();
  }
})();