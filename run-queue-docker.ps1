# Run Redis + RQ workers + API in Linux containers (recommended on Windows when you want
# `use_queue=true` / `VITE_INGEST_USE_QUEUE=true` with real background jobs).
# Prerequisite: Docker Desktop.
#
# Usage (from repo root):
#   .\run-queue-docker.ps1
#
# Then point the frontend at http://localhost:8000 (or use the bundled frontend service).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting redis, api, worker (x2) — Ctrl+C to stop." -ForegroundColor Cyan
docker compose up --build redis api worker
