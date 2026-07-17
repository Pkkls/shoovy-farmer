@echo off
cd /d "%~dp0"
if exist data\STOP_ALL del data\STOP_ALL
echo Bots resumed (STOP flag cleared). The supervisor will relaunch them within a few seconds.
