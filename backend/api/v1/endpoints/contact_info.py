from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from beanie import PydanticObjectId

from backend.database.mongodb_models import ContactInformation
from backend.core.auth import get_admin

router = APIRouter()

# Pydantic models for request/response
class ContactInfoBase(BaseModel):
    category: str
    label: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    office_hours: Optional[str] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_primary: bool = False
    display_order: int = 0

class ContactInfoCreate(ContactInfoBase):
    pass

class ContactInfoUpdate(ContactInfoBase):
    pass

class ContactInfoResponse(ContactInfoBase):
    id: PydanticObjectId
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ContactInfoListResponse(BaseModel):
    contact_infos: List[ContactInfoResponse]
    total: int

@router.get("/contact-info", response_model=ContactInfoListResponse)
async def get_contact_infos(
    current_user = Depends(get_admin),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get all contact information entries.
    Admin only endpoint.
    """
    try:
        # Build query filters
        query_filter = {}
        if category:
            query_filter["category"] = category
        if is_active is not None:
            query_filter["is_active"] = is_active
            
        # Get total count
        total = await ContactInformation.find(query_filter).count()
        
        # Get paginated results
        contact_infos = await ContactInformation.find(query_filter).sort(
            [("display_order", 1), ("-created_at", 1)]
        ).skip(skip).limit(limit).to_list()
        
        # Convert to response format
        contact_info_list = []
        for contact_info in contact_infos:
            contact_info_dict = contact_info.dict()
            contact_info_dict["id"] = contact_info.id
            contact_info_list.append(ContactInfoResponse(**contact_info_dict))
        
        return ContactInfoListResponse(
            contact_infos=contact_info_list,
            total=total
        )
        
    except Exception as e:
        print(f"Error fetching contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contact information"
        )

@router.get("/contact-info/public", response_model=ContactInfoListResponse)
async def get_public_contact_infos(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None
):
    """
    Get active contact information for public display.
    No authentication required.
    """
    try:
        # Build query filter for active contact info only
        query_filter = {"is_active": True}
        if category:
            query_filter["category"] = category
            
        # Get total count
        total = await ContactInformation.find(query_filter).count()
        
        # Get paginated results
        contact_infos = await ContactInformation.find(query_filter).sort(
            [("display_order", 1), ("-created_at", 1)]
        ).skip(skip).limit(limit).to_list()
        
        # Convert to response format
        contact_info_list = []
        for contact_info in contact_infos:
            contact_info_dict = contact_info.dict()
            contact_info_dict["id"] = contact_info.id
            contact_info_list.append(ContactInfoResponse(**contact_info_dict))
        
        return ContactInfoListResponse(
            contact_infos=contact_info_list,
            total=total
        )
        
    except Exception as e:
        print(f"Error fetching public contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contact information"
        )

@router.get("/contact-info/{contact_info_id}", response_model=ContactInfoResponse)
async def get_contact_info(
    contact_info_id: PydanticObjectId,
    current_user = Depends(get_admin)
):
    """
    Get a specific contact information entry by ID.
    Admin only endpoint.
    """
    try:
        contact_info = await ContactInformation.get(contact_info_id)
        
        if not contact_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact information not found"
            )
        
        contact_info_dict = contact_info.dict()
        contact_info_dict["id"] = contact_info.id
        return ContactInfoResponse(**contact_info_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contact information"
        )

@router.post("/contact-info", response_model=ContactInfoResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_info(
    contact_info: ContactInfoCreate,
    current_user = Depends(get_admin)
):
    """
    Create a new contact information entry.
    Admin only endpoint.
    """
    try:
        # Handle primary contact logic
        if contact_info.is_primary:
            # Set all other contacts in the same category to non-primary
            await ContactInformation.find(
                ContactInformation.category == contact_info.category
            ).update({"$set": {"is_primary": False}})
        
        # Create new contact info
        contact_data = contact_info.dict()
        new_contact = ContactInformation(**contact_data)
        await new_contact.insert()
        
        contact_info_dict = new_contact.dict()
        contact_info_dict["id"] = new_contact.id
        return ContactInfoResponse(**contact_info_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contact information"
        )

@router.put("/contact-info/{contact_info_id}", response_model=ContactInfoResponse)
async def update_contact_info(
    contact_info_id: PydanticObjectId,
    contact_info: ContactInfoUpdate,
    current_user = Depends(get_admin)
):
    """
    Update a contact information entry.
    Admin only endpoint.
    """
    try:
        # Check if contact info exists
        existing_contact = await ContactInformation.get(contact_info_id)
        
        if not existing_contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact information not found"
            )
        
        # Handle primary contact logic
        if contact_info.is_primary:
            # Set all other contacts in the same category to non-primary (excluding current one)
            await ContactInformation.find(
                ContactInformation.category == contact_info.category,
                ContactInformation.id != contact_info_id
            ).update({"$set": {"is_primary": False}})
        
        # Update contact info
        update_data = contact_info.dict(exclude_unset=True)
        await existing_contact.update({"$set": update_data})
        
        # Fetch updated contact
        updated_contact = await ContactInformation.get(contact_info_id)
        
        contact_info_dict = updated_contact.dict()
        contact_info_dict["id"] = updated_contact.id
        return ContactInfoResponse(**contact_info_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update contact information"
        )

@router.delete("/contact-info/{contact_info_id}")
async def delete_contact_info(
    contact_info_id: PydanticObjectId,
    current_user = Depends(get_admin)
):
    """
    Delete a contact information entry.
    Admin only endpoint.
    """
    try:
        # Check if contact info exists
        existing_contact = await ContactInformation.get(contact_info_id)
        
        if not existing_contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact information not found"
            )
        
        # Delete contact info
        await existing_contact.delete()
        
        return {"message": "Contact information deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting contact information: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact information"
        )