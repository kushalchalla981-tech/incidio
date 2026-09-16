# AI Incident Copilot - Quick Start Commands
# Source this script or run individual commands

Write-Host "🚀 AI Incident Copilot - Quick Start" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Start Database (Docker):" -ForegroundColor Yellow
Write-Host "   docker-compose up -d" -ForegroundColor White
Write-Host ""
Write-Host "2. Start Backend:" -ForegroundColor Yellow
Write-Host "   cd backend; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "3. Start Frontend (new terminal):" -ForegroundColor Yellow
Write-Host "   cd frontend; npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "4. View API Docs:" -ForegroundColor Yellow
Write-Host "   http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "5. View Frontend:" -ForegroundColor Yellow
Write-Host "   http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "To stop all services:" -ForegroundColor Yellow
Write-Host "   docker-compose down" -ForegroundColor White
