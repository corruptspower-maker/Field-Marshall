@echo off
REM INSTALL.bat — One-time setup: install Python dependencies and index docs
echo ================================================
echo  Field Marshal — Installation
echo ================================================
echo.

echo [1/2] Installing Python dependencies...
pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo ERROR: pip install failed. Ensure Python and pip are in PATH.
    pause
    exit /b 1
)
echo.

echo [2/2] Indexing documents into RAG (optional)...
if exist "%~dp0docs\" (
    python "%~dp0rag_index.py" --docs "%~dp0docs"
) else (
    echo   No docs\ directory found - skipping RAG index.
    echo   Create docs\ with .md or .txt files and re-run to enable RAG.
)
echo.

echo ================================================
echo  Installation complete.
echo  Run smoke_test.py to verify, then LAUNCH.bat
echo ================================================
pause
