"use strict";

// Logo fijo mientras un lector detecta el libro; oculto si no se detecta o no hay datos del lector.
const indicators = document.querySelectorAll(".indicator");

function show(present) {
  for (const indicator of indicators) indicator.classList.toggle("present", present[indicator.id] === true);
}

async function poll() {
  try {
    const response = await fetch("/objetos", {cache: "no-store", signal: AbortSignal.timeout(2000)});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    show(await response.json());
  } catch {
    show({});
  } finally {
    setTimeout(poll, 500);
  }
}

poll();
