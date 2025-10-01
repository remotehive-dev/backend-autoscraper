from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.database import get_db
from backend.database.services import EmployerService
from backend.models.mongodb_models import Employer

router = APIRouter()

@router.get("/")
async def get_companies(
    featured: Optional[bool] = Query(None, description="Filter for featured companies"),
    trending: Optional[bool] = Query(None, description="Filter for trending companies"),
    limit: int = Query(10, description="Number of companies to return"),
    skip: int = Query(0, description="Number of companies to skip"),
    search: Optional[str] = Query(None, description="Search companies by name"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get companies (public endpoint)"""
    try:
        # Get employers from database
        employer_service = EmployerService()
        employers = await employer_service.get_employers(
            db,
            search=search,
            skip=skip,
            limit=limit
        )
        
        # Convert employers to company format
        companies = []
        for employer in employers:
            company = {
                "id": str(employer.id),
                "name": employer.company_name,
                "description": employer.company_description,
                "website": employer.company_website,
                "logo_url": employer.company_logo,
                "location": employer.location,
                "industry": employer.industry,
                "size": employer.company_size,
                "created_at": employer.created_at.isoformat() if employer.created_at else None
            }
            companies.append(company)
        
        # Apply featured/trending filters (for now, return all companies)
        # In a real implementation, you would have featured/trending flags in the database
        if featured or trending:
            # For demo purposes, return a subset of companies
            companies = companies[:limit]
        
        return companies
        
    except Exception as e:
        logger.error(f"Error fetching companies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch companies"
        )

@router.get("/{company_id}")
async def get_company_by_id(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get a specific company by ID"""
    try:
        employer_service = EmployerService()
        employer = await employer_service.get_employer_by_id(db, company_id)
        
        if not employer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        company = {
            "id": str(employer.id),
            "name": employer.company_name,
            "description": employer.company_description,
            "website": employer.company_website,
            "logo_url": employer.company_logo,
            "location": employer.location,
            "industry": employer.industry,
            "size": employer.company_size,
            "created_at": employer.created_at.isoformat() if employer.created_at else None
        }
        
        return company
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid company ID"
        )
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch company"
        )

@router.post("/")
async def create_company(
    company_data: Dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create a new company (public endpoint)"""
    try:
        # Create employer data dictionary
        employer_data = {
            "user_id": "system",  # Use system user ID
            "company_name": company_data.get("company_name") or company_data.get("name"),
            "company_email": company_data.get("email"),
            "company_website": company_data.get("website"),
            "company_description": company_data.get("description"),
            "industry": company_data.get("industry"),
            "company_size": company_data.get("company_size"),
            "location": company_data.get("location"),
            "is_verified": False  # New companies start unverified
        }
        
        # Create employer record using service
        employer_service = EmployerService()
        employer = await employer_service.create_employer(db, employer_data, "system")
        
        # Return in company format
        company = {
            "id": str(employer.id),
            "name": employer.company_name,
            "description": employer.company_description,
            "website": employer.company_website,
            "logo_url": employer.company_logo,
            "location": employer.location,
            "industry": employer.industry,
            "size": employer.company_size,
            "created_at": employer.created_at.isoformat() if employer.created_at else None
        }
        
        return company
        
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )