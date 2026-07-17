@echo off
schtasks /delete /tn "ShoovyFarmer" /f
echo Removed the startup task. (Running bots keep running until you STOP them or reboot.)
pause
