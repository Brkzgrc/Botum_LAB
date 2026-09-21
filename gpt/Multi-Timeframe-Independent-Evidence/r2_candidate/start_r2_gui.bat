@echo off
cd /d "%~dp0"
python r2_candidate_gui.py
if errorlevel 1 (
  echo.
  echo Uygulama baslatilamadi. Python ve gereksinimlerin kurulu oldugunu kontrol edin.
  pause
)
