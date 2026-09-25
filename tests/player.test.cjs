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

function harness(initial) {
  const env = {state: initial, offline: false, blocked: false, completions: [], timers: new Map(), siblings: []};
  let timerId = 0;
  class Element {
    constructor(tag) {
      this.tag = tag; this.children = []; this.listeners = {}; this.hidden = true;
      this.duration = 12; this.currentTime = 0; this.dataset = {}; this.attributes = {};
    }
    setAttribute(key, value) { this.attributes[key] = value; }
    removeAttribute(key) { delete this.attributes[key]; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    after(...nodes) { env.siblings.push(...nodes); }
    remove() { this.removed = true; }
    addEventListener(name, handler) { (this.listeners[name] ??= []).push(handler); }
    emit(name) { for (const handler of this.listeners[name] ?? []) handler(); }
    pause() { this.paused = true; }
    load() {}
    play() {
      // Como los navegadores: sin interacción se bloquea el sonido, no la reproducción silenciada.
      this.plays = (this.plays ?? 0) + 1;
      if (env.blocked && !this.muted) return Promise.reject(new Error("NotAllowed"));
      this.paused = false;
      return Promise.resolve();
    }
  }
  const elements = Object.fromEntries(["stage", "connection"].map(name => [name, new Element(name)]));
  const context = vm.createContext({
    document: {
      body: {dataset: {channel: "figuras"}},
      querySelector: selector => elements[selector.slice(1)],
      createElement: tag => new Element(tag),
    },
    console: {error() {}, warn() {}}, AbortSignal,
    setTimeout: (fn, ms) => { const id = ++timerId; env.timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => env.timers.delete(id),
    fetch: async (url, options) => {
      if (env.offline) throw new Error("Offline");
      if (url.includes("/complete/")) {
        env.completions.push(JSON.parse(options.body).event_id);
        return {ok: true, json: async () => ({accepted: true})};
      }
      return {ok: true, json: async () => structuredClone(env.state)};
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/player.js"), "utf8"), context);
  env.poll = () => vm.runInContext("poll()", context);
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

test("el tiempo de protección devuelve la base sin respuesta del servidor", async () => {
  const env = harness(snapshot({revision: 1, mode: "event", event_id: "stalled", remaining_ms: 1000})); await flush();
  env.offline = true;
  [...env.timers.values()].find(timer => timer.ms === 1000).fn(); await flush();
  assert.equal(env.video().loop, true);
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

test("un reinicio del servidor actualiza la pantalla aunque coincida la revisión", async () => {
  const env = harness(snapshot()); await flush();
  env.state = snapshot({session: "restarted", content: {...base, src: "/media/new-base.mp4"}});
  await env.poll();
  assert.equal(env.video().src, "/media/new-base.mp4");
});
