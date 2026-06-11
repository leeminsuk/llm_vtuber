/**
 * llm_vtuber quick character switcher.
 *
 * Injected by the server into the frontend's index.html BEFORE the app
 * bundle (classic scripts run before module scripts), so it can wrap
 * window.WebSocket and piggyback on the app's own /client-ws connection.
 * Clicking a chip sends the same "switch-config" message the settings
 * dialog sends — model, voice and persona switch together in one click.
 */
(() => {
  "use strict";

  const LABELS = {
    ko_yuna: "💁‍♀️ 유나",
    ko_hana: "🎮 하나",
    ko_sora: "📚 소라",
    ko_rin: "💻 린",
    ko_mao: "🐱 마오",
    en_nuke_debator: "⚔️ 토론가 밀리 (영어)",
    unhelpful_ai: "🙃 불친절 AI (영어)",
    "米粒": "🍚 미리 (중국어)",
    "翻译腔-神经大人": "🎭 번역투 대인 (중국어)",
  };

  // ── 1. Capture the app's websocket ────────────────────────────────
  const NativeWS = window.WebSocket;
  let appWs = null;
  const onMessage = [];

  function hook(ws, url) {
    if (!String(url).includes("/client-ws")) return ws;
    appWs = ws;
    ws.addEventListener("message", (e) => {
      let d;
      try {
        d = JSON.parse(e.data);
      } catch {
        return;
      }
      onMessage.forEach((f) => f(d));
    });
    ws.addEventListener("open", () => {
      // ask for the character list once the app's socket is live
      setTimeout(() => send({ type: "fetch-configs" }), 500);
    });
    return ws;
  }

  window.WebSocket = function (url, protocols) {
    const ws =
      protocols !== undefined ? new NativeWS(url, protocols) : new NativeWS(url);
    return hook(ws, url);
  };
  window.WebSocket.prototype = NativeWS.prototype;
  for (const k of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
    window.WebSocket[k] = NativeWS[k];
  }

  function send(obj) {
    if (appWs && appWs.readyState === NativeWS.OPEN) {
      appWs.send(JSON.stringify(obj));
    }
  }

  // ── 2. Chip bar UI ─────────────────────────────────────────────────
  const css = `
  #qs-bar {
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 8px; z-index: 9999; align-items: center;
    max-width: min(92vw, 1100px); overflow-x: auto; scrollbar-width: none;
    padding: 6px 10px; border-radius: 999px;
    background: rgba(15, 18, 28, 0.72);
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
    font-family: -apple-system, "Apple SD Gothic Neo", sans-serif;
  }
  #qs-bar::-webkit-scrollbar { display: none; }
  #qs-bar.qs-collapsed .qs-chip:not(.qs-active) { display: none; }
  .qs-toggle {
    border: none; background: transparent; cursor: pointer;
    color: rgba(235, 238, 245, 0.55); font-size: 12px; padding: 4px 6px;
    flex: none;
  }
  .qs-toggle:hover { color: #fff; }
  .qs-chip {
    border: 1px solid transparent; border-radius: 999px;
    padding: 6px 14px; font-size: 13px; font-weight: 600;
    color: rgba(235, 238, 245, 0.85); background: transparent;
    cursor: pointer; white-space: nowrap;
    transition: all 0.18s ease;
  }
  .qs-chip:hover {
    background: rgba(255, 255, 255, 0.10); transform: translateY(-1px);
  }
  .qs-chip.qs-active {
    background: linear-gradient(135deg, #7c5cff, #4f8cff);
    color: #fff; border-color: rgba(255, 255, 255, 0.25);
    box-shadow: 0 2px 12px rgba(99, 110, 255, 0.55);
  }
  .qs-chip.qs-busy { opacity: 0.45; pointer-events: none; }
  `;

  function buildBar(configs) {
    let bar = document.getElementById("qs-bar");
    if (bar) bar.remove();
    bar = document.createElement("div");
    bar.id = "qs-bar";

    // ko_* presets first (they pair model+voice+persona), then the rest
    const chars = configs
      .filter((c) => c.filename !== "conf.yaml")
      .sort((a, b) => {
        const ak = a.name.startsWith("ko_") ? 0 : 1;
        const bk = b.name.startsWith("ko_") ? 0 : 1;
        return ak - bk || a.name.localeCompare(b.name);
      });

    for (const c of chars) {
      const btn = document.createElement("button");
      btn.className = "qs-chip";
      btn.dataset.conf = c.name;
      btn.textContent = LABELS[c.name] || c.name;
      btn.title = c.filename;
      btn.addEventListener("click", () => {
        bar.querySelectorAll(".qs-chip").forEach((b) =>
          b.classList.add("qs-busy")
        );
        send({ type: "switch-config", file: c.filename });
      });
      bar.appendChild(btn);
    }
    const toggle = document.createElement("button");
    toggle.className = "qs-toggle";
    toggle.textContent = "◀";
    toggle.title = "접기/펼치기";
    toggle.addEventListener("click", () => {
      const collapsed = bar.classList.toggle("qs-collapsed");
      toggle.textContent = collapsed ? "▶" : "◀";
    });
    bar.appendChild(toggle);
    document.body.appendChild(bar);
  }

  function markActive(confName) {
    const bar = document.getElementById("qs-bar");
    if (!bar) return;
    bar.querySelectorAll(".qs-chip").forEach((b) => {
      b.classList.remove("qs-busy");
      b.classList.toggle("qs-active", b.dataset.conf === confName);
    });
  }

  onMessage.push((d) => {
    if (d.type === "config-files" && Array.isArray(d.configs)) {
      const render = () => buildBar(d.configs);
      document.body ? render() : document.addEventListener("DOMContentLoaded", render);
    }
    if (d.type === "set-model-and-conf") {
      markActive(d.conf_name);
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  });
})();
