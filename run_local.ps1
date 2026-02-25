
# run_local.ps1
Write-Host "Setting up SmartToll to run locally without Docker..." -ForegroundColor Green

# 1. Setup .env file
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "IMPORTANT: Please edit .env with your remote Kafka, Redis, and Postgres credentials if you don't have them running locally!" -ForegroundColor Red
}

# 2. Start services in separate windows
Write-Host "Starting Billing Service..."
Start-Process powershell -ArgumentList "-NoExit -Command `"cd billing_service; if (-not (Test-Path venv)) { python -m venv venv }; .\venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`""

Write-Host "Starting Toll Processor..."
Start-Process powershell -ArgumentList "-NoExit -Command `"cd toll_processor; if (-not (Test-Path venv)) { python -m venv venv }; .\venv\Scripts\activate; pip install -r requirements.txt; python -m app.main`""

Write-Host "Starting OBU Simulator..."
Start-Process powershell -ArgumentList "-NoExit -Command `"cd obu_simulator; if (-not (Test-Path venv)) { python -m venv venv }; .\venv\Scripts\activate; pip install -r requirements.txt; python obu_simulator.py`""

Write-Host "All services started in separate windows." -ForegroundColor Green

