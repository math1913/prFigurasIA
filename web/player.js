"use strict";

const channel = document.body.dataset.channel;
const stage = document.querySelector("#stage");
const connection = document.querySelector("#connection");
let token = null;
let latest = null;
let expiryTimer = null;
let pendingCompletion = null;
let finishedEvent = null;
let activeVideo = null;
let renderVersion = 0;
let overlay = null;

async function request(path, options = {}) {
  const response = await fetch(path, {cache: "no-store", signal: AbortSignal.timeout(2000), ...options});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function placeholder(content, isEvent) {
  const section = document.createElement("section");
  section.className = `placeholder ${isEvent ? "is-event" : ""}`;
  const brand = document.createElement("div");
  brand.className = "brand";
  brand.textContent = "BIGBANG";
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = channel === "figuras" ? "El universo de las figuras" : "Objetos que cuentan historias";
  const title = document.createElement("h1");
  title.textContent = content.title;
  const description = document.createElement("p");
  description.className = "invitation";
  description.textContent = isEvent ? "Descubre su historia" : channel === "figuras"
    ? "Muestra una figura o escanea su código y descubre su historia."
    : "Levanta un objeto de su base y descubre su historia.";
  const orbit = document.createElement("div");
  orbit.className = "orbit";
  orbit.setAttribute("aria-hidden", "true");
  section.append(brand, orbit, eyebrow, title, description);
  return section;
}

function render(content, state, fallback = null) {
  const version = ++renderVersion;
  if (activeVideo) {
    activeVideo.pause();
    activeVideo.removeAttribute("src");
    activeVideo.load();
    activeVideo = null;
  }
  if (!content.src) {
    stage.replaceChildren(placeholder(content, state.mode === "event"));
    return;
  }
  const video = document.createElement("video");
  activeVideo = video;
  video.src = content.src;
  video.muted = content.muted;
  video.loop = state.mode === "base";
  video.playsInline = true;
  video.preload = "auto";
  video.setAttribute("aria-label", content.title);
  video.addEventListener("ended", () => {
    if (version === renderVersion && state.mode === "event") finish(state.event_id);
  });
  video.addEventListener("error", () => {
    if (version !== renderVersion) return;
    console.error("No se puede reproducir", content.src);
    if (state.mode === "event") finish(state.event_id);
    else if (fallback?.src && fallback.src !== content.src) render(fallback, state);
    else render({...content, src: null}, state);
  });
  video.addEventListener("loadedmetadata", () => {
    if (version !== renderVersion) return;
    if (state.mode === "event" && Number.isFinite(video.duration)) {
      if (state.elapsed_seconds >= video.duration) {
        finish(state.event_id);
        return;
      }
      if (state.elapsed_seconds > 0.5) video.currentTime = state.elapsed_seconds;
    }
    start(video);
  });
  stage.replaceChildren(video);
}

// Modo kiosco, sin botones: si el navegador bloquea el sonido, se reproduce sin sonido.
function start(video) {
  video.play().catch(() => {
    if (video !== activeVideo || video.muted) return;
    console.warn("El navegador bloquea el sonido; se reproduce sin sonido", video.src);
    video.muted = true;
    start(video);
  });
}

async function sendCompletion() {
  if (!pendingCompletion) return;
  const id = pendingCompletion;
  await request(`/api/complete/${channel}`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({event_id: id}),
  });
  if (pendingCompletion === id) pendingCompletion = null;
}

function finish(id) {
  if (!latest || latest.event_id !== id || finishedEvent === id) return;
  clearTimeout(expiryTimer);
  finishedEvent = id;
  pendingCompletion = id;
  // Vuelve a la base incluso si se pierde la conexión al finalizar el vídeo.
  render(latest.base, {mode: "base"}, latest.fallback_base);
  sendCompletion().catch(() => { connection.hidden = false; });
}

// Indicadores NFC de /overlay sobre el vídeo, según nfc.overlay_channels.
function syncOverlay(enabled) {
  if (Boolean(enabled) === Boolean(overlay)) return;
  if (overlay) {
    overlay.remove();
    overlay = null;
    return;
  }
  overlay = document.createElement("iframe");
  overlay.className = "overlay-frame";
  overlay.src = "/overlay";
  overlay.title = "Indicadores NFC";
  overlay.tabIndex = -1;
  stage.after(overlay);
}

function applySnapshot(state) {
  latest = state;
  syncOverlay(state.overlay);
  const nextToken = `${state.session}:${state.revision}`;
  if (nextToken === token) return;
  token = nextToken;
  clearTimeout(expiryTimer);
  if (state.event_id && state.event_id === finishedEvent) return;
  render(state.content, state, state.fallback_base);
  if (state.mode === "event") {
    expiryTimer = setTimeout(() => finish(state.event_id), state.remaining_ms);
  }
}

async function poll() {
  try {
    await sendCompletion();
    applySnapshot(await request(`/api/state/${channel}`));
    connection.hidden = true;
  } catch (error) {
    connection.hidden = false;
  } finally {
    // Nada debe quedarse en pausa (p. ej., tras un cambio de salida de audio): se reanuda.
    if (activeVideo?.paused && !activeVideo.ended && activeVideo.readyState >= 2) start(activeVideo);
    setTimeout(poll, 250);
  }
}

stage.replaceChildren(placeholder({title: "Todo empieza con una historia"}, false));
poll();
