from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from beanie import PydanticObjectId
from datetime import datetime, timedelta
import csv
import io
from fastapi.responses import StreamingResponse

from backend.models.mongodb_models import (
    Lead, LeadActivity, LeadTask, LeadNote, User,
    LeadSource, LeadCategory, LeadStatus, LeadScore, 
    ActivityType, Priority
)
from backend.core.security import require_admin
from backend.services.lead_scoring import LeadScoringService
from backend.services.email_service import EmailService

router = APIRouter()
scoring_service = LeadScoringService()
email_service = EmailService()

# Pydantic models for API requests/responses
class LeadCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    company: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=200)
    linkedin_url: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    lead_source: LeadSource
    lead_category: LeadCategory
    status: LeadStatus = LeadStatus.NEW
    priority: Priority = Priority.MEDIUM
    budget_range: Optional[str] = Field(None, max_length=50)
    timeline: Optional[str] = Field(None, max_length=100)
    requirements: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    assigned_to: Optional[PydanticObjectId] = None
    tags: List[str] = Field(default_factory=list)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)
    referrer: Optional[str] = Field(None, max_length=500)
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)

class LeadUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    company: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=200)
    linkedin_url: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    lead_source: Optional[LeadSource] = None
    lead_category: Optional[LeadCategory] = None
    status: Optional[LeadStatus] = None
    priority: Optional[Priority] = None
    budget_range: Optional[str] = Field(None, max_length=50)
    timeline: Optional[str] = Field(None, max_length=100)
    requirements: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    assigned_to: Optional[PydanticObjectId] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None

class LeadResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    website: Optional[str]
    linkedin_url: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
    lead_source: LeadSource
    lead_category: LeadCategory
    status: LeadStatus
    priority: Priority
    lead_score: Optional[LeadScore]
    score_value: Optional[int]
    budget_range: Optional[str]
    timeline: Optional[str]
    requirements: Optional[str]
    notes: Optional[str]
    assigned_to: Optional[PydanticObjectId]
    tags: List[str]
    custom_fields: Dict[str, Any]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    referrer: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    last_contact_date: Optional[datetime]
    next_follow_up_date: Optional[datetime]
    conversion_date: Optional[datetime]
    conversion_value: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True

class LeadActivityCreate(BaseModel):
    lead_id: PydanticObjectId
    activity_type: ActivityType
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    outcome: Optional[str] = Field(None, max_length=1000)
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=200)
    attendees: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class LeadTaskCreate(BaseModel):
    lead_id: PydanticObjectId
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    due_date: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    assigned_to: Optional[PydanticObjectId] = None
    tags: List[str] = Field(default_factory=list)

class LeadNoteCreate(BaseModel):
    lead_id: PydanticObjectId
    content: str = Field(..., min_length=1, max_length=2000)
    is_private: bool = False
    tags: List[str] = Field(default_factory=list)

class BulkLeadUpdate(BaseModel):
    lead_ids: List[PydanticObjectId]
    updates: LeadUpdate

class LeadAssignment(BaseModel):
    lead_ids: List[PydanticObjectId]
    assigned_to: PydanticObjectId
    notify_assignee: bool = True

class LeadExportRequest(BaseModel):
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    fields: Optional[List[str]] = None
    format: str = Field(default="csv", pattern="^(csv|excel)$")

class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

class LeadStatsResponse(BaseModel):
    total: int
    new: int
    contacted: int
    qualified: int
    converted: int
    lost: int
    employer_leads: int
    jobseeker_leads: int
    freelancer_leads: int

@router.get("/", response_model=LeadListResponse)
async def get_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[LeadStatus] = Query(None),
    category: Optional[LeadCategory] = Query(None),
    source: Optional[LeadSource] = Query(None),
    assigned_to: Optional[PydanticObjectId] = Query(None),
    score_min: Optional[int] = Query(None, ge=0, le=100),
    score_max: Optional[int] = Query(None, ge=0, le=100),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(require_admin)
):
    """Get paginated list of leads with advanced filtering and sorting"""
    try:
        # Build query filters
        query_filters = {}
        
        if search:
            query_filters["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"company": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        
        if status:
            query_filters["status"] = status
        if category:
            query_filters["lead_category"] = category
        if source:
            query_filters["lead_source"] = source
        if assigned_to:
            query_filters["assigned_to"] = assigned_to
        
        if score_min is not None:
            query_filters["score_value"] = query_filters.get("score_value", {})
            query_filters["score_value"]["$gte"] = score_min
        if score_max is not None:
            query_filters["score_value"] = query_filters.get("score_value", {})
            query_filters["score_value"]["$lte"] = score_max
        
        if created_after:
            query_filters["created_at"] = query_filters.get("created_at", {})
            query_filters["created_at"]["$gte"] = created_after
        if created_before:
            query_filters["created_at"] = query_filters.get("created_at", {})
            query_filters["created_at"]["$lte"] = created_before
        
        # Get total count
        total = await Lead.find(query_filters).count()
        
        # Build sort criteria
        sort_criteria = [(sort_by, 1 if sort_order == "asc" else -1)]
        
        # Get leads with pagination
        leads = await Lead.find(query_filters).sort(sort_criteria).skip(skip).limit(limit).to_list()
        
        # Convert to response format
        lead_responses = []
        for lead in leads:
            lead_response = LeadResponse(
                id=lead.id,
                first_name=lead.first_name,
                last_name=lead.last_name,
                email=lead.email,
                phone=lead.phone,
                company=lead.company,
                job_title=lead.job_title,
                website=lead.website,
                linkedin_url=lead.linkedin_url,
                address=lead.address,
                city=lead.city,
                state=lead.state,
                country=lead.country,
                postal_code=lead.postal_code,
                lead_source=lead.lead_source,
                lead_category=lead.lead_category,
                status=lead.status,
                priority=lead.priority,
                lead_score=lead.lead_score,
                score_value=lead.score_value,
                budget_range=lead.budget_range,
                timeline=lead.timeline,
                requirements=lead.requirements,
                notes=lead.notes,
                assigned_to=lead.assigned_to,
                tags=lead.tags,
                custom_fields=lead.custom_fields,
                utm_source=lead.utm_source,
                utm_medium=lead.utm_medium,
                utm_campaign=lead.utm_campaign,
                referrer=lead.referrer,
                ip_address=lead.ip_address,
                user_agent=lead.user_agent,
                last_contact_date=lead.last_contact_date,
                next_follow_up_date=lead.next_follow_up_date,
                conversion_date=lead.conversion_date,
                conversion_value=lead.conversion_value,
                created_at=lead.created_at,
                updated_at=lead.updated_at
            )
            lead_responses.append(lead_response)
        
        return LeadListResponse(
            leads=lead_responses,
            total=total,
            page=skip // limit + 1,
            per_page=limit,
            total_pages=(total + limit - 1) // limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch leads: {str(e)}"
        )

@router.get("/stats", response_model=LeadStatsResponse)
async def get_lead_stats(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(require_admin)
):
    """Get comprehensive lead statistics with date filtering"""
    try:
        # Build date filter
        date_filter = {}
        if date_from:
            date_filter["created_at"] = date_filter.get("created_at", {})
            date_filter["created_at"]["$gte"] = date_from
        if date_to:
            date_filter["created_at"] = date_filter.get("created_at", {})
            date_filter["created_at"]["$lte"] = date_to
        
        # Get total leads count
        total_leads = await Lead.find(date_filter).count()
        
        # Get leads by status
        new_leads = await Lead.find({**date_filter, "status": LeadStatus.NEW}).count()
        contacted_leads = await Lead.find({**date_filter, "status": LeadStatus.CONTACTED}).count()
        qualified_leads = await Lead.find({**date_filter, "status": LeadStatus.QUALIFIED}).count()
        converted_leads = await Lead.find({**date_filter, "status": LeadStatus.CONVERTED}).count()
        
        # Get leads by category
        employer_leads = await Lead.find({**date_filter, "lead_category": LeadCategory.EMPLOYER}).count()
        jobseeker_leads = await Lead.find({**date_filter, "lead_category": LeadCategory.JOBSEEKER}).count()
        freelancer_leads = await Lead.find({**date_filter, "lead_category": LeadCategory.FREELANCER}).count()
        
        # Calculate lost leads (assuming any status not in the main categories)
        lost_leads = total_leads - (new_leads + contacted_leads + qualified_leads + converted_leads)
        
        return LeadStatsResponse(
            total=total_leads,
            new=new_leads,
            contacted=contacted_leads,
            qualified=qualified_leads,
            converted=converted_leads,
            lost=max(0, lost_leads),
            employer_leads=employer_leads,
            jobseeker_leads=jobseeker_leads,
            freelancer_leads=freelancer_leads
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch lead statistics: {str(e)}"
        )

@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """Create a new lead with automatic scoring and notifications"""
    try:
        # Check if lead with email already exists
        existing_lead = await Lead.find_one({"email": lead_data.email})
        if existing_lead:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lead with this email already exists"
            )
        
        # Create new lead
        lead = Lead(
            first_name=lead_data.first_name,
            last_name=lead_data.last_name,
            email=lead_data.email,
            phone=lead_data.phone,
            company=lead_data.company,
            job_title=lead_data.job_title,
            website=lead_data.website,
            linkedin_url=lead_data.linkedin_url,
            address=lead_data.address,
            city=lead_data.city,
            state=lead_data.state,
            country=lead_data.country,
            postal_code=lead_data.postal_code,
            lead_source=lead_data.lead_source,
            lead_category=lead_data.lead_category,
            status=lead_data.status,
            priority=lead_data.priority,
            budget_range=lead_data.budget_range,
            timeline=lead_data.timeline,
            requirements=lead_data.requirements,
            notes=lead_data.notes,
            assigned_to=lead_data.assigned_to,
            tags=lead_data.tags,
            custom_fields=lead_data.custom_fields,
            utm_source=lead_data.utm_source,
            utm_medium=lead_data.utm_medium,
            utm_campaign=lead_data.utm_campaign,
            referrer=lead_data.referrer,
            ip_address=lead_data.ip_address,
            user_agent=lead_data.user_agent,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        
        # Calculate lead score
        score_data = await scoring_service.calculate_lead_score(lead)
        lead.score_value = score_data["score"]
        lead.lead_score = score_data["grade"]
        
        await lead.insert()
        
        # Create initial activity
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type=ActivityType.NOTE,
            title="Lead Created",
            description=f"Lead created by {current_user.first_name} {current_user.last_name}",
            created_by=current_user.id
        )
        await activity.insert()
        
        # Send notifications if assigned
        if lead.assigned_to:
            background_tasks.add_task(
                email_service.send_lead_assignment_notification,
                lead.id,
                lead.assigned_to,
                current_user.id
            )
        
        return LeadResponse(
            id=lead.id,
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            company=lead.company,
            job_title=lead.job_title,
            website=lead.website,
            linkedin_url=lead.linkedin_url,
            address=lead.address,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            postal_code=lead.postal_code,
            lead_source=lead.lead_source,
            lead_category=lead.lead_category,
            status=lead.status,
            priority=lead.priority,
            lead_score=lead.lead_score,
            score_value=lead.score_value,
            budget_range=lead.budget_range,
            timeline=lead.timeline,
            requirements=lead.requirements,
            notes=lead.notes,
            assigned_to=lead.assigned_to,
            tags=lead.tags,
            custom_fields=lead.custom_fields,
            utm_source=lead.utm_source,
            utm_medium=lead.utm_medium,
            utm_campaign=lead.utm_campaign,
            referrer=lead.referrer,
            ip_address=lead.ip_address,
            user_agent=lead.user_agent,
            last_contact_date=lead.last_contact_date,
            next_follow_up_date=lead.next_follow_up_date,
            conversion_date=lead.conversion_date,
            conversion_value=lead.conversion_value,
            created_at=lead.created_at,
            updated_at=lead.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create lead: {str(e)}"
        )

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: PydanticObjectId,
    current_user: User = Depends(require_admin)
):
    """Get a specific lead by ID with complete details"""
    try:
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        return LeadResponse(
            id=lead.id,
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            company=lead.company,
            job_title=lead.job_title,
            website=lead.website,
            linkedin_url=lead.linkedin_url,
            address=lead.address,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            postal_code=lead.postal_code,
            lead_source=lead.lead_source,
            lead_category=lead.lead_category,
            status=lead.status,
            priority=lead.priority,
            lead_score=lead.lead_score,
            score_value=lead.score_value,
            budget_range=lead.budget_range,
            timeline=lead.timeline,
            requirements=lead.requirements,
            notes=lead.notes,
            assigned_to=lead.assigned_to,
            tags=lead.tags,
            custom_fields=lead.custom_fields,
            utm_source=lead.utm_source,
            utm_medium=lead.utm_medium,
            utm_campaign=lead.utm_campaign,
            referrer=lead.referrer,
            ip_address=lead.ip_address,
            user_agent=lead.user_agent,
            last_contact_date=lead.last_contact_date,
            next_follow_up_date=lead.next_follow_up_date,
            conversion_date=lead.conversion_date,
            conversion_value=lead.conversion_value,
            created_at=lead.created_at,
            updated_at=lead.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve lead: {str(e)}"
        )

@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: PydanticObjectId,
    lead_data: LeadUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """Update a lead with activity tracking and notifications"""
    try:
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        # Store original values for change tracking
        original_status = lead.status
        original_assigned_to = lead.assigned_to
        
        # Update fields if provided
        update_data = lead_data.dict(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                setattr(lead, field, value)
            
            lead.updated_by = current_user.id
            lead.updated_at = datetime.utcnow()
            
            # Recalculate score if relevant fields changed
            score_affecting_fields = ['lead_category', 'lead_source', 'company', 'budget_range', 'timeline']
            if any(field in update_data for field in score_affecting_fields):
                score_data = await scoring_service.calculate_lead_score(lead)
                lead.score_value = score_data["score"]
                lead.lead_score = score_data["grade"]
            
            await lead.save()
            
            # Create activity for status change
            if 'status' in update_data and original_status != lead.status:
                activity = LeadActivity(
                    lead_id=lead.id,
                    activity_type=ActivityType.STATUS_CHANGE,
                    title="Status Changed",
                    description=f"Status changed from {original_status} to {lead.status}",
                    created_by=current_user.id
                )
                await activity.insert()
                
                # Send status change notification
                if lead.assigned_to:
                    background_tasks.add_task(
                        email_service.send_status_change_notification,
                        lead.id,
                        original_status,
                        lead.status
                    )
            
            # Create activity for assignment change
            if 'assigned_to' in update_data and original_assigned_to != lead.assigned_to:
                activity = LeadActivity(
                    lead_id=lead.id,
                    activity_type=ActivityType.ASSIGNMENT,
                    title="Lead Reassigned",
                    description=f"Lead assigned to new user",
                    created_by=current_user.id
                )
                await activity.insert()
                
                # Send assignment notification
                if lead.assigned_to:
                    background_tasks.add_task(
                        email_service.send_lead_assignment_notification,
                        lead.id,
                        lead.assigned_to,
                        current_user.id
                    )
        
        return LeadResponse(
            id=lead.id,
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            company=lead.company,
            job_title=lead.job_title,
            website=lead.website,
            linkedin_url=lead.linkedin_url,
            address=lead.address,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            postal_code=lead.postal_code,
            lead_source=lead.lead_source,
            lead_category=lead.lead_category,
            status=lead.status,
            priority=lead.priority,
            lead_score=lead.lead_score,
            score_value=lead.score_value,
            budget_range=lead.budget_range,
            timeline=lead.timeline,
            requirements=lead.requirements,
            notes=lead.notes,
            assigned_to=lead.assigned_to,
            tags=lead.tags,
            custom_fields=lead.custom_fields,
            utm_source=lead.utm_source,
            utm_medium=lead.utm_medium,
            utm_campaign=lead.utm_campaign,
            referrer=lead.referrer,
            ip_address=lead.ip_address,
            user_agent=lead.user_agent,
            last_contact_date=lead.last_contact_date,
            next_follow_up_date=lead.next_follow_up_date,
            conversion_date=lead.conversion_date,
            conversion_value=lead.conversion_value,
            created_at=lead.created_at,
            updated_at=lead.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update lead: {str(e)}"
        )

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: PydanticObjectId,
    current_user: User = Depends(require_admin)
):
    """Delete a lead and all associated data"""
    try:
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        # Delete associated activities, tasks, and notes
        await LeadActivity.find({"lead_id": lead_id}).delete()
        await LeadTask.find({"lead_id": lead_id}).delete()
        await LeadNote.find({"lead_id": lead_id}).delete()
        
        # Delete the lead
        await lead.delete()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lead: {str(e)}"
        )

@router.put("/bulk", response_model=dict)
async def bulk_update_leads(
    bulk_update: BulkLeadUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """Bulk update multiple leads with activity tracking"""
    try:
        if not bulk_update.lead_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No lead IDs provided"
            )
        
        updated_count = 0
        
        for lead_id in bulk_update.lead_ids:
            lead = await Lead.get(lead_id)
            if lead:
                # Update fields if provided
                update_fields = bulk_update.updates.dict(exclude_unset=True)
                if update_fields:
                    for field, value in update_fields.items():
                        setattr(lead, field, value)
                    
                    lead.updated_at = datetime.utcnow()
                    lead.updated_by = current_user.id
                    await lead.save()
                    updated_count += 1
        
        # Create bulk activity record
        if updated_count > 0:
            activity = LeadActivity(
                lead_id=None,  # Bulk operation
                activity_type=ActivityType.BULK_UPDATE,
                title="Bulk Update",
                description=f"Bulk updated {updated_count} leads",
                metadata={
                    "updated_fields": list(bulk_update.updates.dict(exclude_unset=True).keys()),
                    "lead_count": updated_count,
                    "lead_ids": [str(id) for id in bulk_update.lead_ids]
                },
                created_by=current_user.id
            )
            await activity.insert()
        
        return {
            "message": f"Successfully updated {updated_count} leads",
            "updated_count": updated_count,
            "total_requested": len(bulk_update.lead_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update leads: {str(e)}"
        )


# Lead Activities Endpoints
@router.post("/{lead_id}/activities", response_model=dict)
async def create_lead_activity(
    lead_id: PydanticObjectId,
    activity_data: LeadActivityCreate,
    current_user: User = Depends(require_admin)
):
    """Create a new activity for a lead"""
    try:
        # Verify lead exists
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type=activity_data.activity_type,
            title=activity_data.title,
            description=activity_data.description,
            details=activity_data.details or {},
            created_by=current_user.id
        )
        
        await activity.insert()
        
        # Update lead's last activity
        lead.last_activity = datetime.utcnow()
        await lead.save()
        
        return {"message": "Activity created successfully", "activity_id": str(activity.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create activity: {str(e)}"
        )


@router.get("/{lead_id}/activities", response_model=List[dict])
async def get_lead_activities(
    lead_id: PydanticObjectId,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin)
):
    """Get activities for a specific lead"""
    try:
        activities = await LeadActivity.find(
            {"lead_id": lead_id}
        ).sort("-created_at").skip(skip).limit(limit).to_list()
        
        activity_list = []
        for activity in activities:
            # Get creator name
            creator = await User.get(activity.created_by) if activity.created_by else None
            creator_name = f"{creator.first_name} {creator.last_name}" if creator else "System"
            
            activity_list.append({
                "id": str(activity.id),
                "activity_type": activity.activity_type,
                "title": activity.title,
                "description": activity.description,
                "details": activity.details,
                "created_at": activity.created_at,
                "created_by": creator_name
            })
        
        return activity_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch activities: {str(e)}"
        )


# Lead Tasks Endpoints
@router.post("/{lead_id}/tasks", response_model=dict)
async def create_lead_task(
    lead_id: PydanticObjectId,
    task_data: LeadTaskCreate,
    current_user: User = Depends(require_admin)
):
    """Create a new task for a lead"""
    try:
        # Verify lead exists
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        task = LeadTask(
            lead_id=lead_id,
            title=task_data.title,
            description=task_data.description,
            due_date=task_data.due_date,
            priority=task_data.priority,
            assigned_to=task_data.assigned_to,
            created_by=current_user.id
        )
        
        await task.insert()
        
        return {"message": "Task created successfully", "task_id": str(task.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/{lead_id}/tasks", response_model=List[dict])
async def get_lead_tasks(
    lead_id: PydanticObjectId,
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_admin)
):
    """Get tasks for a specific lead"""
    try:
        query = {"lead_id": lead_id}
        if status:
            query["status"] = status
            
        tasks = await LeadTask.find(query).sort("-created_at").to_list()
        
        task_list = []
        for task in tasks:
            # Get assigned user name
            assigned_user = await User.get(task.assigned_to) if task.assigned_to else None
            assigned_name = f"{assigned_user.first_name} {assigned_user.last_name}" if assigned_user else None
            
            task_list.append({
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date,
                "assigned_to": assigned_name,
                "created_at": task.created_at,
                "completed_at": task.completed_at
            })
        
        return task_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tasks: {str(e)}"
        )


@router.put("/tasks/{task_id}", response_model=dict)
async def update_task_status(
    task_id: PydanticObjectId,
    status: str = Query(..., regex="^(pending|in_progress|completed|cancelled)$"),
    current_user: User = Depends(require_admin)
):
    """Update task status"""
    try:
        task = await LeadTask.get(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        task.status = status
        if status == "completed":
            task.completed_at = datetime.utcnow()
        
        await task.save()
        
        return {"message": "Task status updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )


# Lead Notes Endpoints
@router.post("/{lead_id}/notes", response_model=dict)
async def create_lead_note(
    lead_id: PydanticObjectId,
    note_data: LeadNoteCreate,
    current_user: User = Depends(require_admin)
):
    """Create a new note for a lead"""
    try:
        # Verify lead exists
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        note = LeadNote(
            lead_id=lead_id,
            content=note_data.content,
            is_private=note_data.is_private,
            created_by=current_user.id
        )
        
        await note.insert()
        
        return {"message": "Note created successfully", "note_id": str(note.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note: {str(e)}"
        )


@router.get("/{lead_id}/notes", response_model=List[dict])
async def get_lead_notes(
    lead_id: PydanticObjectId,
    current_user: User = Depends(require_admin)
):
    """Get notes for a specific lead"""
    try:
        notes = await LeadNote.find(
            {"lead_id": lead_id}
        ).sort("-created_at").to_list()
        
        note_list = []
        for note in notes:
            # Get creator name
            creator = await User.get(note.created_by) if note.created_by else None
            creator_name = f"{creator.first_name} {creator.last_name}" if creator else "System"
            
            note_list.append({
                "id": str(note.id),
                "content": note.content,
                "is_private": note.is_private,
                "created_at": note.created_at,
                "created_by": creator_name
            })
        
        return note_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notes: {str(e)}"
        )


# Lead Assignment Endpoint
@router.post("/assign", response_model=dict)
async def assign_leads(
    assignment: LeadAssignment,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """Assign leads to a team member"""
    try:
        # Verify assignee exists
        assignee = await User.get(assignment.assigned_to)
        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignee not found"
            )
        
        updated_count = 0
        
        for lead_id in assignment.lead_ids:
            lead = await Lead.get(PydanticObjectId(lead_id))
            if lead:
                old_assignee = lead.assigned_to
                lead.assigned_to = assignment.assigned_to
                lead.updated_at = datetime.utcnow()
                lead.updated_by = current_user.id
                await lead.save()
                
                # Create activity
                activity = LeadActivity(
                    lead_id=lead.id,
                    activity_type=ActivityType.ASSIGNMENT,
                    title="Lead Assigned",
                    description=f"Lead assigned to {assignee.first_name} {assignee.last_name}",
                    details={
                        "old_assignee": str(old_assignee) if old_assignee else None,
                        "new_assignee": str(assignment.assigned_to)
                    },
                    created_by=current_user.id
                )
                await activity.insert()
                
                updated_count += 1
                
                # Send notification email
                background_tasks.add_task(
                    email_service.send_lead_assignment_notification,
                    assignee.email,
                    lead,
                    assignee.first_name
                )
        
        return {
            "message": f"Successfully assigned {updated_count} leads",
            "assigned_count": updated_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign leads: {str(e)}"
        )


# Lead Export Endpoint
@router.post("/export", response_class=StreamingResponse)
async def export_leads(
    export_request: LeadExportRequest,
    current_user: User = Depends(require_admin)
):
    """Export leads to CSV format"""
    try:
        # Build query based on filters
        query = {}
        
        if export_request.lead_ids:
            object_ids = [PydanticObjectId(id_str) for id_str in export_request.lead_ids]
            query["_id"] = {"$in": object_ids}
        else:
            # Apply filters if no specific IDs provided
            if export_request.status:
                query["status"] = export_request.status
            if export_request.lead_category:
                query["lead_category"] = export_request.lead_category
            if export_request.date_from:
                query.setdefault("created_at", {})["$gte"] = export_request.date_from
            if export_request.date_to:
                query.setdefault("created_at", {})["$lte"] = export_request.date_to
        
        # Fetch leads
        leads = await Lead.find(query).to_list()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            "ID", "First Name", "Last Name", "Email", "Phone", "Company",
            "Job Title", "Lead Category", "Lead Source", "Status", "Score",
            "Created At", "Updated At", "Last Activity"
        ]
        writer.writerow(headers)
        
        # Write data
        for lead in leads:
            writer.writerow([
                str(lead.id),
                lead.first_name or "",
                lead.last_name or "",
                lead.email or "",
                lead.phone or "",
                lead.company or "",
                lead.job_title or "",
                lead.lead_category or "",
                lead.lead_source or "",
                lead.status or "",
                lead.lead_score or 0,
                lead.created_at.isoformat() if lead.created_at else "",
                lead.updated_at.isoformat() if lead.updated_at else "",
                lead.last_activity.isoformat() if lead.last_activity else ""
            ])
        
        # Prepare response
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_export.csv"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export leads: {str(e)}"
        )


# Lead Analytics Endpoint
@router.get("/analytics", response_model=dict)
async def get_lead_analytics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(require_admin)
):
    """Get comprehensive lead analytics"""
    try:
        # Date filter
        date_filter = {}
        if date_from:
            date_filter["created_at"] = {"$gte": date_from}
        if date_to:
            date_filter.setdefault("created_at", {})["$lte"] = date_to
        
        # Basic stats
        total_leads = await Lead.find(date_filter).count()
        
        # Conversion funnel
        new_leads = await Lead.find({**date_filter, "status": LeadStatus.NEW}).count()
        contacted_leads = await Lead.find({**date_filter, "status": LeadStatus.CONTACTED}).count()
        qualified_leads = await Lead.find({**date_filter, "status": LeadStatus.QUALIFIED}).count()
        converted_leads = await Lead.find({**date_filter, "status": LeadStatus.CONVERTED}).count()
        
        # Lead sources
        source_pipeline = [
            {"$match": date_filter},
            {"$group": {"_id": "$lead_source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        source_stats = await Lead.aggregate(source_pipeline).to_list()
        
        # Lead categories
        category_pipeline = [
            {"$match": date_filter},
            {"$group": {"_id": "$lead_category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        category_stats = await Lead.aggregate(category_pipeline).to_list()
        
        # Score distribution
        score_pipeline = [
            {"$match": date_filter},
            {
                "$bucket": {
                    "groupBy": "$lead_score",
                    "boundaries": [0, 25, 50, 75, 90, 100],
                    "default": "other",
                    "output": {"count": {"$sum": 1}}
                }
            }
        ]
        score_distribution = await Lead.aggregate(score_pipeline).to_list()
        
        # Recent activities
        recent_activities = await LeadActivity.find(
            date_filter
        ).sort("-created_at").limit(10).to_list()
        
        activity_list = []
        for activity in recent_activities:
            lead = await Lead.get(activity.lead_id) if activity.lead_id else None
            creator = await User.get(activity.created_by) if activity.created_by else None
            
            activity_list.append({
                "id": str(activity.id),
                "title": activity.title,
                "description": activity.description,
                "lead_name": f"{lead.first_name} {lead.last_name}" if lead else "Bulk Operation",
                "created_by": f"{creator.first_name} {creator.last_name}" if creator else "System",
                "created_at": activity.created_at
            })
        
        return {
            "summary": {
                "total_leads": total_leads,
                "conversion_rate": round((converted_leads / total_leads * 100) if total_leads > 0 else 0, 2)
            },
            "funnel": {
                "new": new_leads,
                "contacted": contacted_leads,
                "qualified": qualified_leads,
                "converted": converted_leads
            },
            "sources": [{"source": item["_id"], "count": item["count"]} for item in source_stats],
            "categories": [{"category": item["_id"], "count": item["count"]} for item in category_stats],
            "score_distribution": score_distribution,
            "recent_activities": activity_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )