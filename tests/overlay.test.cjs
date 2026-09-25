// Pruebas de los indicadores NFC superpuestos sin navegador ni lectores.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

const flush = () => new Promise(resolve => setImmediate(resolve));
const ok = body => ({status: 200, body});

function harness(initial) {
  const env = {response: initial, timers: []};
  const indicators = ["Superman", "Prince", "Jackson", "Beatles"].map(id => {
    const classes = new Set();
    return {id, classes, classList: {toggle: (name, force) => force ? classes.add(name) : classes.delete(name)}};
  });
  const context = vm.createContext({
    document: {querySelectorAll: selector => selector === ".indicator" ? indicators : []},
    AbortSignal,
    setTimeout: (fn, ms) => env.timers.push({fn, ms}),
    fetch: async url => {
      assert.equal(url, "/objetos");
      if (env.response instanceof Error) throw env.response;
      const {status, body} = env.response;
      return {ok: status === 200, json: async () => structuredClone(body)};
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/overlay.js"), "utf8"), context);
  env.poll = async () => { env.timers.shift().fn(); await flush(); };
  env.visible = () => indicators.filter(item => item.classes.has("present")).map(item => item.id);
  return env;
}

test("muestra fijo solo el logo de los libros detectados", async () => {
  const env = harness(ok({Beatles: false, Jackson: false, Prince: true, Superman: true})); await flush();
  assert.deepEqual(env.visible(), ["Superman", "Prince"]);
  assert.equal(env.timers[0].ms, 500);
  env.response = ok({Beatles: true, Jackson: false, Prince: false, Superman: true});
  await env.poll();
  assert.deepEqual(env.visible(), ["Superman", "Beatles"]);
});

test("oculta todos los logos sin lector disponible o sin conexión", async () => {
  const env = harness(ok({Beatles: true, Jackson: true, Prince: true, Superman: true})); await flush();
  assert.equal(env.visible().length, 4);
  env.response = {status: 503, body: {detail: "Lector NFC no disponible"}};
  await env.poll();
  assert.deepEqual(env.visible(), []);
  env.response = ok({Beatles: true, Jackson: false, Prince: false, Superman: false});
  await env.poll();
  assert.deepEqual(env.visible(), ["Beatles"]);
  env.response = new Error("Offline");
  await env.poll();
  assert.deepEqual(env.visible(), []);
});
