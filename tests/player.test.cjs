// Pruebas de eventos del reproductor sin navegador ni dispositivos físicos.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

const flush = () => new Promise(resolve => setImmediate(resolve));
const base = {title: "Base", src: "/media/base.mp4", muted: true};
const snapshot = (overrides = {}) => ({
  channel: "figuras", session: "test", revision: 0, mode: "base", event_id: null,
  content: base, base, fallback_base: base, remaining_ms: 60000, elapsed_seconds: 0,
  ...overrides,
});

function harness(initial, {role, channel = "figuras", pathname} = {}) {
  const env = {state: initial, offline: false, blocked: false, legacy: false, completions: [], timers: new Map(),
               siblings: [], urls: [], now: 0};
  let timerId = 0;
  class Element {
    constructor(tag) {
      this.tag = tag; this.children = []; this.listeners = {}; this.hidden = true; this.paused = true;
      this.duration = 12; this.currentTime = 0; this.playbackRate = 1; this.dataset = {}; this.attributes = {};
    }
    get firstChild() { return this.children[0] ?? null; }
    setAttribute(key, value) { this.attributes[key] = value; }
    removeAttribute(key) { delete this.attributes[key]; }
    appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index >= 0) this.children.splice(index, 1);
      child.removed = true;
      return child;
    }
    insertBefore(child) { env.siblings.push(child); child.parentNode = this; return child; }
    addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
    emit(name) { for (const handler of this.listeners[name] ?? []) handler(); }
    pause() { this.paused = true; }
    load() {}
    play() {
      // Como los navegadores: sin interacción se bloquea el sonido, no la reproducción silenciada.
      // Un Chromium antiguo (legacy) no devuelve promesa: el bloqueo solo se nota porque no arranca.
      this.plays = (this.plays ?? 0) + 1;
      const allowed = !env.blocked || this.muted;
      if (allowed) this.paused = false;
      if (env.legacy) return undefined;
      return allowed ? Promise.resolve() : Promise.reject(new Error("NotAllowed"));
    }
  }
  class FakeXHR {
    open(method, url) { this.url = url; env.urls.push(url); }
    setRequestHeader() {}
    send(body) {
      queueMicrotask(() => {
        this.readyState = 4;
        if (env.offline) {
          this.status = 0;
          this.onreadystatechange();
          this.onerror();
          return;
        }
        if (this.url.includes("/complete/")) env.completions.push(JSON.parse(body).event_id);
        this.status = 200;
        this.responseText = JSON.stringify(this.url.includes("/complete/") ? {accepted: true} : env.state);
        this.onreadystatechange();
      });
    }
  }
  const elements = Object.fromEntries(["stage", "connection"].map(name => [name, new Element(name)]));
  elements.stage.parentNode = new Element("body");
  const context = vm.createContext({
    document: {
      body: {dataset: {channel: pathname ? undefined : channel, role}},
      querySelector: selector => elements[selector.slice(1)],
      createElement: tag => new Element(tag),
    },
    location: {pathname: pathname ?? "/" + channel},
    performance: {now: () => env.now},
    console: {error() {}, warn() {}}, XMLHttpRequest: FakeXHR,
    setTimeout: (fn, ms) => { const id = ++timerId; env.timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => env.timers.delete(id),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/player.js"), "utf8"), context);
  env.poll = async () => { vm.runInContext("poll()", context); await flush(); };
  env.timer = ms => [...env.timers.values()].find(timer => timer.ms === ms);
  env.elements = elements;
  env.video = () => elements.stage.children[0];
  return env;
}

test("la base se reproduce en bucle y el evento termina con ended", async () => {
  const env = harness(snapshot()); await flush();
  assert.equal(env.video().loop, true);
  env.state = snapshot({revision: 1, mode: "event", event_id: "one", content: {...base, src: "/media/one.mp4"}});
  await env.poll();
  assert.equal(env.video().loop, false);
  assert.equal(env.video().src, "/media/one.mp4");
  env.video().emit("ended"); await flush();
  assert.equal(env.video().src, "/media/base.mp4");
  assert.deepEqual(env.completions, ["one"]);
});

test("un nuevo evento interrumpe y los callbacks del anterior se ignoran", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "one"})); await flush();
  const old = env.video();
  env.state = snapshot({revision: 2, mode: "event", event_id: "two", content: {...base, src: "/media/two.mp4"}});
  await env.poll();
  assert.equal(old.paused, true);
  old.emit("ended"); old.emit("error"); await flush();
  assert.equal(env.video().src, "/media/two.mp4");
  assert.deepEqual(env.completions, []);
  env.video().emit("ended"); await flush();
  assert.deepEqual(env.completions, ["two"]);
});

test("el clima actualizado durante el evento se usa al terminar", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "one"})); await flush();
  const playing = env.video();
  env.state.base = {...base, src: "/media/weather/rain.mp4"};
  await env.poll();
  assert.equal(env.video(), playing);
  playing.emit("ended"); await flush();
  assert.equal(env.video().src, "/media/weather/rain.mp4");
});

test("vídeo ausente o dañado vuelve a la base", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "broken"})); await flush();
  env.video().emit("error"); await flush();
  assert.equal(env.video().loop, true);
  assert.deepEqual(env.completions, ["broken"]);
});

test("si el vídeo de clima falla se reproduce la base genérica", async () => {
  const env = harness(snapshot({content: {...base, src: "/media/weather/broken.mp4"}})); await flush();
  env.video().emit("error");
  assert.equal(env.video().src, "/media/base.mp4");
  env.video().emit("error");
  assert.equal(env.elements.stage.children[0].tag, "section");
});

test("termina sin conexión y reintenta confirmar al reconectar", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "offline"})); await flush();
  env.offline = true;
  env.video().emit("ended"); await flush();
  assert.equal(env.video().loop, true);
  assert.equal(env.elements.connection.hidden, false);
  env.offline = false;
  await env.poll();
  assert.deepEqual(env.completions, ["offline"]);
  assert.equal(env.video().loop, true);
});

test("una recarga retoma el vídeo por el tiempo transcurrido", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "resume", elapsed_seconds: 7})); await flush();
  env.video().emit("loadedmetadata");
  assert.equal(env.video().currentTime, 7);
  const late = harness(snapshot({revision: 1, mode: "event", event_id: "late", elapsed_seconds: 30})); await flush();
  late.video().emit("loadedmetadata"); await flush();
  assert.deepEqual(late.completions, ["late"]);
});

test("si el navegador bloquea el sonido, sigue reproduciendo sin sonido", async () => {
  const env = harness(snapshot({content: {...base, muted: false}})); await flush();
  env.blocked = true;
  env.video().emit("loadedmetadata"); await flush();
  assert.equal(env.video().muted, true);
  assert.equal(env.video().paused, false);
});

test("un vídeo en pausa se reanuda solo, salvo si ya terminó", async () => {
  const env = harness(snapshot()); await flush();
  const video = env.video();
  video.emit("loadedmetadata"); await flush();
  assert.equal(video.plays, 1);
  Object.assign(video, {paused: true, readyState: 4});
  await env.poll();
  assert.equal(video.plays, 2);
  assert.equal(video.paused, false);
  Object.assign(video, {paused: true, ended: true});
  await env.poll();
  assert.equal(video.plays, 2);
});

test("en un Chromium antiguo, sin promesa en play(), acaba reproduciendo sin sonido", async () => {
  const env = harness(snapshot({content: {...base, muted: false}})); await flush();
  Object.assign(env, {legacy: true, blocked: true});
  const video = env.video();
  video.emit("loadedmetadata"); await flush();
  assert.equal(video.paused, true);
  video.readyState = 4;
  for (let check = 0; check < 3; check += 1) await env.poll();
  assert.equal(video.muted, true);
  assert.equal(video.paused, false);
});

test("el tiempo de protección devuelve la base sin respuesta del servidor", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "stalled", remaining_ms: 1000})); await flush();
  env.offline = true;
  env.timer(1000).fn(); await flush();
  assert.equal(env.video().loop, true);
});

test("un vídeo de acción que no arranca en 12 s vuelve a la base", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "mudo"})); await flush();
  env.timer(12000).fn(); await flush();
  assert.equal(env.video().loop, true);
  assert.deepEqual(env.completions, ["mudo"]);
  const playing = harness(snapshot({revision: 1, mode: "event", event_id: "sigue"})); await flush();
  playing.video().emit("playing");
  playing.timer(12000).fn(); await flush();
  assert.equal(playing.video().loop, false);
});

test("si la base no carga, se vuelve a pedir a los 15 s", async () => {
  const env = harness(snapshot()); await flush();
  env.video().emit("error");
  assert.equal(env.elements.stage.children[0].tag, "section");
  env.timer(15000).fn();
  await env.poll();
  assert.equal(env.video().src, "/media/base.mp4");
});

test("si el reproductor ignora loop, la base vuelve a empezar", async () => {
  const env = harness(snapshot()); await flush();
  const video = env.video();
  video.currentTime = 30;
  video.emit("ended");
  assert.equal(video.currentTime, 0);
  assert.equal(video.paused, false);
});

test("superpone los indicadores NFC solo si la pantalla lo tiene configurado", async () => {
  const env = harness(snapshot({overlay: true})); await flush();
  assert.equal(env.siblings.length, 1);
  const [frame] = env.siblings;
  assert.equal(frame.tag, "iframe");
  assert.equal(frame.src, "/overlay");
  await env.poll();
  assert.equal(env.siblings.length, 1);
  env.state = snapshot({session: "restarted", overlay: false});
  await env.poll();
  assert.equal(frame.removed, true);
  const plain = harness(snapshot()); await flush();
  assert.deepEqual(plain.siblings, []);
});

test("los vídeos llenan la pantalla salvo que su configuración diga otra cosa", async () => {
  const env = harness(snapshot()); await flush();
  assert.equal(env.video().className, "fit-cover");
  env.state = snapshot({revision: 1, fit: "contain", mode: "event", event_id: "one", content: {...base, fit: "fill"}});
  await env.poll();
  assert.equal(env.video().className, "fit-fill");
  env.state = snapshot({revision: 2, fit: "contain", mode: "event", event_id: "two", content: {...base, src: "/media/two.mp4"}});
  await env.poll();
  assert.equal(env.video().className, "fit-contain");
});

test("con audio_on_pc la pantalla va en silencio y la página de audio pone el sonido", async () => {
  const song = {title: "Canción", src: "/media/song.mp4", muted: false};
  const screen = harness(snapshot({audio_on_pc: true, content: song, base: song}), {channel: "nfc"}); await flush();
  assert.equal(screen.video().tag, "video");
  assert.equal(screen.video().muted, true);
  assert.match(screen.urls.at(-1), /^\/api\/state\/nfc\?t=\d+$/);
  const audio = harness(snapshot({audio_on_pc: true, content: song, base: song}), {role: "audio", pathname: "/audio/nfc"}); await flush();
  assert.equal(audio.video().tag, "audio");
  assert.equal(audio.video().muted, false);
  assert.match(audio.urls.at(-1), /^\/api\/state\/nfc\?t=\d+&audio=1$/);
  assert.deepEqual(audio.siblings, []);
  const alone = harness(snapshot({content: song, base: song}), {role: "audio", pathname: "/audio/nfc"}); await flush();
  assert.equal(alone.video().muted, true);
});

test("pantalla y audio siguen el reloj del servidor sin saltos salvo que se separen mucho", async () => {
  const song = {title: "Canción", src: "/media/song.mp4", muted: false};
  const env = harness(snapshot({audio_on_pc: true, revision: 1, mode: "event", event_id: "song", content: song, elapsed_seconds: 10}));
  await flush();
  const video = env.video();
  Object.assign(video, {paused: false, readyState: 4, duration: 60});
  const at = (now, elapsed, position) => {
    Object.assign(env, {now});
    env.state.elapsed_seconds = elapsed;
    video.currentTime = position;
    return env.poll();
  };
  await at(1000, 11, 10.8);
  assert.ok(Math.abs(video.playbackRate - 1.1) < 1e-9);  // Va 0,2 s por detrás: acelera un poco.
  await at(1250, 11.25, 11.27);
  assert.equal(video.playbackRate, 1);
  await at(1500, 11.5, 5);
  assert.equal(video.currentTime, 11.5);  // Muy separado: salta.
  await at(2000, 12, 12.3);
  assert.equal(video.currentTime, 12.3);  // Justo después de un salto se espera antes de corregir.
  await at(3500, 13.5, 13.8);
  assert.ok(video.playbackRate < 1);
  await at(9000, 19, 19.3);
  assert.equal(video.currentTime, 19);  // Lleva más de 5 s sin recuperarse: salta.
});

test("el audio del PC va con el retraso configurado y sigue la base en bucle", async () => {
  const loop = {title: "Base", src: "/media/base.mp4", muted: false};
  const env = harness(snapshot({audio_on_pc: true, audio_delay_ms: 200, content: loop, base: loop, elapsed_seconds: 25}),
                      {role: "audio", pathname: "/audio/nfc"});
  await flush();
  const video = env.video();
  video.duration = 12;
  video.emit("loadedmetadata");
  assert.ok(Math.abs(video.currentTime - 0.8) < 1e-9);  // 25 s - 0,2 s de retraso, dentro de un bucle de 12 s.
});

test("al terminar un vídeo, la base no vuelve a empezar cuando el servidor lo confirma", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "one", content: {...base, src: "/media/one.mp4"}}));
  await flush();
  env.video().emit("ended"); await flush();
  const playing = env.video();
  assert.equal(playing.src, "/media/base.mp4");
  env.state = snapshot({revision: 2});
  await env.poll();
  assert.equal(env.video(), playing);
});

test("player.js y overlay.js siguen en ES5 para el Chromium antiguo del reproductor", () => {
  const modern = [/=>/, /`/, /\?\./, /\?\?/, /\b(const|let|class|async|await)\s/, /\.\.\.[\w$[{(]/,
    /\b(fetch|AbortSignal|replaceChildren|queueMicrotask|structuredClone)\s*[.(]/, /\.(append|prepend|after|before|replaceWith)\(/];
  for (const file of ["player.js", "overlay.js"]) {
    const source = fs.readFileSync(path.join(__dirname, "../web", file), "utf8");
    for (const pattern of modern) assert.doesNotMatch(source, pattern, `${file} usa ${pattern}`);
  }
});

test("un reinicio del servidor actualiza la pantalla aunque coincida la revisión", async () => {
  const env = harness(snapshot()); await flush();
  env.state = snapshot({session: "restarted", content: {...base, src: "/media/new-base.mp4"}});
  await env.poll();
  assert.equal(env.video().src, "/media/new-base.mp4");
});
