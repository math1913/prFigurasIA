# BigBang · Figuras, NFC y pantallas HTML

Una aplicación Python ejecuta el detector YOLO, el escáner de códigos de barras, los lectores NFC y el clima en el mismo PC. Sirve dos pantallas HTML independientes, reproduce vídeos locales y ya no lee ni escribe `biomax.xml` o `temp.xml` ni necesita Admira. Cámara y códigos de barras comparten `/figuras`; NFC utiliza `/nfc`.

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

El sonido sigue desactivado por defecto (`muted: true`). Para oír las canciones, añade `"muted": false` a los vídeos NFC que quieras escuchar en `config.json`, reinicia y pulsa «Iniciar reproducción» si el navegador lo solicita.

No hace falta activar el entorno virtual. El desarrollo y las pruebas web se han realizado con Python 3.13.

| URL | Uso |
| --- | --- |
| http://localhost:8002/ | Estado de los dispositivos y accesos a las pantallas |
| http://localhost:8002/figuras | Pantalla de figuras |
| http://localhost:8002/nfc | Pantalla de NFC |
| http://localhost:8002/objetos | API de presencia NFC, conserva los nombres y el puerto original |

Abre cada pantalla en una ventana del navegador, muévela al monitor correspondiente y pulsa F11 o el botón de pantalla completa. Las páginas necesitan el servidor en ejecución; no se abren directamente como archivos. Detén la aplicación con Ctrl+C.

El servidor escucha en `127.0.0.1:8002`. Puedes cambiar el puerto con `--port 8003`. Si necesitas pantallas en otros ordenadores de la red, configura explícitamente `--host 0.0.0.0`; no hay autenticación para ese modo. Usa una sola instancia: varias instancias competirían por la cámara y los lectores.

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

`media/nfc/prince.mp4` debe existir. Usa vídeos que tu navegador pueda reproducir; MP4 con H.264 es una opción habitual. El reproductor mantiene las proporciones y usa bandas negras si el formato no coincide con la pantalla.

`muted` es `true` por defecto para permitir reproducción automática. Si lo cambias a `false`, el navegador puede pedir una interacción inicial: la pantalla mostrará «Iniciar reproducción». Los navegadores aplican sus propias reglas de autoplay.

Con `src: null` se muestra una pantalla provisional con el título. Una acción sin vídeo dura `placeholder_seconds` (5 segundos por defecto). Un vídeo configurado termina con su evento real `ended`; **no usa una duración fija de 20 segundos**. `max_event_seconds` (3600 por defecto) es un límite de recuperación para vídeos bloqueados o pantallas ausentes: ajústalo por encima de la duración del vídeo más largo.

Si un vídeo de acción no se puede cargar, se vuelve a la base. Si falla el vídeo base del clima, se intenta el base genérico de esa pantalla. Si este también falla, aparece la pantalla provisional. Los errores de archivo/reproducción se registran en la consola del navegador.

## Comportamiento

- El vídeo base se reproduce en bucle.
- Una nueva acción interrumpe inmediatamente el vídeo de acción anterior **del mismo canal**.
- Cuando termina el vídeo de acción, vuelve a comenzar el vídeo base que corresponda en ese momento.
- Los canales de figuras y NFC pueden reproducir acciones simultáneas sin interferirse.
- Cada acción tiene un identificador: un aviso de fin tardío del vídeo anterior no puede cerrar el vídeo nuevo.
- Las pantallas consultan el estado cada 250 ms y reintentan automáticamente si se corta la conexión. Al recargar una pantalla, retoma el evento vigente por su tiempo transcurrido. Si el vídeo termina durante una desconexión, vuelve a la base localmente y confirma el fin cuando recupera conexión.
- El estado está en memoria: al reiniciar la aplicación, comienza desde la base.

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

Se activa **al retirar el objeto**, conservando el comportamiento original. `aliases.json` asigna UID a contenido. Los alias disponibles son Beatles, Jackson, Prince, Superman, Jeep y Batman. El mismo objeto puede retirarse varias veces y activar su vídeo cada vez.

Las tarjetas sin alias o con lectura fallida no activan contenido. Los lectores se distinguen por su nombre; retirar una tarjeta no borra la presencia en otros lectores. `/objetos` mantiene los cuatro objetos monitorizados originalmente: Beatles, Jackson, Prince y Superman, configurables mediante `nfc.monitored_objects`. Responde 503 si el lector no está disponible.

El lector requiere PC/SC y `pyscard`. Si el sistema no reconoce el ACR122U, consulta los [controladores oficiales de ACS](https://www.acs.com.hk/en/products/3/acr122u-usb-nfc-reader/). La aplicación espera si no hay lectores y los detecta al conectarlos. `nfc.enabled: false` desactiva la integración.

Si aparece el error `0x8010001D`, Windows informa de que el servicio de tarjetas inteligentes no está ejecutándose. Comprueba el lector y el servicio «Tarjeta inteligente» en el PC del montaje. La aplicación reintenta y mantiene las pantallas disponibles.

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
node --test tests/player.test.cjs
```

Node solo es necesario para las pruebas JavaScript, no para ejecutar la aplicación. Estas pruebas cubren eventos simultáneos, interrupciones, fin de vídeo, retorno a la base, lecturas NFC repetidas y fallidas, reconexión, clasificación del clima y estabilidad de la detección. Las pruebas del reproductor simulan eventos multimedia: no sustituyen comprobar tus vídeos reales en el navegador y con la cámara/lectores del montaje.

La organización principal es:

```text
main.py                 Arranque único
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
  barcode.py            Escáner serie y lectura de códigos
  weather.py            OpenWeather y selección de clima
web/
  figuras.html          Pantalla de figuras
  nfc.html              Pantalla de NFC
  player.js             Reproductor compartido
  index.html            Panel de control y simulación
media/                  Tus vídeos locales
scripts/media.py        Preparar, verificar e instalar el ZIP
tests/                  Pruebas Python y JavaScript
```
