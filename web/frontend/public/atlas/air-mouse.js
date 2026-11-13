(() => {
  if (window.__airMouseStarted) return;
  window.__airMouseStarted = true;

  const cursor = document.createElement("div");
  cursor.id = "holoAirMouse";
  cursor.innerHTML = '<div class="pointer"></div><span>AIR MOUSE</span>';
  document.body.appendChild(cursor);

  let x = innerWidth / 2;
  let y = innerHeight / 2;
  let socket;

  const style = document.createElement("style");
  style.textContent = `
    #holoAirMouse {
      position:fixed; left:50%; top:50%; z-index:100000;
      pointer-events:none; display:none; transform:translate(-50%,-50%);
    }
    #holoAirMouse .pointer {
      width:24px;height:24px;border:2px solid #8cc7c1;
      border-radius:50%;background:#8cc7c133;
      box-shadow:0 0 18px #8cc7c1;
    }
    #holoAirMouse span {
      position:absolute;left:20px;top:-8px;white-space:nowrap;
      background:#252d37;color:#8cc7c1;padding:5px 8px;
      border-radius:4px;font:10px Arial;letter-spacing:1px;
    }
    #holoAirMouse.pinching .pointer {
      background:#8cc7c1;transform:scale(.65);
      box-shadow:0 0 22px #8cc7c1;
    }
    #holoAirMouse.pinching span { color:#fff; }
  `;
  document.head.appendChild(style);

  function connect() {
    socket = new WebSocket("ws://127.0.0.1:8765");

    socket.onmessage = event => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type !== "tracking") return;

      // MediaPipe Left = physical right hand.
      const hand = data.hands?.Left;
      if (!hand?.index_tip) {
        cursor.style.display = "none";
        return;
      }

      // Amplify the movement: central 50% of camera controls
      // the full screen, allowing cursor travel beyond the hand.
      const p = hand.index_tip;
      const targetX = ((p.x - 0.25) / 0.5) * innerWidth;
      const targetY = ((p.y - 0.20) / 0.6) * innerHeight;

      x += (Math.max(0, Math.min(innerWidth, targetX)) - x) * 0.38;
      y += (Math.max(0, Math.min(innerHeight, targetY)) - y) * 0.38;

      cursor.style.left = x + "px";
      cursor.style.top = y + "px";
      cursor.style.display = "block";

      const pinch = hand.gesture === "PINCH";
      cursor.classList.toggle("pinching", pinch);
      cursor.querySelector("span").textContent =
        pinch ? "PINCH" : "AIR MOUSE";
    };

    socket.onclose = () => setTimeout(connect, 2000);
    socket.onerror = () => socket.close();
  }

  connect();
})();
