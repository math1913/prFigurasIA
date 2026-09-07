@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\media.py pack
) else (
  python scripts\media.py pack
)
set "RESULT=%ERRORLEVEL%"
popd
pause
exit /b %RESULT%
