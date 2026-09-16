# AI Incident Copilot - Setup Script
# Run this script to set up the development environment

Write-Host "🚀 Setting up AI Incident Copilot..." -ForegroundColor Cyan

# Check prerequisites
Write-Host "`n📋 Checking prerequisites..." -ForegroundColor Yellow

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Python not found. Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Check Node.js
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Node.js: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# Check Docker
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "⚠️  Docker not found. Required for database services." -ForegroundColor Yellow
}

# Setup Backend
Write-Host "`n🔧 Setting up backend..." -ForegroundColor Yellow
Set-Location backend

# Create virtual environment if it doesn't exist
if (-not (Test-Path venv)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Activate and install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Check .env file
if (-not (Test-Path .env)) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Cyan
    Copy-Item .env.example .env
    Write-Host "⚠️  Please edit backend/.env with your credentials" -ForegroundColor Yellow
}

Set-Location ..

# Setup Frontend
Write-Host "`n🎨 Setting up frontend..." -ForegroundColor Yellow
Set-Location frontend

if (-not (Test-Path node_modules)) {
    Write-Host "Installing Node.js dependencies..." -ForegroundColor Cyan
    npm install
}

Set-Location ..

# Create .env.example at root if it doesn't exist
if (-not (Test-Path .env.example)) {
    Write-Host "`n📝 Creating root .env.example..." -ForegroundColor Cyan
    @'
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here

# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
'@ | Set-Content .env.example -Encoding UTF8
}

Write-Host "`n✅ Setup complete!" -ForegroundColor Green
Write-Host "`n📖 Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit backend/.env with your Supabase and OpenAI credentials" -ForegroundColor White
Write-Host "2. Start services: docker-compose up" -ForegroundColor White
Write-Host "3. Run backend: cd backend; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload" -ForegroundColor White
Write-Host "4. Run frontend: cd frontend; npm run dev" -ForegroundColor White
Write-Host "`n🌐 Access the application:" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
