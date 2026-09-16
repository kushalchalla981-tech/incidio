# Day 1-2 Detailed Task Breakdown

## Day 1: Foundation Setup

### Task 1: Initialize Project Structure (30 min)

**Objective:** Create organized project structure

**Steps:**
```bash
# 1. Create directory structure
cd C:\projectwa\workshop
mkdir backend
cd backend
mkdir app
cd app
mkdir api
cd api
mkdir v1
cd v1
mkdir routes

# 2. Create __init__.py files
cd C:\projectwa\workshop\backend
type nul > app\__init__.py
type nul > app\api\__init__.py
type nul > app\api\v1\__init__.py
type nul > app\api\v1\routes\__init__.py
```

**Verification:**
```bash
# Your structure should look like:
tree /F
```

---

### Task 2: Set Up Python Environment (20 min)

**Steps:**
```bash
# 1. Create virtual environment
cd C:\projectwa\workshop\backend
python -m venv venv

# 2. Activate virtual environment
venv\Scripts\activate

# 3. Upgrade pip
python -m pip install --upgrade pip
```

**Verification:**
```bash
# Should show virtual environment path
where python
```

---

### Task 3: Create Requirements File (10 min)

**Create:** `backend/requirements.txt`

**Content:** See IMPLEMENTATION_FILES.md

**Install:**
```bash
cd C:\projectwa\workshop\backend
pip install -r requirements.txt
```

**Verification:**
```bash
pip list | findstr fastapi
# Should show: fastapi 0.109.0
```

---

### Task 4: Set Up Supabase Database (45 min)

**Steps:**

1. **Create Supabase Project**
   - Go to https://app.supabase.com
   - Click "New Project"
   - Name: `ai-incident-copilot`
   - Database Password: (save this securely!)
   - Region: Choose closest to you
   - Wait 2-3 minutes for provisioning

2. **Enable pgvector Extension**
   - Go to Database → Extensions
   - Search for "vector"
   - Enable `vector` extension

3. **Create Database Schema**
   - Go to SQL Editor
   - Click "New Query"
   - Copy schema from DATABASE_SCHEMA.md
   - Click "Run"

4. **Get Connection Details**
   - Go to Project Settings → API
   - Copy:
     - Project URL (SUPABASE_URL)
     - anon/public key (SUPABASE_KEY)

**Verification:**
- Go to Table Editor
- You should see: logs, incidents, log_templates tables

---

### Task 5: Configure Environment Variables (15 min)

**Create:** `backend/.env.example`

**Content:**
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here

# OpenAI Configuration (optional for Day 1-2)
OPENAI_API_KEY=sk-your-key-here

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Create:** `backend/.env` (copy from .env.example and fill in real values)

**Verification:**
```bash
# Should not show your actual keys
type .env.example
```

---

### Task 6: Create Configuration Module (30 min)

**Create:** `backend/app/config.py`

**Content:** See IMPLEMENTATION_FILES.md

**Verification:**
```bash
cd C:\projectwa\workshop\backend
python -c "from app.config import settings; print(settings.SUPABASE_URL)"
# Should print your Supabase URL
```

---

### Task 7: Create Database Client (30 min)

**Create:** `backend/app/database.py`

**Content:** See IMPLEMENTATION_FILES.md

**Verification:**
```bash
python -c "from app.database import get_supabase_client; client = get_supabase_client(); print('Connected!')"
```

---

### Task 8: Create Pydantic Models (30 min)

**Create:** `backend/app/models.py`

**Content:** See IMPLEMENTATION_FILES.md

---

### Task 9: Create FastAPI Application (45 min)

**Create:** `backend/app/main.py`

**Content:** See IMPLEMENTATION_FILES.md

**Run:**
```bash
cd C:\projectwa\workshop\backend
uvicorn app.main:app --reload
```

**Verification:**
- Open browser: http://localhost:8000/docs
- Should see Swagger UI
- Test /health endpoint

---

### Task 10: Create Health Check Endpoint (30 min)

**Create:** `backend/app/api/v1/routes/health.py`

**Content:** See IMPLEMENTATION_FILES.md

**Verification:**
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", "database": "connected"}
```

---

## Day 2: Core API Implementation

### Task 11: Create Log Endpoints (2 hours)

**Create:** `backend/app/api/v1/routes/logs.py`

**Content:** See IMPLEMENTATION_FILES.md

**Endpoints to implement:**
- `POST /api/v1/logs` - Create single log
- `POST /api/v1/logs/batch` - Create multiple logs
- `GET /api/v1/logs` - List logs with filters
- `GET /api/v1/logs/{id}` - Get single log

**Verification:**
```bash
# Test single log creation
curl -X POST http://localhost:8000/api/v1/logs \
  -H "Content-Type: application/json" \
  -d "{\"timestamp\":\"2026-05-19T10:00:00Z\",\"service\":\"api\",\"level\":\"INFO\",\"message\":\"Test\",\"raw_log\":\"Test log\"}"

# Test log retrieval
curl http://localhost:8000/api/v1/logs?limit=10
```

---

### Task 12: Create File Upload Endpoint (1.5 hours)

**Add to:** `backend/app/api/v1/routes/logs.py`

**Endpoint:** `POST /api/v1/logs/upload`

**Features:**
- Accept .txt, .log files
- Parse common log formats
- Return summary of processed logs

**Verification:**
```bash
curl -X POST http://localhost:8000/api/v1/logs/upload \
  -F "file=@../../sample-logs.txt"
```

---

### Task 13: Create Incident Endpoints (1.5 hours)

**Create:** `backend/app/api/v1/routes/incidents.py`

**Content:** See IMPLEMENTATION_FILES.md

**Endpoints:**
- `POST /api/v1/incidents` - Create incident
- `GET /api/v1/incidents` - List incidents
- `GET /api/v1/incidents/{id}` - Get incident
- `PATCH /api/v1/incidents/{id}` - Update incident

**Verification:**
```bash
# Create incident
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Test Incident\",\"severity\":\"high\",\"start_time\":\"2026-05-19T10:00:00Z\"}"
```

---

### Task 14: Create Docker Configuration (1 hour)

**Create:** `backend/Dockerfile`

**Content:** See IMPLEMENTATION_FILES.md

**Create:** `docker-compose.yml` (in root directory)

**Content:** See IMPLEMENTATION_FILES.md

**Build and Run:**
```bash
cd C:\projectwa\workshop
docker-compose up --build
```

**Verification:**
- Open http://localhost:8000/docs
- All endpoints should work

---

### Task 15: Create .gitignore (10 min)

**Create:** `.gitignore` (in root directory)

**Content:**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
*.log
```

---

### Task 16: Update Documentation (30 min)

**Update:** `README.md` with:
- Installation instructions
- API endpoint documentation
- Example curl commands

---

## Testing Checklist

### Day 1 Tests
- [ ] Virtual environment activates
- [ ] All dependencies install without errors
- [ ] Can connect to Supabase database
- [ ] FastAPI app starts without errors
- [ ] /health endpoint returns success
- [ ] Swagger UI loads at /docs

### Day 2 Tests
- [ ] Can create single log via API
- [ ] Can create batch logs via API
- [ ] Can upload sample-logs.txt file
- [ ] Can query logs with filters (service, level, time_range)
- [ ] Can create incident
- [ ] Can list incidents
- [ ] Can update incident status
- [ ] Docker container builds successfully
- [ ] All endpoints work in Docker

---

## Troubleshooting

### Python Import Errors
```bash
# Make sure you're in the right directory
cd C:\projectwa\workshop\backend

# Make sure virtual environment is activated
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Supabase Connection Errors
```bash
# Test connection
python -c "from app.database import get_supabase_client; client = get_supabase_client(); print(client.table('logs').select('*').limit(1).execute())"
```

### Port Already in Use
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use different port
uvicorn app.main:app --reload --port 8001
```

---

## Next: Implementation Files

See `IMPLEMENTATION_FILES.md` for complete code for all files.
