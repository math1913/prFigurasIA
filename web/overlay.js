/*
 * Logo fijo mientras un lector detecta el libro; oculto si no se detecta o no hay datos del lector.
 * ES5 y XMLHttpRequest, como player.js, para el Chromium antiguo del reproductor de cartelería.
 */
"use strict";

var indicators = document.querySelectorAll(".indicator");

function show(present) {
  for (var index = 0; index < indicators.length; index += 1) {
    var indicator = indicators[index];
    if (present[indicator.id] === true) indicator.classList.add("present");
    else indicator.classList.remove("present");
  }
}

function poll() {
  var xhr = new XMLHttpRequest();
  var settled = false;
  function done(present) {
    if (settled) return;
    settled = true;
    setTimeout(poll, 500);
    show(present);
  }
  xhr.open("GET", "/objetos?t=" + new Date().getTime(), true);
  xhr.timeout = 2000;
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) return;
    var present = null;
    if (xhr.status === 200) {
      try {
        present = JSON.parse(xhr.responseText);
      } catch (error) {
        present = null;
      }
    }
    done(present || {});
  };
  xhr.onerror = xhr.ontimeout = function () { done({}); };
  xhr.send(null);
}

poll();
