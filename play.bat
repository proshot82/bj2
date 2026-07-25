@echo off
rem Launcher: Latunny Yanychar 2.0 (LOVE 11.5)
rem Keep this .bat in the bj2 folder, next to main.lua.
set "LOVE=%~dp0work\love-11.5-win64\love.exe"
if not exist "%LOVE%" (
  echo love.exe not found: "%LOVE%"
  echo Keep play.bat in the bj2 folder next to main.lua.
  pause
  exit /b 1
)
start "" "%LOVE%" "%~dp0."
