@echo off
rem Arranque del montaje BigBang para una tarea programada al iniciar sesion.
rem Ejecuta main.py (camara, escaner, NFC, clima y pantallas) y lo reinicia si se cierra.
rem Para detenerlo, cierra esta ventana.
setlocal
title BigBang
pushd "%~dp0"
rem 0.0.0.0: accesible desde la red local (http://IP-DEL-PC:8002). 127.0.0.1: solo este PC.
set "HOST=0.0.0.0"
set "PORT=8002"
set "PYTHON=.venv\Scripts\python.exe"
if not exist "logs" mkdir "logs"

if not exist "%PYTHON%" (
  echo No existe %PYTHON%. Crea el entorno virtual como indica el README.
  echo [%date% %time%] Falta %PYTHON%>>"logs\arranque.log"
  goto fin
)

rem Variables locales opcionales en .env (Git lo ignora), por ejemplo OPENWEATHER_API_KEY=TU_CLAVE
if exist ".env" for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"

rem Una sola instancia: si el puerto ya esta ocupado, BigBang ya esta en marcha.
"%PYTHON%" -c "import socket, sys; socket.socket().bind((sys.argv[1], int(sys.argv[2])))" %HOST% %PORT% 2>nul
if errorlevel 1 (
  echo El puerto %PORT% ya esta en uso: BigBang ya esta en marcha.
  echo [%date% %time%] Puerto %PORT% ocupado, no se inicia otra instancia>>"logs\arranque.log"
  goto fin
)

:bucle
echo [%date% %time%] Inicio de main.py>>"logs\arranque.log"
"%PYTHON%" main.py --host %HOST% --port %PORT%
echo [%date% %time%] main.py se cerro con codigo %errorlevel%, reinicio en 10 s>>"logs\arranque.log"
echo main.py se cerro. Se reinicia en 10 segundos.
ping -n 11 127.0.0.1 >nul
goto bucle

:fin
popd
ping -n 6 127.0.0.1 >nul
