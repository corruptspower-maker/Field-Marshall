@echo off
REM LAUNCH.bat — Open all Field Marshal services in Windows Terminal tabs
echo Starting Field Marshal...

wt -w 0 new-tab -d "%~dp0" -p "Command Prompt" "%~dp0_start_router.cmd" ; ^
   new-tab -d "%~dp0" -p "Command Prompt" "%~dp0_start_agent.cmd" ; ^
   new-tab -d "%~dp0" -p "Command Prompt" "%~dp0_start_cline.cmd" ; ^
   new-tab -d "%~dp0" -p "Command Prompt" "%~dp0_start_copilot.cmd" ; ^
   new-tab -d "%~dp0" -p "Command Prompt" "%~dp0_start_fieldmarshal.cmd"

REM Wait for router to start, then open browser
timeout /t 3 /nobreak > nul
start http://localhost:5000
