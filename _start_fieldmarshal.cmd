@echo off
title Field Marshal — Field Marshal Brain
echo Starting Field Marshal Brain...
echo Waiting 5 seconds for router to be ready...
timeout /t 5 /nobreak > nul
cd /d "%~dp0"
python field_marshal.py
pause
