# BigBang · Figuras, NFC y pantallas HTML

Una aplicación Python ejecuta el detector YOLO, el escáner de códigos de barras, los lectores NFC y el clima en el mismo PC. Sirve dos pantallas HTML independientes, reproduce vídeos locales y ya no lee ni escribe `biomax.xml` o `temp.xml` ni necesita Admira. Cámara y códigos de barras comparten `/figuras`; NFC utiliza `/nfc`, con los indicadores de `/overlay` superpuestos.

La integración utiliza `prFigurasIA` como repositorio principal e incorpora los 40 UID de `NFC-ACR122/aliases.json`. El repositorio NFC original no necesita ejecutarse. Se conservan los modelos `.pt` y los scripts de entrenamiento.

También integra los 14 códigos de `BarcodeBigBang/barcode_id.json`, conservados en `barcode_id.json`. No ejecutes los antiguos lectores a la vez que esta aplicación: competirían por los mismos dispositivos.

## Arranque en Windows

En el PC del montaje, instala Python 3.13 de 64 bits y abre PowerShell dentro de la carpeta `prFigurasIA` actualizada. Copia esta versión del proyecto o clona la rama `integracion-figuras-nfc-html` una vez que sus cambios estén guardados y subidos a GitHub. No copies `.venv` de otro PC: créala allí.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Descarga `bigbang-media.zip` desde la [carpeta de media en Google Drive](https://drive.google.com/drive/folders/18BIm4Wl_v0IUXELOWheuGE0pJhidnlNj?usp=drive_link). Descarga el archivo ZIP preparado, no la carpeta completa comprimida por Drive. Instálalo sin descomprimir manualmente:

```powershell
.\descargar_media.bat --archive "$env:USERPROFILE\Downloads\bigbang-media.zip"
.\.venv\Scripts\python.exe scripts/media.py check
```

Ajusta la ruta si lo guardaste en otra carpeta. Si ya tienes la media completa en este PC, basta con ejecutar la comprobación.

Conecta cámara, escáner y lectores NFC. Para probar con la API de clima real, configura tu clave en esa misma ventana de PowerShell y arranca:

```powershell
$env:OPENWEATHER_API_KEY = "TU_CLAVE"
.\.venv\Scripts\python.exe main.py
```

Si todavía no tienes clave, omite la primera línea: la ventana utilizará `despejado.mp4`. La ciudad se configura en `weather.city` (Barcelona por defecto). La variable se establece para esa sesión de PowerShell; repítelo si abres otra.

Para probar primero sin dispositivos ni API, usa `main.py --demo`. Abre el panel, las dos pantallas y pulsa los botones de prueba; los botones del clima permiten alternar lluvia y despejado. Detén la demo con Ctrl+C antes de arrancar el modo real. En el montaje comprueba una figura, un código de barras y la retirada de un objeto NFC; verifica el retorno a sus bases y que otra acción interrumpe el vídeo del mismo canal.

El sonido sigue desactivado por defecto (`muted: true`). Para oír las canciones, añade `"muted": false` a los vídeos NFC que quieras escuchar en `config.json` y reinicia. El software de pantallas debe permitir la reproducción automática con sonido; si no, los vídeos se reproducen sin sonido (consulta «Modo kiosco»).

No hace falta activar el entorno virtual. El desarrollo y las pruebas web se han realizado con Python 3.13.

| URL | Uso |
| --- | --- |
| http://localhost:8002/ | Estado de los dispositivos y accesos a las pantallas |
| http://localhost:8002/figuras | Pantalla de figuras |
| http://localhost:8002/nfc | Pantalla de NFC |
| http://localhost:8002/overlay | Indicadores NFC con fondo transparente, superpuestos a una pantalla |
| http://localhost:8002/objetos | API de presencia NFC, conserva los nombres y el puerto original |
| http://localhost:8002/audio/nfc | Solo el sonido de NFC, para el PC (la aplicación la abre sola, ver «Sonido desde el PC») |

Muestra cada pantalla a pantalla completa en su monitor con el software de pantallas; para una prueba rápida en un navegador, usa F11. Las páginas necesitan el servidor en ejecución; no se abren directamente como archivos. Detén la aplicación con Ctrl+C.

`main.py` escucha en `127.0.0.1:8002`: solo responde a `localhost`, ni siquiera a la IP del propio PC. Puedes cambiar el puerto con `--port 8003`. Para acceder desde la red local, arranca con `--host 0.0.0.0`, como hace `iniciar_bigbang.bat`; no hay autenticación para ese modo. Usa una sola instancia: varias instancias competirían por la cámara y los lectores.

### Arranque automático

`main.py` ejecuta todo en un único proceso: servidor web, cámara, escáner, lectores NFC y clima. No hay que arrancar nada más. Desactiva las tareas o accesos directos antiguos de los repositorios originales, como `start_barcode.bat`.

`iniciar_bigbang.bat` arranca `main.py` con el entorno virtual y lo vuelve a arrancar a los 10 segundos si se cierra. Si ya hay una instancia en el puerto 8002, no abre otra. Deja constancia de cada arranque y cierre en `logs/arranque.log`; los mensajes de la aplicación aparecen en su ventana, «BigBang». Para detenerlo, cierra esa ventana. El registro de peticiones HTTP está desactivado para que las consultas de las pantallas no tapen esos mensajes.

Para la API del clima, crea un archivo `.env` junto a `main.py` con la línea `OPENWEATHER_API_KEY=TU_CLAVE`. El `.bat` lo lee y Git lo ignora.

El `.bat` escucha en toda la red local (`HOST=0.0.0.0`): el panel y las pantallas se abren desde otros equipos con `http://IP-DEL-PC:8002/`, por ejemplo http://192.168.1.13:8002/. Para que entren, el firewall de Windows debe permitir el puerto. Créale una regla una sola vez, en PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "BigBang 8002" -Direction Inbound -Protocol TCP -LocalPort 8002 -Action Allow -Profile Private,Domain
```

La regla solo se aplica si Windows considera la red privada. Si aparece como pública, cámbiala en Configuración > Red e Internet > Ethernet > Tipo de perfil de red. Si al arrancar Windows pregunta por Python, pulsa «Permitir acceso». Si alguien canceló ese aviso, Windows habrá creado reglas que bloquean `python.exe`; esas reglas tienen prioridad, así que bórralas en «Firewall de Windows Defender con seguridad avanzada» > «Reglas de entrada».

Para que arranque al encender el PC, crea una tarea en el Programador de tareas:

1. **Desencadenador:** «Al iniciar la sesión» del usuario del montaje, con el inicio de sesión automático de Windows activado. En la sesión del usuario, la cámara y los lectores funcionan con menos problemas que con «Al iniciar el sistema».
2. **Acción:** «Iniciar un programa», con la ruta completa de `iniciar_bigbang.bat`.
3. **General:** «Ejecutar solo cuando el usuario haya iniciado sesión». El sonido del PC también lo necesita: fuera de la sesión no hay altavoces.
4. **Configuración:** desmarca «Detener la tarea si se ejecuta durante más de 3 días», que viene marcada y la cerraría a los tres días. Mantén «No iniciar una instancia nueva».

El software de pantallas necesita que el servidor ya responda al abrir las URL. Si arranca antes que la tarea, añade unos segundos de retraso o activa su recarga automática.

## Demostración sin dispositivos

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe main.py --demo
```

En el panel principal aparecen botones para simular figuras, códigos de barras, objetos NFC y estados del clima. Abre las pantallas y pulsa esos botones. `--demo` desactiva la cámara, el puerto serie, PC/SC y las consultas reales a OpenWeather. Los botones y la API de simulación solo funcionan con este argumento.

## Añadir tus vídeos

Edita `config.json` y reinicia el servidor. Todas las rutas parten de la carpeta del proyecto, aunque lo arranques desde otro directorio. `--config ruta\config.json` permite usar otro archivo de configuración; los modelos, alias y medios siguen resolviéndose desde la carpeta del proyecto.

1. Copia los vídeos dentro de `media/`. Puedes crear subcarpetas `figuras/`, `nfc/` y `clima/`.
2. Sustituye los `src: null` de la configuración por sus rutas `/media/...`.
3. Configura el vídeo base de cada pantalla en `channels.figuras.base` y `channels.nfc.base`.
4. Asigna los vídeos de cada acción en `channels.figuras.events` y `channels.nfc.events`.
5. Asigna los vídeos meteorológicos en `weather.videos`.

Por ejemplo, este objeto configura el contenido de `channels.nfc.events.Prince`:

```json
{
  "title": "Prince",
  "src": "/media/nfc/prince.mp4",
  "muted": true
}
```

`media/nfc/prince.mp4` debe existir. Usa vídeos que tu navegador pueda reproducir; MP4 con H.264 es una opción habitual.

Los vídeos llenan la pantalla aunque su formato no coincida con ella: `fit` es `cover` por defecto y recorta lo que sobra, sin deformar. Se configura por pantalla, en `channels.figuras.fit` y `channels.nfc.fit`, y un vídeo concreto puede llevar el suyo con `"fit"`. `contain` muestra el vídeo entero con bandas negras y `fill` lo estira hasta llenar la pantalla. Si con `cover` queda una franja negra, está fuera de la página: es el margen que deja el propio reproductor o la tele.

`muted` es `true` por defecto para permitir reproducción automática. Con `false`, muchos navegadores solo reproducen con sonido tras una interacción del usuario. Como las pantallas no tienen botones, en ese caso el vídeo se reproduce igualmente, sin sonido, y la consola del navegador lo avisa. Para que suene, permite la reproducción automática con sonido en el software de pantallas; en Chrome o Edge, con el argumento `--autoplay-policy=no-user-gesture-required`.

Con `src: null` se muestra una pantalla provisional con el título. Una acción sin vídeo dura `placeholder_seconds` (5 segundos por defecto). Un vídeo configurado termina con su evento real `ended`; **no usa una duración fija de 20 segundos**. `max_event_seconds` (3600 por defecto) es un límite de recuperación para vídeos bloqueados o pantallas ausentes: ajústalo por encima de la duración del vídeo más largo.

Si un vídeo de acción no se puede cargar, se vuelve a la base. Si falla el vídeo base del clima, se intenta el base genérico de esa pantalla. Si este también falla, aparece la pantalla provisional. Los errores de archivo/reproducción se registran en la consola del navegador.

## Comportamiento

- El vídeo base se reproduce en bucle.
- Una nueva acción interrumpe inmediatamente el vídeo de acción anterior **del mismo canal**. La excepción es NFC: retirar otra vez el objeto cuya canción ya suena no la reinicia.
- Cuando termina el vídeo de acción, vuelve a comenzar el vídeo base que corresponda en ese momento.
- Los canales de figuras y NFC pueden reproducir acciones simultáneas sin interferirse.
- Cada acción tiene un identificador: un aviso de fin tardío del vídeo anterior no puede cerrar el vídeo nuevo.
- Las pantallas consultan el estado cada 250 ms y reintentan automáticamente si se corta la conexión. Al recargar una pantalla, retoma el evento vigente por su tiempo transcurrido. Si el vídeo termina durante una desconexión, vuelve a la base localmente y confirma el fin cuando recupera conexión.
- El estado está en memoria: al reiniciar la aplicación, comienza desde la base.
- **Modo kiosco**, para funcionar 24 horas: las pantallas no tienen botones ni cursor, el vídeo empieza solo y, si algo lo pausa (por ejemplo, un cambio de salida de audio), se reanuda. Un vídeo de acción que en 12 segundos ni arranca ni da error se abandona y vuelve la base; si la base no carga, se vuelve a pedir cada 15 segundos.

### Reproductor de cartelería (Admira)

Las pantallas se muestran en el reproductor de Admira, que en Android usa un Chromium antiguo. Por eso `player.js` y `overlay.js` están escritos en ES5: sin `const`/`let`, funciones flecha, `async`, `fetch` ni `?.`, y con `XMLHttpRequest`. El CSS de las pantallas evita `inset`, `dvh`, `aspect-ratio`, `gap` en flex, `color-mix` y los colores de 8 cifras. Son las mismas reglas que los contenidos de cartelería de controlStore. Una sola sintaxis nueva impide que el script arranque y deja la pantalla en negro, así que las pruebas JavaScript lo comprueban. El panel de control (`control.js`) no tiene esa restricción.

Cada vez que un dispositivo abre una pantalla, la consola anota su navegador, por ejemplo `Pantalla nfc abierta desde 192.168.1.50 · Mozilla/5.0 (Linux; Android …) Chrome/…`. Así se sabe qué versión de Chromium tiene el reproductor.

Los vídeos actuales son H.264 de 8 bits, lo que decodifica ese hardware. Si alguno va a tirones, los primeros candidatos a pasar a 30 fps son los de 50-60 fps: tres de NFC en 1080p y varios de figuras. Muchos tienen el índice (`moov`) al final del archivo; `ffmpeg -i entrada.mp4 -c copy -movflags +faststart salida.mp4` lo mueve al principio sin recodificar, y el vídeo arranca antes.

### Figuras

Se usa `yoloFiguritasv2.pt`, cámara `0` y confianza mínima `0.8`. Todo es configurable en `figures`. `labels` incluye los nombres de clases usados en los modelos v2 y v3, manteniendo los códigos anteriores:

| Código | Figura |
| --- | --- |
| A | Alfred |
| G | Batgirl |
| B | Bruce Wayne |
| C | Catwoman |
| Y | Cyborg |
| F | Flash |
| H | Harley Quinn |
| J | Joker |
| S | Superman / Jor-el |
| W | Wonder Woman |

La detección debe mantenerse `stable_seconds` (0.5 segundos) para activarse. Si hay varias figuras visibles, se toma la de mayor confianza. Por defecto, una misma figura no se reactiva continuamente: debe dejar de verse durante `absence_seconds` (1 segundo) y volver a mostrarse. Así el vídeo puede terminar y regresar a la base aunque la figura siga delante de la cámara.

Además, `figures.cooldown_seconds` establece **un mínimo de 60 segundos entre activaciones de la misma figura**. Se cuenta desde su última activación aceptada: las detecciones descartadas no reinician el contador. Se conserva aunque la figura desaparezca, cambie por otra o se reconecte la cámara. Una figura diferente puede activarse sin esperar el margen de la anterior. Este filtro solo afecta a la cámara.

`repeat_while_present: true` permite repetir al terminar si sigue presente, respetando también `cooldown_seconds`. Con el valor por defecto `false`, cumplir el minuto no provoca por sí solo una repetición: se conserva la necesidad de retirar y volver a mostrar la figura. `preview: true` abre la vista de detección de OpenCV; Q detiene únicamente el detector. `enabled: false` desactiva la cámara. Las desconexiones de cámara se reintentan sin detener NFC ni las pantallas. El contador se reinicia al cerrar y volver a abrir la aplicación.

### Códigos de barras

El escáner utiliza `pyserial` y un puerto COM, igual que `BarcodeBigBang`. Se configura en `barcode`: por defecto autodetecta VID `9969` y PID `34818`, a 9600 baudios, 8 bits, sin paridad y 1 bit de parada. Si hay varios escáneres iguales, asigna un puerto explícito, por ejemplo `"port": "COM7"`. Para listar los dispositivos:

```powershell
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
```

El mapa `barcode_id.json` se vuelve a leer con cada escaneo. Las claves son cadenas para conservar ceros iniciales y códigos alfanuméricos. Su valor identifica una entrada en `channels.figuras.events`. Por ejemplo, `787926301397` activa `Joker`, cuyo vídeo es `/media/figuras/jokerFigura.mp4`; la cámara activa `J` y reproduce `/media/figuras/joker.mp4`.

El último evento de cámara o escáner sustituye al anterior en la pantalla de figuras. Escanear de nuevo el mismo código también reinicia su vídeo. NFC no se interrumpe. El lector admite CR, LF, CRLF y códigos sin terminador cuando vence el tiempo de lectura. Si se desconecta, reintenta cada 2 segundos. `barcode.enabled: false` permite desactivarlo.

### NFC

Se activa **al retirar el objeto**, conservando el comportamiento original. `aliases.json` asigna UID a contenido. Los alias disponibles son Beatles, Jackson, Prince, Superman, Jeep y Batman. Como con las figuras, un contenido no se interrumpe a sí mismo: si la canción de un objeto ya suena, retirarlo otra vez no la devuelve al principio. Cuando termina, vuelve a activarse la próxima vez que se retire, lo que exige haberlo colocado antes en su lector. Otro objeto sí la interrumpe.

Las tarjetas sin alias o con lectura fallida no activan contenido. Los lectores se distinguen por su nombre; retirar una tarjeta no borra la presencia en otros lectores. `/objetos` mantiene los cuatro objetos monitorizados originalmente: Beatles, Jackson, Prince y Superman, configurables mediante `nfc.monitored_objects`. Responde 503 si el lector no está disponible.

El lector requiere PC/SC y `pyscard`. Si el sistema no reconoce el ACR122U, consulta los [controladores oficiales de ACS](https://www.acs.com.hk/en/products/3/acr122u-usb-nfc-reader/). La aplicación espera si no hay lectores y los detecta al conectarlos. `nfc.enabled: false` desactiva la integración.

Si aparece el error `0x8010001D`, Windows informa de que el servicio de tarjetas inteligentes no está ejecutándose. Comprueba el lector y el servicio «Tarjeta inteligente» en el PC del montaje. La aplicación reintenta y mantiene las pantallas disponibles.

#### Indicadores superpuestos

Integra el overlay de la rama `controlNFC` de NFC-ACR122 en una página aparte, `/overlay`, con fondo transparente. Muestra **fijo** el logo de cada libro mientras un lector lo detecta y lo oculta al retirarlo; ya no parpadea. Si el lector no está disponible o se pierde la conexión con el servidor, se ocultan todos los logos. Se actualiza cada 500 ms a partir de `/objetos`, sin procesos ni archivos generados adicionales.

`nfc.overlay_channels` decide sobre qué pantallas se superpone: `["nfc"]` por defecto, `["figuras"]`, ambas o `[]` para ninguna. La pantalla lo coloca encima del vídeo sin bloquear los botones y lo retira si se desactiva al reiniciar. Para usarlo en otro sistema de capas, abre directamente `/overlay`.

Los logos están en `web/img/` y el `id` de cada indicador de `web/overlay.html` coincide con su alias de `aliases.json`. En `--demo` no aparece ningún logo, porque no hay lectores que detecten libros.

#### Sonido desde el PC

Con `channels.nfc.audio_on_pc: true`, como ahora, la pantalla de NFC se reproduce siempre en silencio y el sonido sale por los altavoces del PC que ejecuta la aplicación. La tele no necesita altavoz.

La aplicación abre `/audio/nfc` en un Chrome sin ventana, o en Edge si no hay Chrome, con la reproducción automática con sonido permitida. Lo vuelve a abrir si se cierra o deja de responder, y lo cierra al terminar, aunque la aplicación se cierre de golpe. El panel muestra su estado en «Sonido · PC». `audio.browser` permite indicar la ruta del navegador y `audio.enabled: false` evita abrirlo, por ejemplo si prefieres abrir `/audio/nfc` en otro equipo.

Pantalla y sonido siguen el reloj del servidor y se corrigen solos con pequeños cambios de velocidad, sin saltos, así que imagen y canción van a la par. Si la tele tarda en mostrar la imagen y el sonido se adelanta, sube `channels.nfc.audio_delay_ms` (por ejemplo, a `100`); con un valor negativo, el sonido se adelanta. Con `audio_on_pc: false`, cada pantalla suena por sí misma, como antes.

### Clima

El antiguo `weatherReader.py` está integrado en `display_app/weather.py`. Se utiliza la [API de clima actual de OpenWeather](https://openweathermap.org/current) con la misma clasificación del proyecto original. La API key se lee de una variable de entorno y no se guarda en el código:

```powershell
$env:OPENWEATHER_API_KEY = "TU_CLAVE"
.\.venv\Scripts\python.exe main.py
```

Por defecto consulta Barcelona cada 300 segundos. Configura `weather.city`, `poll_seconds` y `sunset_seconds` (3600 segundos de atardecer). Sin clave, si falla la consulta o si caducan los datos (`stale_seconds`), se utiliza **`media/ventana/despejado.mp4` como respaldo**. Tras una consulta correcta se recupera el vídeo del clima actual. Las pantallas y sensores siguen funcionando; una acción en curso termina antes de volver a la base.

La ventana (`/figuras`) usa `media/ventana/lluvioso.mp4` para DL y NL; para DD, DN, A, ND y NN usa `media/ventana/despejado.mp4`. Al haber dos vídeos, nublado y atardecer también usan despejado. Se conserva la clasificación original: los códigos de OpenWeather menores de 800 se agrupan en DL/NL. La pantalla de canciones (`/nfc`) reproduce **`media/pantalla/bigBangIntro.mp4` en bucle** como base y no cambia con el clima.

| Código | Contenido |
| --- | --- |
| DL | Día con precipitación / código meteorológico menor que 800 |
| DD | Día despejado |
| DN | Día nublado |
| A | Atardecer despejado |
| NL | Noche con precipitación / código meteorológico menor que 800 |
| ND | Noche despejada |
| NN | Noche nublada |

Durante el atardecer se conserva DL o DN si no está despejado, como en el original. El clima selecciona el **vídeo base** y nunca interrumpe un vídeo de acción. Cuando este termina, vuelve a la base del clima actual. Si un código todavía tiene `src: null`, se usa la base genérica.

`weather.base_channels` decide dónde se aplica: `["figuras"]` por defecto, `["nfc"]` o `["figuras", "nfc"]`. `weather.enabled: false` desactiva las consultas. El clima no necesita otro proceso ni escribe XML.

## Distribuir los vídeos sin incluirlos en Git

`media/` está excluida de Git salvo su README. También se excluye `media-dist/`, donde se prepara el ZIP. Guarda en Git `config.json`, `media-manifest.json`, `media-source.json`, los scripts y los `.bat`. Los archivos `.pt` existentes siguen en el repositorio como antes.

La media se distribuye mediante esta [carpeta de Google Drive](https://drive.google.com/drive/folders/18BIm4Wl_v0IUXELOWheuGE0pJhidnlNj?usp=drive_link). Dentro debe estar el archivo **`bigbang-media.zip` generado por `preparar_media.bat`**. El enlace es de una carpeta, por lo que se abre en el navegador para descargar el ZIP; no se pasa como URL directa al descargador.

En el PC que tiene los vídeos:

1. Ejecuta `preparar_media.bat`. Crea `media-dist/bigbang-media.zip` y actualiza `media-manifest.json` con tamaños y SHA-256. Incluye los vídeos de `media/`, también los todavía no asignados a una acción.
2. Sube `media-dist/bigbang-media.zip` a la carpeta de Drive indicada. El script prepara el archivo local; la subida se hace desde Drive.
3. Guarda y sube a Git el `media-manifest.json` generado junto con los cambios del proyecto. El ZIP de Drive y el manifiesto del código deben pertenecer a la misma versión. Si cambias vídeos, regenera y actualiza ambos.

En otro PC, tras obtener esta versión del repositorio y tener Python instalado, descarga **el archivo `bigbang-media.zip`** desde Drive. No selecciones «Descargar» sobre toda la carpeta de Drive, porque produciría otro ZIP con una estructura diferente. Instala el archivo descargado con:

```powershell
.\descargar_media.bat --archive "$env:USERPROFILE\Downloads\bigbang-media.zip"
```

El script comprueba los archivos locales, valida todos los vídeos del ZIP y después los instala en `media/` con sus subcarpetas. Si ya están completos, no copia nada. No borra archivos adicionales del destino. Los archivos incluidos en el manifiesto que difieran se sustituyen por la versión verificada; cierra el reproductor antes de actualizar vídeos en uso. No hace falta extraer el ZIP a mano.

`media-source.json` guarda el enlace en `folder_url`. `url` permanece vacía porque no tenemos un enlace directo al ZIP. Si ejecutas el `.bat` sin argumentos y faltan archivos, te indicará la carpeta de Drive y el comando `--archive`.

También funciona sin alojamiento, desde un USB o una carpeta compartida:

```powershell
.\descargar_media.bat --archive "E:\bigbang-media.zip"
```

Para un enlace temporal o firmado, evita guardarlo en Git y usa la variable de entorno:

```powershell
$env:BIGBANG_MEDIA_URL = "ENLACE_DIRECTO_AL_ZIP"
.\descargar_media.bat
```

El descargador no inicia sesión en Drive. Si la carpeta es privada, descarga desde el navegador con una cuenta que tenga acceso y usa `--archive`. Para comprobar la instalación sin descargar:

```powershell
python scripts/media.py check
```

Necesita espacio temporal para el ZIP y su extracción. Una descarga o verificación fallida no reemplaza vídeos existentes. Tras cambiar o añadir archivos a `media/`, vuelve a generar el manifiesto con `preparar_media.bat`.

### Rutas asignadas en esta integración

Quedan asignados los diez vídeos de cámara (incluido `Cyborg.mp4`), ocho contenidos de códigos de barras y cuatro de NFC. Se respeta el nombre de carpeta `NFC` y las mayúsculas de los archivos para que también funcionen en sistemas sensibles a mayúsculas.

Las dos bases y los siete estados del clima ya tienen rutas asignadas con los vídeos de `ventana/` y `pantalla/`. Permanecen sin vídeo los cuatro coches de códigos de barras y los alias NFC Jeep y Batman. `halo.mp4` se conserva sin asociarlo a ninguna acción. Añade esos contenidos después mediante `config.json`.

## Desarrollo y comprobaciones

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/player.test.cjs tests/overlay.test.cjs
```

Node solo es necesario para las pruebas JavaScript, no para ejecutar la aplicación. Estas pruebas cubren eventos simultáneos, interrupciones, fin de vídeo, retorno a la base, lecturas NFC repetidas y fallidas, reconexión, clasificación del clima, estabilidad de la detección y los indicadores NFC superpuestos. Las pruebas del reproductor simulan eventos multimedia: no sustituyen comprobar tus vídeos reales en el navegador y con la cámara/lectores del montaje.

La organización principal es:

```text
main.py                 Arranque único
iniciar_bigbang.bat     Arranque automático con reinicio (tarea programada)
config.json             Dispositivos, clima y vídeos
aliases.json            UID NFC → nombre
barcode_id.json         Código de barras → contenido de figuras
media-manifest.json     Inventario y checksums de vídeos
media-source.json       Enlace directo al ZIP
display_app/
  server.py             HTTP, ciclo de vida y APIs
  state.py              Canales, fin de reproducción y filtro de detecciones
  figures.py            Cámara y YOLO
  nfc.py                PC/SC y retirada de objetos
  audio.py              Navegador sin ventana que pone el sonido en el PC
  barcode.py            Escáner serie y lectura de códigos
  weather.py            OpenWeather y selección de clima
web/
  figuras.html          Pantalla de figuras
  nfc.html              Pantalla de NFC
  player.js             Reproductor compartido
  overlay.html          Indicadores NFC superpuestos (overlay.js, overlay.css)
  audio.html            Sonido de una pantalla en el PC (usa player.js)
  img/                  Logos de los libros NFC
  index.html            Panel de control y simulación
media/                  Tus vídeos locales
scripts/media.py        Preparar, verificar e instalar el ZIP
tests/                  Pruebas Python y JavaScript
```
