// Pruebas del cargador de Admira (admira/cargador): la tele se enciende antes que el PC.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

const flush = () => new Promise(resolve => setImmediate(resolve));
const script = fs.readFileSync(path.join(__dirname, "../admira/cargador/index.html"), "utf8")
  .match(/<script>([\s\S]*?)<\/script>/)[1];

function harness() {
  const env = {up: false, frames: [], timers: [], listeners: {}};
  class FakeImage {
    set src(url) { this.url = url; queueMicrotask(() => (env.up ? this.onload() : this.onerror())); }
  }
  const body = {
    appendChild: node => { env.frames.push(node); node.parentNode = body; },
    removeChild: node => { node.removed = true; },
  };
  const context = vm.createContext({
    Image: FakeImage,
    document: {body, createElement: tag => ({tag, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; }})},
    window: {addEventListener: (name, handler) => { env.listeners[name] = handler; }},
    setTimeout: (fn, ms) => env.timers.push({fn, ms}),
    clearTimeout() {},
  });
  vm.runInContext(script, context);
  env.run = async ms => {
    const [timer] = env.timers.splice(env.timers.findIndex(item => item.ms === ms), 1);
    timer.fn();
    await flush();
  };
  env.message = data => env.listeners.message({data});
  env.visible = () => env.frames.filter(frame => !frame.removed);
  return env;
}

test("espera al servidor y entonces carga la pantalla", async () => {
  const env = harness(); await flush();
  assert.equal(env.frames.length, 0);
  await env.run(2000);
  assert.equal(env.frames.length, 0);  // Sigue sin contestar: sigue esperando.
  env.up = true;
  await env.run(2000);
  const [frame] = env.visible();
  assert.match(frame.src, /^http:\/\/192\.168\.1\.13:8002\/nfc\?t=\d+$/);
  assert.equal(frame.attributes.allow, "autoplay; fullscreen");
  env.message("bigbang-lista");
  await env.run(20000);
  assert.equal(env.frames.length, 1);  // La pantalla avisó: no se toca.
});

test("si la pantalla no avisa, reintenta una sola vez y después la deja", async () => {
  const env = harness();
  env.up = true;
  await flush();
  await env.run(20000);
  assert.equal(env.frames.length, 2);
  await env.run(20000);
  assert.equal(env.frames.length, 2);
  assert.equal(env.visible().length, 1);
});

test("si el servidor cae mientras carga, espera a que vuelva y la carga otra vez", async () => {
  const env = harness();
  env.up = true;
  await flush();
  env.up = false;
  await env.run(20000);
  assert.equal(env.frames.length, 1);
  env.up = true;
  await env.run(2000);
  assert.equal(env.frames.length, 2);
  assert.equal(env.visible().length, 1);
});
