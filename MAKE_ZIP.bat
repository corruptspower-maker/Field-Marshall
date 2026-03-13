@echo off
REM MAKE_ZIP.bat — Package Field Marshal to Desktop as a zip
echo Creating Field Marshal zip on Desktop...

set "SRC=%~dp0"

powershell -NoProfile -Command ^
  "$date = Get-Date -Format 'yyyyMMdd'; $dst = [Environment]::GetFolderPath('Desktop') + '\Field-Marshal-' + $date + '.zip'; Compress-Archive -Path '%SRC%*' -DestinationPath $dst -Force -CompressionLevel Optimal; Write-Host ('Done: ' + $dst)"

if errorlevel 1 (
    echo ERROR: Zip creation failed.
    pause
    exit /b 1
)
pause
