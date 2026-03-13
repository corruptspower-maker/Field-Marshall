@echo off
title Field Marshal — Terminal Agent
echo Starting Terminal Agent...
cd /d "%~dp0"
python agents\terminal_agent.py
pause
