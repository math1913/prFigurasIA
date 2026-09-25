"use strict";

const names = {figuras: "Pantalla · Figuras", barcode: "Lector · Códigos de barras", nfc: "Lector · NFC", weather: "Clima", audio: "Sonido · PC"};
let built = false;

function buildButtons(groups) {
  const container = document.querySelector("#event-groups");
  for (const [channel, events] of Object.entries(groups)) {
    const title = document.createElement("h3");
    title.textContent = names[channel];
    const buttons = document.createElement("div");
    buttons.className = "event-buttons";
    for (const [key, label] of Object.entries(events)) {
      const button = document.createElement("button");
      button.textContent = label;
      button.addEventListener("click", async () => {
        const feedback = document.querySelector("#feedback");
        try {
          const response = await fetch(`/api/demo/${channel}`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({key}), signal: AbortSignal.timeout(2000),
          });
          if (!response.ok) throw new Error();
          feedback.textContent = `${names[channel]}: ${label}`;
        } catch {
          feedback.textContent = "No se pudo enviar la acción. Comprueba la conexión.";
        }
      });
      buttons.append(button);
    }
    container.append(title, buttons);
  }
}

async function updateStatus() {
  try {
    const response = await fetch("/api/status", {cache: "no-store", signal: AbortSignal.timeout(2000)});
    if (!response.ok) throw new Error();
    const data = await response.json();
    document.querySelector("#mode").textContent = data.demo ? "Modo demostración" : "Sistema local";
    document.querySelector("#demo").hidden = !data.demo;
    const status = document.querySelector("#status");
    status.replaceChildren();
    for (const [key, value] of Object.entries(data.hardware)) {
      const item = document.createElement("div");
      item.className = "status-item";
      item.dataset.status = value.status;
      const title = document.createElement("strong");
      title.textContent = names[key];
      const detail = document.createElement("span");
      detail.textContent = value.detail + (key === "weather" && data.weather_code ? ` · ${data.weather_code}` : "");
      item.append(title, detail);
      status.append(item);
    }
    if (data.demo && !built) {
      const barcodeResponse = await fetch("/api/barcodes", {cache: "no-store", signal: AbortSignal.timeout(2000)});
      if (!barcodeResponse.ok) throw new Error();
      const mapping = await barcodeResponse.json();
      const barcode = Object.fromEntries(Object.entries(mapping).map(([code, label]) => [code, `${label} · ${code}`]));
      const cameraEvents = Object.fromEntries(Object.entries(data.events.figuras).filter(([key]) => !Object.values(mapping).includes(key)));
      buildButtons({figuras: cameraEvents, barcode, nfc: data.events.nfc, weather: data.weather_videos});
      built = true;
    }
  } catch {
    document.querySelector("#mode").textContent = "Sin conexión · Reintentando";
  } finally {
    setTimeout(updateStatus, 2000);
  }
}
updateStatus();
