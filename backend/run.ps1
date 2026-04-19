# Start the FastAPI API (http://127.0.0.1:8000).
# In another terminal: cd ..\frontend && npm run dev  →  http://localhost:5173
Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} else {
    $py = "python"
}

& $py -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "uvicorn is missing from this environment. Installing requirements.txt ..."
    & $py -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install failed. Fix errors above, then run this script again."
        exit 1
    }
}

Write-Host ""
Write-Host "API:  http://127.0.0.1:8000   (health: /api/health)" -ForegroundColor Cyan
Write-Host "Next: open a second terminal, cd frontend, npm run dev → http://localhost:5173" -ForegroundColor Yellow
Write-Host "Live data: USE_FIXTURES=false → run: $py -m app.ingestion.runner" -ForegroundColor DarkGray
Write-Host ""

& $py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
