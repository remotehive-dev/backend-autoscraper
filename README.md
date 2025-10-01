# RemoteHive Backend & Autoscraper Services

This repository contains the backend API and autoscraper services for the RemoteHive job board platform, configured for deployment on Railway.

## Architecture Overview

### Services
- **Backend API** (Port 8000) - FastAPI application with MongoDB
- **Autoscraper Service** (Port 8001) - Independent FastAPI service for job scraping

### Technology Stack
- **Backend**: FastAPI, MongoDB (via Beanie ODM), Redis, Celery
- **Autoscraper**: FastAPI, SQLite, MongoDB integration
- **Authentication**: JWT tokens, Role-based access control
- **Background Tasks**: Celery workers with Redis

## Project Structure

```
.
├── backend/                 # Main Backend API
│   ├── main.py             # FastAPI application entry
│   ├── api/                # API endpoints and routers
│   ├── core/               # Core utilities (auth, config, database)
│   ├── models/             # Database models
│   ├── services/           # Business logic
│   └── middleware/         # Custom middleware
├── autoscraper/            # Autoscraper Service
│   ├── app/
│   │   ├── main.py         # Autoscraper FastAPI app
│   │   ├── api/            # Scraping endpoints
│   │   ├── scrapers/       # Scraping engines
│   │   └── database/       # Database managers
│   └── requirements.txt    # Autoscraper dependencies
├── requirements.txt        # Backend dependencies
├── railway.json           # Railway deployment configuration
└── Procfile              # Process definitions for Railway
```

## Environment Variables

### Backend API
```bash
# Database
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/remotehive
REDIS_URL=redis://redis:6379

# Authentication
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["https://remotehive.vercel.app", "https://admin.remotehive.com"]

# External APIs
CLERK_SECRET_KEY=your-clerk-secret-key
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Autoscraper Service
```bash
# Database
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/remotehive
SQLITE_DATABASE_URL=sqlite:///./autoscraper.db

# Authentication
JWT_SECRET_KEY=your-jwt-secret-key
AUTOSCRAPER_API_KEY=your-autoscraper-api-key

# External APIs
OPENROUTER_API_KEY=your-openrouter-api-key
```

## Railway Deployment

### Prerequisites
1. Railway account
2. GitHub repository connected to Railway
3. MongoDB Atlas database
4. Redis instance (Railway provides this)

### Deployment Steps

1. **Connect Repository to Railway**
   ```bash
   # Railway will automatically detect the services
   # Backend API will be deployed from /backend
   # Autoscraper will be deployed from /autoscraper
   ```

2. **Configure Environment Variables**
   - Set all required environment variables in Railway dashboard
   - Ensure MongoDB Atlas connection string is correct
   - Configure CORS origins for your frontend domains

3. **Deploy Services**
   - Railway will automatically build and deploy both services
   - Backend API will be available at: `https://backend-production-xxxx.up.railway.app`
   - Autoscraper will be available at: `https://autoscraper-production-xxxx.up.railway.app`

## Local Development

### Setup
```bash
# Clone repository
git clone https://github.com/remotehive-dev/backend-autoscraper.git
cd backend-autoscraper

# Install backend dependencies
pip install -r requirements.txt

# Install autoscraper dependencies
cd autoscraper
pip install -r requirements.txt
cd ..

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Running Services

#### Backend API
```bash
cd backend
uvicorn main:app --reload --port 8000
```

#### Autoscraper Service
```bash
cd autoscraper
uvicorn app.main:app --reload --port 8001
```

### Testing
```bash
# Run backend tests
cd backend
pytest

# Run autoscraper tests
cd autoscraper
pytest
```

## API Documentation

### Backend API
- **Base URL**: `https://your-backend-url.railway.app`
- **Swagger Docs**: `https://your-backend-url.railway.app/docs`
- **Health Check**: `https://your-backend-url.railway.app/health`

### Autoscraper API
- **Base URL**: `https://your-autoscraper-url.railway.app`
- **Swagger Docs**: `https://your-autoscraper-url.railway.app/docs`
- **Health Check**: `https://your-autoscraper-url.railway.app/health`

## Security

### Authentication
- JWT tokens for API access
- Role-based access control (RBAC)
- Rate limiting on all endpoints
- CORS protection

### Database Security
- MongoDB Atlas with authentication
- Connection string encryption
- Input validation and sanitization

## Monitoring

### Health Checks
Both services provide health check endpoints:
- Backend: `/health`
- Autoscraper: `/health`

### Logging
- Structured logging with appropriate levels
- Error tracking and monitoring
- Performance metrics collection

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Verify MongoDB Atlas connection string
   - Check network access settings in MongoDB Atlas
   - Ensure IP whitelist includes Railway IPs

2. **Authentication Errors**
   - Verify JWT secret key consistency
   - Check token expiration settings
   - Validate CORS configuration

3. **Service Communication**
   - Ensure both services are deployed and running
   - Check internal service URLs
   - Verify API key configurations

### Debug Commands
```bash
# Check service health
curl https://your-backend-url.railway.app/health
curl https://your-autoscraper-url.railway.app/health

# Test authentication
curl -X POST https://your-backend-url.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@remotehive.in", "password": "Ranjeet11$"}'
```

## Support

For deployment issues or questions:
1. Check Railway logs for error details
2. Verify environment variable configuration
3. Review MongoDB Atlas connection settings
4. Contact development team for assistance

## License

This project is proprietary software for RemoteHive platform.