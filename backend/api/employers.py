from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import logging

from backend.database import get_database
from backend.database.services import EmployerService
from backend.models.mongodb_models import Employer, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(tags=["employers"])

# Pydantic models for request/response
class EmployerCreate(BaseModel):
    company_name: str
    company_email: EmailStr
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None

class EmployerResponse(BaseModel):
    id: str
    company_name: str
    company_email: str
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None
    
    class Config:
        from_attributes = True

class EmployersListResponse(BaseModel):
    employers: List[EmployerResponse]
    total: int
    page: int
    limit: int

@router.get("/", response_model=EmployersListResponse)
async def get_employers(
    search: Optional[str] = Query(None, description="Search term for company name, industry, or city"),
    limit: int = Query(50, ge=1, le=100, description="Number of employers to return"),
    skip: int = Query(0, ge=0, description="Number of employers to skip"),
    db = Depends(get_database)
):
    """Get list of employers with optional search and pagination."""
    try:
        employers = await EmployerService.get_employers(
            db=db,
            search=search,
            skip=skip,
            limit=limit
        )
        
        # Get total count for pagination
        filter_dict = {}
        if search:
            filter_dict["$or"] = [
                {"company_name": {"$regex": search, "$options": "i"}},
                {"industry": {"$regex": search, "$options": "i"}},
                {"location": {"$regex": search, "$options": "i"}}
            ]
        
        total = await db.employers.count_documents(filter_dict)
        
        return EmployersListResponse(
            employers=[EmployerResponse.model_validate(emp) for emp in employers],
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error fetching employers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch employers")

@router.post("/", response_model=EmployerResponse, status_code=201)
async def create_employer(
    employer_data: EmployerCreate,
    db = Depends(get_database)
):
    """Create a new employer."""
    try:
        employer = await EmployerService.create_employer(db=db, employer_data=employer_data.model_dump())
        return EmployerResponse.model_validate(employer)
    except Exception as e:
        logger.error(f"Error creating employer: {e}")
        raise HTTPException(status_code=500, detail="Failed to create employer")

@router.get("/{employer_id}", response_model=EmployerResponse)
async def get_employer_by_id(
    employer_id: str,
    db = Depends(get_database)
):
    """Get employer by ID."""
    try:
        employer = await EmployerService.get_employer_by_id(db, employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        return EmployerResponse.model_validate(employer)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching employer {employer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch employer")

@router.put("/{employer_id}", response_model=EmployerResponse)
async def update_employer(
    employer_id: str,
    employer_data: EmployerCreate,
    db = Depends(get_database)
):
    """Update employer information."""
    try:
        employer = await EmployerService.update_employer(
            db=db,
            employer_id=employer_id,
            employer_data=employer_data.model_dump(exclude_unset=True)
        )
        
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        
        return EmployerResponse.model_validate(employer)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating employer {employer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update employer")

@router.delete("/{employer_id}")
async def delete_employer(
    employer_id: str,
    db = Depends(get_database)
):
    """Delete an employer."""
    try:
        success = await EmployerService.delete_employer(db=db, employer_id=employer_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Employer not found")
        
        return {"message": "Employer deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting employer {employer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete employer")