@echo off
cd /d "%~dp0"
echo Registering Shoovy Farmer to start automatically when you log in...
schtasks /create /tn "ShoovyFarmer" /tr "wscript.exe \"%~dp0run-hidden.vbs\"" /sc onlogon /rl limited /f
if %errorlevel%==0 (
  echo.
  echo Installed. It will run in the background every time you log in.
  echo Starting it now...
  wscript.exe "%~dp0run-hidden.vbs"
) else (
  echo Failed to register the task.
)
pause
