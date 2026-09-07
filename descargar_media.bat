@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\media.py sync %*
) else (
  python scripts\media.py sync %*
)
set "RESULT=%ERRORLEVEL%"
popd
if "%~1"=="" pause
exit /b %RESULT%
