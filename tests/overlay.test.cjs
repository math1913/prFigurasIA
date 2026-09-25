// Pruebas de los indicadores NFC superpuestos sin navegador ni lectores.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

const flush = () => new Promise(resolve => setImmediate(resolve));
const ok = body => ({status: 200, body});

function harness(initial) {
  const env = {response: initial, timers: [], urls: []};
  const indicators = ["Superman", "Prince", "Jackson", "Beatles"].map(id => {
    const classes = new Set();
    return {id, classes, classList: {add: name => classes.add(name), remove: name => classes.delete(name)}};
  });
  class FakeXHR {
    open(method, url) { env.urls.push(url); }
    send() {
      queueMicrotask(() => {
        this.readyState = 4;
        if (env.response instanceof Error) {
          this.status = 0;
          this.onreadystatechange();
          this.onerror();
          return;
        }
        this.status = env.response.status;
        this.responseText = JSON.stringify(env.response.body);
        this.onreadystatechange();
      });
    }
  }
  const context = vm.createContext({
    document: {querySelectorAll: selector => selector === ".indicator" ? indicators : []},
    XMLHttpRequest: FakeXHR,
    setTimeout: (fn, ms) => env.timers.push({fn, ms}),
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
  assert.match(env.urls[0], /^\/objetos\?t=\d+$/);
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
  assert.equal(env.timers.length, 1);
});
