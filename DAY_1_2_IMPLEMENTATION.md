# Day 1-2 Implementation Guide

## Overview

**Goal:** Build the foundational infrastructure for AI Incident Copilot
**Duration:** 2 days
**Team:** 3 developers (can work in parallel on different tasks)

---

## What We're Building

### Day 1: Project Setup & Database
- Project structure and dependencies
- Supabase database setup with schema
- FastAPI application foundation
- Health check endpoint

### Day 2: Core API & CRUD Operations
- Database connection layer
- Log ingestion endpoints (single, batch, file upload)
- Log retrieval with filtering
- Incident management CRUD
- Docker containerization

---

## Prerequisites

### Required Accounts
- [ ] Supabase account (free tier) - https://app.supabase.com
- [ ] OpenAI API key (optional for Day 1-2) - https://platform.openai.com

### Required Software
- [ ] Python 3.11+ installed
- [ ] Git installed
- [ ] Docker Desktop installed (for Day 2)
- [ ] Code editor (VS Code recommended)

### Verify Installation
```bash
python --version  # Should be 3.11+
git --version
docker --version
```

---

## Architecture for Day 1-2

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  API Endpoints                                    │  │
│  │  - GET  /health                                   │  │
│  │  - POST /api/v1/logs                             │  │
│  │  - POST /api/v1/logs/batch                       │  │
│  │  - POST /api/v1/logs/upload                      │  │
│  │  - GET  /api/v1/logs                             │  │
│  │  - POST /api/v1/incidents                        │  │
│  │  - GET  /api/v1/incidents                        │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Database Layer (Supabase Client)                │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Supabase (PostgreSQL + pgvector)                      │
│  - logs table                                           │
│  - incidents table                                      │
│  - log_templates table                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Key Technical Decisions

### 1. Why Supabase?
- ✅ Free tier includes PostgreSQL + pgvector
- ✅ No Docker setup needed for database
- ✅ Built-in connection pooling
- ✅ Web dashboard for debugging
- ✅ Easy migration to self-hosted later

### 2. Why FastAPI?
- ✅ Async support (important for ML workloads later)
- ✅ Automatic API documentation (Swagger UI)
- ✅ Type safety with Pydantic
- ✅ Fast development iteration

### 3. Database Schema Design
- **logs table:** Stores raw and parsed logs with vector embeddings
- **incidents table:** Groups related anomalies
- **log_templates table:** Stores Drain3 templates (for Day 3+)

---

## Success Criteria

By end of Day 2, you should be able to:
- [ ] Upload sample-logs.txt via API
- [ ] Query logs by service and time range
- [ ] Create and manage incidents
- [ ] View API documentation at /docs
- [ ] Run application in Docker container

---

## Common Issues & Solutions

### Issue 1: Supabase Connection Timeout
**Symptom:** `Connection timeout` errors
**Solution:** Use connection pooler URL: `[project].pooler.supabase.com:6543`

### Issue 2: Import Errors
**Symptom:** `ModuleNotFoundError`
**Solution:** Ensure you're in virtual environment and ran `pip install -r requirements.txt`

### Issue 3: Port Already in Use
**Symptom:** `Address already in use: 8000`
**Solution:** Kill existing process or use different port: `uvicorn main:app --port 8001`

### Issue 4: CORS Errors (if testing from browser)
**Symptom:** `CORS policy blocked`
**Solution:** Already configured in main.py with `allow_origins=["*"]` for development

---

## Next Steps After Day 1-2

**Day 3-4:** Integrate Drain3 log parsing
**Day 5-6:** Add PyOD anomaly detection
**Day 7:** Implement vector embeddings and semantic search
**Day 8-9:** LLM integration for root cause analysis
**Day 10-11:** Build frontend dashboard

---

## File Structure Reference

```
ai-incident-copilot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # Supabase client
│   │   ├── models.py            # Pydantic models
│   │   └── api/
│   │       └── v1/
│   │           ├── __init__.py
│   │           └── routes/
│   │               ├── health.py    # Health check
│   │               ├── logs.py      # Log endpoints
│   │               └── incidents.py # Incident endpoints
│   ├── requirements.txt
│   ├── .env.example
│   ├── .env                     # Your local config (gitignored)
│   └── Dockerfile
├── sample-logs.txt              # Test data
├── docker-compose.yml
├── .gitignore
└── DAY_1_2_TASKS.md            # Detailed task breakdown
```

---

## Time Estimates

| Task | Time | Assignee |
|------|------|----------|
| **Day 1** | | |
| Project structure setup | 30 min | Dev 1 |
| Supabase setup + schema | 45 min | Dev 2 |
| FastAPI foundation | 1 hour | Dev 1 |
| Health check endpoint | 30 min | Dev 1 |
| **Day 2** | | |
| Database connection layer | 1 hour | Dev 2 |
| Log ingestion endpoints | 2 hours | Dev 1 |
| Log retrieval endpoints | 1 hour | Dev 1 |
| Incident CRUD | 1.5 hours | Dev 3 |
| File upload endpoint | 1.5 hours | Dev 1 |
| Docker setup | 1 hour | Dev 2 |
| Testing & documentation | 1 hour | All |

**Total:** ~12 hours (1.5 days with 3 developers working in parallel)

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Python Client](https://supabase.com/docs/reference/python/introduction)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

**Ready to start? Proceed to DAY_1_2_TASKS.md for detailed step-by-step instructions.**
