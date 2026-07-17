@echo off
cd /d "%~dp0"
echo Building Shoovy Farmer bots...
for %%d in (fisher econ watchdog dashboard supervisor) do (
  echo   building %%d
  pushd %%d
  go build -ldflags "-s -w" -o "..\bin\%%d.exe" . || (echo BUILD FAILED for %%d & popd & exit /b 1)
  popd
)
echo.
echo Done. Executables are in the bin\ folder.
