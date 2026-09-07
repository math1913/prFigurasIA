Coloca aquí los vídeos de ambas experiencias y del clima.

Se sirven localmente bajo `/media/`. Ejemplo: `media/nfc/prince.mp4`
corresponde a `/media/nfc/prince.mp4` en `config.json`.

No se necesita Internet para reproducir archivos locales.

Los vídeos están excluidos de Git. Descarga `bigbang-media.zip` desde la
[carpeta de media en Google Drive](https://drive.google.com/drive/folders/18BIm4Wl_v0IUXELOWheuGE0pJhidnlNj?usp=drive_link)
y ejecuta `descargar_media.bat --archive "RUTA\bigbang-media.zip"` desde la raíz
del proyecto. No hace falta extraerlo manualmente. Descarga el ZIP preparado,
no la carpeta entera de Drive como otro ZIP. También funciona desde un USB.

Para preparar un paquete con los vídeos locales, ejecuta `preparar_media.bat`.
Genera `media-dist/bigbang-media.zip` y `media-manifest.json`; solo el manifiesto
se guarda en Git. Consulta el README principal para publicar y descargar el ZIP.
