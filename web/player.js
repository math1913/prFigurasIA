/*
 * Reproductor de las pantallas /figuras y /nfc, en modo kiosco.
 *
 * Escrito en ES5 y sin APIs recientes (fetch, AbortSignal, replaceChildren,
 * promesas obligatorias...), como los contenidos de cartelería de controlStore:
 * el reproductor de Admira corre en Android con un Chromium antiguo, y una sola
 * sintaxis que no entienda impide que el script arranque y deja la pantalla en negro.
 */
"use strict";

var channel = document.body.dataset.channel;
var stage = document.querySelector("#stage");
var connection = document.querySelector("#connection");
var token = null;
var latest = null;
var expiryTimer = null;
var pendingCompletion = null;
var finishedEvent = null;
var activeVideo = null;
var renderVersion = 0;
var overlay = null;

// done(error, datos). XMLHttpRequest en lugar de fetch, que los reproductores antiguos no tienen.
function request(method, path, body, done) {
  var xhr = new XMLHttpRequest();
  var settled = false;
  function settle(error, data) {
    if (settled) return;
    settled = true;
    done(error, data);
  }
  xhr.open(method, path, true);
  xhr.timeout = 2000;
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) return;
    if (xhr.status < 200 || xhr.status >= 300) {
      settle(new Error("HTTP " + xhr.status));
      return;
    }
    var data;
    try {
      data = JSON.parse(xhr.responseText);
    } catch (error) {
      settle(error);
      return;
    }
    settle(null, data);
  };
  xhr.onerror = xhr.ontimeout = function () { settle(new Error("Sin conexión")); };
  if (body) xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send(body ? JSON.stringify(body) : null);
}

function element(tag, className, text) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function placeholder(content, isEvent) {
  var section = element("section", isEvent ? "placeholder is-event" : "placeholder");
  var orbit = element("div", "orbit");
  orbit.setAttribute("aria-hidden", "true");
  var description = isEvent ? "Descubre su historia" : channel === "figuras"
    ? "Muestra una figura o escanea su código y descubre su historia."
    : "Levanta un objeto de su base y descubre su historia.";
  section.appendChild(element("div", "brand", "BIGBANG"));
  section.appendChild(orbit);
  section.appendChild(element("p", "eyebrow", channel === "figuras" ? "El universo de las figuras" : "Objetos que cuentan historias"));
  section.appendChild(element("h1", "", content.title));
  section.appendChild(element("p", "invitation", description));
  return section;
}

function show(node) {
  while (stage.firstChild) stage.removeChild(stage.firstChild);
  stage.appendChild(node);
}

function render(content, state, fallback) {
  var version = ++renderVersion;
  if (activeVideo) {
    activeVideo.pause();
    activeVideo.removeAttribute("src");
    activeVideo.load();
    activeVideo = null;
  }
  if (!content.src) {
    show(placeholder(content, state.mode === "event"));
    return;
  }
  var video = document.createElement("video");
  activeVideo = video;
  video.src = content.src;
  video.muted = content.muted;
  video.loop = state.mode === "base";
  video.preload = "auto";
  video.setAttribute("playsinline", "");
  video.setAttribute("aria-label", content.title);
  video.addEventListener("playing", function () {
    video.started = true;
    video.pausedChecks = 0;
  });
  video.addEventListener("ended", function () {
    if (version !== renderVersion) return;
    if (state.mode === "event") {
      finish(state.event_id);
    } else {
      // Por si el reproductor ignora el atributo loop.
      video.currentTime = 0;
      start(video);
    }
  });
  video.addEventListener("error", function () {
    if (version !== renderVersion) return;
    console.error("No se puede reproducir", content.src);
    if (state.mode === "event") {
      finish(state.event_id);
    } else if (fallback && fallback.src && fallback.src !== content.src) {
      render(fallback, state);
    } else {
      render({title: content.title, src: null}, state);
      retryLater();
    }
  });
  video.addEventListener("loadedmetadata", function () {
    if (version !== renderVersion) return;
    if (state.mode === "event" && isFinite(video.duration)) {
      if (state.elapsed_seconds >= video.duration) {
        finish(state.event_id);
        return;
      }
      if (state.elapsed_seconds > 0.5) video.currentTime = state.elapsed_seconds;
    }
    start(video);
  });
  if (state.mode === "event") {
    // Un vídeo que no arranca ni da error no puede dejar la pantalla en negro hasta max_event_seconds.
    setTimeout(function () {
      if (version === renderVersion && !video.started) finish(state.event_id);
    }, 12000);
  }
  show(video);
}

// Si la base no se pudo leer (red cortada, servidor reiniciándose), se vuelve a pedir.
function retryLater() {
  var version = renderVersion;
  setTimeout(function () {
    if (version === renderVersion) token = null;
  }, 15000);
}

// Modo kiosco, sin botones. Los Chromium antiguos no devuelven promesa desde play().
function start(video) {
  var started;
  try {
    started = video.play();
  } catch (error) {
    mute(video);
    return;
  }
  if (started && typeof started.then === "function") {
    started.then(null, function () { mute(video); });
  }
}

// Si el navegador bloquea el sonido, se reproduce sin sonido.
function mute(video) {
  if (video !== activeVideo || video.muted) return;
  console.warn("El navegador bloquea el sonido; se reproduce sin sonido", video.src);
  video.muted = true;
  start(video);
}

// Nada debe quedarse en pausa (p. ej., tras un cambio de salida de audio): se reanuda.
function keepPlaying() {
  var video = activeVideo;
  if (!video || !video.paused || video.ended || !(video.readyState >= 2)) return;
  // Sin promesa, el sonido bloqueado solo se nota porque el vídeo no arranca.
  video.pausedChecks = (video.pausedChecks || 0) + 1;
  if (video.pausedChecks > 2 && !video.muted) mute(video);
  else start(video);
}

// done(error)
function sendCompletion(done) {
  if (!pendingCompletion) {
    done(null);
    return;
  }
  var id = pendingCompletion;
  request("POST", "/api/complete/" + channel, {event_id: id}, function (error) {
    if (!error && pendingCompletion === id) pendingCompletion = null;
    done(error);
  });
}

function finish(id) {
  if (!latest || latest.event_id !== id || finishedEvent === id) return;
  clearTimeout(expiryTimer);
  finishedEvent = id;
  pendingCompletion = id;
  // Vuelve a la base incluso si se pierde la conexión al finalizar el vídeo.
  render(latest.base, {mode: "base"}, latest.fallback_base);
  sendCompletion(function (error) {
    if (error) connection.hidden = false;
  });
}

// Indicadores NFC de /overlay sobre el vídeo, según nfc.overlay_channels.
function syncOverlay(enabled) {
  if (Boolean(enabled) === Boolean(overlay)) return;
  if (overlay) {
    overlay.parentNode.removeChild(overlay);
    overlay = null;
    return;
  }
  overlay = document.createElement("iframe");
  overlay.className = "overlay-frame";
  overlay.src = "/overlay";
  overlay.title = "Indicadores NFC";
  overlay.tabIndex = -1;
  stage.parentNode.insertBefore(overlay, stage.nextSibling);
}

function applySnapshot(state) {
  latest = state;
  syncOverlay(state.overlay);
  var nextToken = state.session + ":" + state.revision;
  if (nextToken === token) return;
  token = nextToken;
  clearTimeout(expiryTimer);
  if (state.event_id && state.event_id === finishedEvent) return;
  render(state.content, state, state.fallback_base);
  if (state.mode === "event") {
    expiryTimer = setTimeout(function () { finish(state.event_id); }, state.remaining_ms);
  }
}

function poll() {
  function done(error) {
    setTimeout(poll, 250);
    connection.hidden = !error;
    keepPlaying();
  }
  sendCompletion(function (error) {
    if (error) {
      done(error);
      return;
    }
    request("GET", "/api/state/" + channel + "?t=" + new Date().getTime(), null, function (error, state) {
      if (!error) {
        try {
          applySnapshot(state);
        } catch (problem) {
          error = problem;
        }
      }
      done(error);
    });
  });
}

show(placeholder({title: "Todo empieza con una historia"}, false));
poll();
