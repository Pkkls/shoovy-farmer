@echo off
cd /d "%~dp0"
if not exist bin\supervisor.exe (echo Run build.bat first. & pause & exit /b 1)
bin\supervisor.exe
