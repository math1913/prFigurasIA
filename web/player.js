/*
 * Reproductor de las pantallas /figuras y /nfc, en modo kiosco, y del sonido de /audio/<canal>.
 *
 * Escrito en ES5 y sin APIs recientes (fetch, AbortSignal, replaceChildren,
 * promesas obligatorias...), como los contenidos de cartelería de controlStore:
 * el reproductor de Admira corre en Android con un Chromium antiguo, y una sola
 * sintaxis que no entienda impide que el script arranque y deja la pantalla en negro.
 *
 * Con audio_on_pc, la pantalla va en silencio y /audio/<canal> pone el sonido en el PC.
 * Los dos siguen el reloj del servidor (elapsed_seconds) para ir a la par.
 */
"use strict";

// La página de audio no lleva data-channel: el canal sale de su ruta, /audio/<canal>.
var role = document.body.dataset.role === "audio" ? "audio" : "screen";
var channel = document.body.dataset.channel || location.pathname.split("/").pop();
var stage = document.querySelector("#stage");
var connection = document.querySelector("#connection");
// Versión de la web con la que se sirvió esta página; si el servidor tiene otra, se recarga.
var pageVersion = document.body.dataset.version;
var announced = false;
var token = null;
var latest = null;
var clock = null;
var shown = null;
var expiryTimer = null;
var pendingCompletion = null;
var finishedEvent = null;
var activeVideo = null;
var renderVersion = 0;
var overlay = null;
// Fundido entre vídeos. Cada relevo lleva su número: así un temporizador del anterior no
// descubre el vídeo que ya no toca. Con fade_ms a 0 nada de esto llega a ocurrir.
var veil = null;
var transition = 0;
var fadeHalf = 0;
var revealed = true;
var volumeTimer = null;
var earlyTimer = null;

function now() {
  return typeof performance !== "undefined" && performance.now ? performance.now() : new Date().getTime();
}

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

function paired() {
  return !!(latest && latest.audio_on_pc);
}

// Con audio_on_pc, la pantalla va en silencio y el sonido lo pone /audio/<canal> en el PC.
function silent(content) {
  return content.muted || (role === "audio" ? !paired() : paired());
}

// Si el reloj del servidor corresponde a lo que suena: el mismo modo, vídeo y evento.
function matches(video) {
  return !!clock && clock.mode === video.contentMode && clock.src === video.contentSrc && clock.id === video.eventId;
}

// Dónde debería ir según el servidor, con el retraso del sonido en la página de audio.
function target(video) {
  var seconds = clock.elapsed + (now() - clock.at) / 1000;
  if (role === "audio") seconds -= (latest.audio_delay_ms || 0) / 1000;
  if (video.loop && video.duration > 0) return ((seconds % video.duration) + video.duration) % video.duration;
  return Math.max(0, seconds);
}

// Dónde empieza: donde va el servidor si pantalla y audio van a la par; si no, donde iba el
// evento (una recarga lo retoma) y la base desde el principio.
function startAt(video, state) {
  if (paired() && matches(video)) return target(video);
  return state.mode === "event" && state.elapsed_seconds > 0.5 ? state.elapsed_seconds : 0;
}

// Lo que dura el paso por negro entero, según la pantalla.
function configuredFade() {
  return latest && latest.fade_ms > 0 ? latest.fade_ms : 0;
}

// El primer vídeo tras cargar la página no se hace esperar: no hay nada que fundir todavía.
function fadeLength() {
  return shown ? configuredFade() : 0;
}

// Velo negro entre el vídeo y los logos de /overlay. Se crea la primera vez que hace falta,
// así una pantalla sin fundido no lo tiene ni en la página.
function veilTo(opacity, ms) {
  if (!veil) {
    veil = document.createElement("div");
    veil.className = "veil";
    veil.setAttribute("aria-hidden", "true");
    stage.parentNode.insertBefore(veil, stage.nextSibling);
  }
  veil.style.transitionDuration = ms + "ms";
  // Leer una medida aplica el estado de partida antes de cambiarlo: sin esta lectura, un velo
  // recién creado saltaría al valor nuevo de golpe, sin fundirse. El valor no se usa.
  veil.measured = veil.offsetWidth;
  veil.style.opacity = String(opacity);
}

// El volumen no se puede animar desde la hoja de estilos: se baja y se sube a pasos.
function rampVolume(element, to, ms, step) {
  clearTimeout(volumeTimer);
  var steps = Math.max(1, Math.round(ms / 40));
  var from = typeof element.volume === "number" ? element.volume : 1;
  var done = 0;
  function tick() {
    // Un relevo nuevo, o un vídeo que ya no es el que suena, deja la rampa a medias.
    if (step !== transition || element !== activeVideo) return;
    done += 1;
    element.volume = Math.max(0, Math.min(1, from + (to - from) * done / steps));
    if (done < steps) volumeTimer = setTimeout(tick, 40);
  }
  volumeTimer = setTimeout(tick, 40);
}

// Un paso del fundido: a negro y sin sonido, o de vuelta. La pantalla cierra el velo y la
// página de audio solo tiene volumen, pero los dos tardan lo mismo para ir a la par.
function fadeTo(dark, ms, step) {
  if (role === "screen") veilTo(dark ? 1 : 0, ms);
  if (activeVideo) rampVolume(activeVideo, dark ? 0 : 1, ms, step);
}

// Descubre el vídeo nuevo cuando ya se mueve, o al agotarse el tope: uno que no arranque
// nunca no puede dejar la pantalla en negro.
function reveal(step) {
  if (step !== transition || revealed) return;
  revealed = true;
  fadeTo(false, fadeHalf, step);
}

// Cambia lo que se ve. Con fade_ms, el vídeo que sale se funde y el que entra aparece cuando
// ya se mueve; con 0, el cambio es inmediato, igual que sin fundido.
function present(content, state, fallback) {
  var ms = fadeLength();
  // Se anota ya lo que va a verse: durante el fundido siguen llegando instantáneas, y la base
  // que se acaba de pedir no debe volver a pedirse a mitad del relevo.
  shown = {mode: state.mode, src: content.src || null, session: latest ? latest.session : null};
  if (!ms) {
    render(content, state, fallback);
    return;
  }
  var step = ++transition;
  fadeHalf = ms / 2;
  revealed = false;
  fadeTo(true, fadeHalf, step);
  setTimeout(function () {
    if (step !== transition) return;
    // El vídeo se cambia con el velo ya cerrado; lo que tarde en arrancar tampoco se ve.
    render(content, state, fallback);
    if (activeVideo) activeVideo.volume = 0;
    setTimeout(function () { reveal(step); }, 5000);
  }, fadeHalf + 50);
}

// El fundido de vuelta a la base empieza justo antes de que acabe la canción: esperar a ended
// dejaría el vídeo terminado y el paso por negro no fundiría nada.
function fadeBeforeEnd(video, version, id) {
  var ms = configuredFade();
  if (!ms || !isFinite(video.duration) || !(video.duration > 0)) return;
  var left = (video.duration - video.currentTime) * 1000 - ms / 2;
  if (left <= 0) return;
  earlyTimer = setTimeout(function () {
    if (version === renderVersion) finish(id);
  }, left);
}

function render(content, state, fallback) {
  var version = ++renderVersion;
  clearTimeout(earlyTimer);
  if (activeVideo) {
    activeVideo.pause();
    activeVideo.removeAttribute("src");
    activeVideo.load();
    activeVideo = null;
  }
  shown = {mode: state.mode, src: content.src || null, session: latest ? latest.session : null};
  if (!content.src) {
    show(placeholder(content, state.mode === "event"));
    reveal(transition);  // No hay ningún vídeo cuyo arranque esperar.
    return;
  }
  var video = document.createElement(role === "audio" ? "audio" : "video");
  activeVideo = video;
  video.src = content.src;
  video.muted = silent(content);
  video.loop = state.mode === "base";
  video.preload = "auto";
  // cover llena la pantalla recortando lo que sobra; contain deja bandas; fill estira.
  video.className = "fit-" + (content.fit || (latest && latest.fit) || "cover");
  video.contentMode = state.mode;
  video.contentSrc = content.src;
  video.eventId = state.event_id || null;
  video.setAttribute("playsinline", "");
  video.setAttribute("aria-label", content.title);
  video.addEventListener("playing", function () {
    video.started = true;
    video.pausedChecks = 0;
    if (version === renderVersion) reveal(transition);
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
    var position = startAt(video, state);
    if (state.mode === "event" && isFinite(video.duration) && position >= video.duration) {
      finish(state.event_id);
      return;
    }
    if (position > 0.25) video.currentTime = position;
    start(video);
    if (state.mode === "event") fadeBeforeEnd(video, version, state.event_id);
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

// Pantalla y audio del PC se corrigen hacia el reloj del servidor: un poco más rápido o más
// lento si se separan poco, y un salto solo si se separan mucho o no se recuperan en 5 s.
function sync() {
  var video = activeVideo;
  if (!paired() || !video || video.paused || !(video.duration > 0) || !matches(video)) return;
  var at = now();
  if (video.holdUntil && at < video.holdUntil) return;
  var drift = video.currentTime - target(video);
  if (video.loop) drift -= Math.round(drift / video.duration) * video.duration;
  var off = Math.abs(drift) > 0.25;
  if (!off) video.driftSince = null;
  else if (!video.driftSince) video.driftSince = at;
  if (Math.abs(drift) > 1.5 || (off && at - video.driftSince > 5000)) {
    video.currentTime = target(video);
    video.playbackRate = 1;
    video.holdUntil = at + 1500;
    video.driftSince = null;
    return;
  }
  video.playbackRate = Math.abs(drift) < 0.04 ? 1 : 1 - Math.max(-0.1, Math.min(0.1, drift * 0.5));
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
  present(latest.base, {mode: "base"}, latest.fallback_base);
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
  overlay.src = "/overlay?v=" + (pageVersion || "") +
    (typeof location !== "undefined" && (location.search || "").indexOf("logos=todos") !== -1 ? "&logos=todos" : "");
  overlay.title = "Indicadores NFC";
  overlay.tabIndex = -1;
  stage.parentNode.insertBefore(overlay, stage.nextSibling);
}

// Tras actualizar el servidor, la pantalla se recarga sola para usar los archivos nuevos. Como
// mucho una vez cada 5 minutos: si un reproductor insistiera en su copia vieja, no entra en bucle.
function reloadForUpdate() {
  var at = new Date().getTime();
  var last = 0;
  try {
    last = Number(localStorage.getItem("bigbang-recarga")) || 0;
    if (at - last < 300000) return;
    localStorage.setItem("bigbang-recarga", String(at));
  } catch (error) {
    return;  // Sin almacenamiento no hay forma de evitar el bucle: se sigue con esta versión.
  }
  location.reload();
}

// Avisa al cargador de Admira (admira/cargador), si la pantalla va dentro de él, de que ya arrancó.
function announce() {
  if (announced) return;
  announced = true;
  if (typeof window !== "undefined" && window.parent && window.parent !== window) {
    window.parent.postMessage("bigbang-lista", "*");
  }
}

function applySnapshot(state) {
  if (state.version && pageVersion && state.version !== pageVersion) reloadForUpdate();
  latest = state;
  clock = {elapsed: state.elapsed_seconds || 0, at: now(), mode: state.mode,
           src: state.content.src || null, id: state.event_id || null};
  if (role === "screen") syncOverlay(state.overlay);
  var nextToken = state.session + ":" + state.revision;
  if (nextToken === token) return;
  token = nextToken;
  clearTimeout(expiryTimer);
  if (state.event_id && state.event_id === finishedEvent) return;
  // La base que ya suena al terminar un vídeo no vuelve a empezar cuando el servidor lo confirma.
  if (state.mode === "base" && shown && shown.mode === "base" && shown.session === state.session
      && shown.src === (state.content.src || null)) return;
  present(state.content, state, state.fallback_base);
  if (state.mode === "event") {
    expiryTimer = setTimeout(function () { finish(state.event_id); }, state.remaining_ms);
  }
}

function poll() {
  function done(error) {
    setTimeout(poll, 250);
    connection.hidden = !error;
    keepPlaying();
    sync();
  }
  sendCompletion(function (error) {
    if (error) {
      done(error);
      return;
    }
    var path = "/api/state/" + channel + "?t=" + new Date().getTime() + (role === "audio" ? "&audio=1" : "");
    request("GET", path, null, function (error, state) {
      if (!error) {
        try {
          applySnapshot(state);
          announce();
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
