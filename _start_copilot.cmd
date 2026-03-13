@echo off
title Field Marshal — Copilot Agent
echo Starting Copilot Agent...
cd /d "%~dp0"
python agents\copilot_agent.py
pause
