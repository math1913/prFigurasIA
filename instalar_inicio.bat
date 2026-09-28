@echo off
rem Arranque automatico sin permisos de administrador: un acceso directo a iniciar_bigbang.bat
rem en la carpeta Inicio del usuario. Se ejecuta una sola vez.
rem   instalar_inicio.bat           crea el acceso directo (ventana minimizada)
rem   instalar_inicio.bat --quitar  lo borra
setlocal
set "ACCESO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BigBang.lnk"
set "DESTINO=%~dp0iniciar_bigbang.bat"
set "CARPETA=%~dp0"

if /i "%~1"=="--quitar" (
  del "%ACCESO%" 2>nul
  echo Arranque automatico quitado.
  goto fin
)

powershell -NoProfile -NonInteractive -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ACCESO); $s.TargetPath = $env:DESTINO; $s.WorkingDirectory = $env:CARPETA; $s.WindowStyle = 7; $s.Save()"
if errorlevel 1 (
  echo No se pudo crear el acceso directo en %ACCESO%
) else (
  echo Listo: BigBang arrancara al iniciar sesion.
  echo Acceso directo: %ACCESO%
)

:fin
pause
