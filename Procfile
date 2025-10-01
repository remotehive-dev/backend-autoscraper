# Backend API Process
web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT

# Autoscraper Service Process  
autoscraper: cd autoscraper && uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Celery Worker (optional, can be deployed as separate service)
worker: cd backend && celery -A core.celery worker --loglevel=info

# Celery Beat Scheduler (optional, can be deployed as separate service)
beat: cd backend && celery -A core.celery beat --loglevel=info