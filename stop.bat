@echo off
cd /d "%~dp0"
if not exist data mkdir data
type nul > data\STOP_ALL
echo Bots stopped (STOP flag set). Run start.bat or use the dashboard to resume.
