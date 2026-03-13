@echo off
title Field Marshal — Cline Agent
echo Starting Cline Agent...
cd /d "%~dp0"
python agents\cline_agent.py
pause
