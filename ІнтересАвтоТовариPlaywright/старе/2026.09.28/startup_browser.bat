@echo off

set "APP_DIR=%~dp0"
set "PYTHON=%APP_DIR%.venv\Scripts\pythonw.exe"

echo Checking Edge debugging port 9222...

powershell -NoProfile -Command ^
    "try { Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if %ERRORLEVEL% EQU 0 (
    echo Edge with debugging is already running on port 9222.
) else (
    echo Starting Edge with debugging...

    start "" msedge.exe ^
        --remote-debugging-port=9222 ^
        --user-data-dir="%APP_DIR%edge_profile" ^
        --no-first-run ^
        --no-default-browser-check ^
        "https://concord-shop.com/search?q=" ^
        "https://sklep.martextruck.pl/clientcatalogue/searchform.aspx" ^
        "https://webterminal.opoltrans.com.pl/search/v2/product?searchOption=-1"

    timeout /t 2 /nobreak >nul
)

echo Starting Playwright app...

start "" "%PYTHON%" "%APP_DIR%playwright_app.pyw"