# RemoteHive AutoScraper Service

A comprehensive web scraping service integrated into the RemoteHive application ecosystem. This service provides automated web scraping capabilities with robust monitoring, testing, and management features.

## Quick Start

### Prerequisites

- Python 3.8+
- Redis server
- PostgreSQL database
- RemoteHive main application

### Installation

1. **Install Dependencies**:
   ```bash
   cd autoscraper-engine-api
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start Service**:
   ```bash
   # Automatic startup (recommended)
   cd ..
   python start_remotehive_macos.py
   
   # Manual startup
   cd scripts
   python startup.py
   ```

### Verification

```bash
# Check service health
curl http://localhost:8001/health

# View service metrics
curl http://localhost:8001/metrics

# Access dashboard
open http://localhost:8001/api/v1/autoscraper/dashboard
```

## Service Architecture

```
AutoScraper Service (Port 8001)
├── FastAPI Application
├── Health Monitoring
├── Metrics Collection
├── Admin Panel Proxy
├── API Endpoints
└── Background Tasks
```

### Core Components

- **FastAPI App** (`backend/main.py`) - Main application entry point
- **API Routes** (`backend/api/`) - REST API endpoints
- **Health Checks** (`backend/api/health.py`) - Service health monitoring
- **Metrics** (`backend/api/metrics.py`) - Prometheus metrics
- **Configuration** (`backend/core/config.py`) - Service configuration

## API Endpoints

### Health & Monitoring

```http
GET /health                    # Overall health status
GET /health/liveness          # Liveness probe
GET /health/readiness         # Readiness probe
GET /health/database          # Database connectivity
GET /health/redis             # Redis connectivity
GET /metrics                  # Prometheus metrics
```

### AutoScraper API

```http
GET /api/v1/autoscraper/dashboard        # Service dashboard
GET /api/v1/autoscraper/engine/state     # Engine status
POST /api/v1/autoscraper/jobs/start      # Start scraping job
POST /api/v1/autoscraper/jobs/pause      # Pause scraping job
GET /api/v1/autoscraper/jobs/list        # List all jobs
GET /api/v1/autoscraper/job-boards       # Available job boards
GET /api/v1/autoscraper/system/metrics   # System metrics
```

### Admin Panel

```http
GET /admin/{path}             # Admin panel proxy
```

## Scripts & Utilities

### Service Management

```bash
cd scripts

# Service Manager
python service_manager.py start     # Start service
python service_manager.py stop      # Stop service
python service_manager.py restart   # Restart service
python service_manager.py status    # Check status
python service_manager.py logs      # View logs

# Startup Script
python startup.py                   # Start with dependency checks

# Health Monitor
python health_monitor.py check      # Single health check
python health_monitor.py monitor    # Continuous monitoring
python health_monitor.py summary    # Health summary
```

### Testing

```bash
cd ../tests

# Comprehensive Tests
python test_autoscraper_comprehensive.py

# Edge Case Tests
python test_autoscraper_edge_cases.py

# Integration Tests
python test_integration_main_autoscraper.py
```

## Configuration

### Environment Variables

```bash
# Service Configuration
AUTOSCRAPER_PORT=8001
AUTOSCRAPER_HOST=0.0.0.0
DEBUG=false

# Database
DATABASE_URL=postgresql://user:password@localhost/remotehive

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here

# Monitoring
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL=30
```

### Service Settings

Edit `backend/core/config.py` for advanced configuration:

```python
class Settings(BaseSettings):
    # Application
    app_name: str = "RemoteHive AutoScraper Service"
    version: str = "1.0.0"
    debug: bool = False
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    
    # Security
    secret_key: str
    api_key: str
    allowed_hosts: List[str] = ["*"]
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # Monitoring
    metrics_enabled: bool = True
    health_check_interval: int = 30
```

## Development

### Local Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Start in development mode
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Run tests
pytest tests/

# Code formatting
black backend/
flake8 backend/
```

### Project Structure

```
autoscraper-engine-api/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   ├── autoscraper.py   # AutoScraper API routes
│   │   ├── health.py        # Health check endpoints
│   │   └── metrics.py       # Metrics endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration settings
│   │   ├── middleware.py    # Custom middleware
│   │   └── security.py      # Security utilities
│   └── utils/
│       ├── __init__.py
│       ├── database.py      # Database utilities
│       └── redis.py         # Redis utilities
├── scripts/
│   ├── startup.py           # Service startup script
│   ├── service_manager.py   # Service management
│   └── health_monitor.py    # Health monitoring
├── tests/
│   ├── test_comprehensive.py
│   ├── test_edge_cases.py
│   └── test_integration.py
├── logs/
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── README.md
```

## Monitoring & Observability

### Health Monitoring

The service includes comprehensive health monitoring:

- **Service Health**: Overall service status
- **Dependency Health**: Database, Redis, Celery status
- **System Metrics**: CPU, memory, disk usage
- **Performance Metrics**: Response times, throughput
- **Alert System**: Configurable alerts for failures

### Metrics Collection

Prometheus metrics are available at `/metrics`:

- HTTP request metrics
- Database connection metrics
- Redis operation metrics
- Celery task metrics
- Custom business metrics

### Logging

Structured logging with multiple levels:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logger.info("Service started successfully")
logger.error("Database connection failed", extra={"error": str(e)})
```

Logs are written to:
- Console (development)
- File: `logs/service.log` (production)
- Structured JSON format for log aggregation

## Testing

### Test Suites

1. **Comprehensive Tests**: Full endpoint coverage
2. **Edge Case Tests**: Error handling and boundary conditions
3. **Integration Tests**: Cross-service communication
4. **Performance Tests**: Load and stress testing

### Test Coverage

- ✅ All API endpoints
- ✅ Health check endpoints
- ✅ Authentication & authorization
- ✅ Error handling
- ✅ Rate limiting
- ✅ Database operations
- ✅ Redis operations
- ✅ Service integration

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test suite
python tests/test_autoscraper_comprehensive.py

# With coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## Deployment

### Production Deployment

1. **Environment Setup**:
   ```bash
   # Set production environment variables
   export DEBUG=false
   export AUTOSCRAPER_PORT=8001
   export DATABASE_URL=postgresql://...
   export REDIS_URL=redis://...
   ```

2. **Service Start**:
   ```bash
   # Using service manager
   python scripts/service_manager.py start
   
   # Or with systemd (recommended)
   sudo systemctl start autoscraper-service
   ```

3. **Health Verification**:
   ```bash
   # Check service health
   curl http://localhost:8001/health
   
   # Monitor continuously
   python scripts/health_monitor.py monitor
   ```

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY scripts/ ./scripts/

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# Build and run
docker build -t autoscraper-service .
docker run -p 8001:8001 autoscraper-service
```

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check dependencies
redis-cli ping
psql $DATABASE_URL -c "SELECT 1;"

# Check port availability
lsof -i :8001

# Review logs
python scripts/service_manager.py logs
```

#### Health Check Failures

```bash
# Check service status
curl -v http://localhost:8001/health

# Check process
ps aux | grep uvicorn

# Check resources
top -p $(pgrep -f "uvicorn.*autoscraper")
```

#### Performance Issues

```bash
# Monitor metrics
curl http://localhost:8001/metrics

# Check database performance
# Review slow query logs

# Monitor Redis
redis-cli info stats
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG=true

# Start with verbose logging
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --log-level debug
```

## Security

### Authentication

- API key authentication for protected endpoints
- JWT tokens for session management
- Rate limiting to prevent abuse

### Security Headers

- CORS configuration
- Trusted host validation
- Security middleware

### Best Practices

- Use HTTPS in production
- Rotate API keys regularly
- Monitor authentication attempts
- Keep dependencies updated
- Implement proper logging

## Contributing

### Development Workflow

1. **Setup Development Environment**:
   ```bash
   git clone <repository>
   cd autoscraper-engine-api
   pip install -r requirements-dev.txt
   ```

2. **Make Changes**:
   - Follow code style guidelines
   - Add tests for new features
   - Update documentation

3. **Test Changes**:
   ```bash
   # Run all tests
   python -m pytest tests/ -v
   
   # Check code style
   black backend/ --check
   flake8 backend/
   ```

4. **Submit Changes**:
   - Create pull request
   - Ensure CI passes
   - Request code review

### Code Style

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use type hints where appropriate
- Write comprehensive docstrings
- Add unit tests for new code

## Support

For support and questions:

1. **Documentation**: Check this README and integration docs
2. **Health Checks**: Run health monitor for diagnostics
3. **Logs**: Review service logs for error details
4. **Tests**: Run test suites to validate functionality
5. **Issues**: Create GitHub issues for bugs or feature requests

## License

This project is part of the RemoteHive application suite.

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Maintainer**: RemoteHive Development Team