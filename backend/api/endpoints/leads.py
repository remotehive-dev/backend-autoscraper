"""Lead Management API endpoints for RemoteHive CRM"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from beanie import PydanticObjectId
from beanie.operators import In, RegEx, GTE, LTE
import csv
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from backend.models.mongodb_models import (
    Lead, LeadActivity, LeadTask, LeadNote, User,
    LeadSource, LeadCategory, LeadStatus, LeadScore, ActivityType, Priority
)
from backend.core.auth import get_admin
from backend.services.lead_scoring import LeadScoringService
from backend.services.email_service import EmailService

router = APIRouter(prefix="/leads", tags=["leads"])

# Pydantic models for requests/responses
class LeadCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    lead_source: LeadSource
    lead_category: LeadCategory
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = []
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer_url: Optional[str] = None
    landing_page: Optional[str] = None

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    lead_source: Optional[LeadSource] = None
    lead_category: Optional[LeadCategory] = None
    status: Optional[LeadStatus] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    quality_rating: Optional[int] = None
    next_follow_up_date: Optional[datetime] = None

class LeadAssignment(BaseModel):
    assigned_to: PydanticObjectId
    notes: Optional[str] = None

class ActivityCreate(BaseModel):
    activity_type: ActivityType
    title: str
    description: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    call_duration: Optional[int] = None
    call_outcome: Optional[str] = None
    meeting_location: Optional[str] = None
    meeting_attendees: List[str] = []
    priority: Priority = Priority.MEDIUM
    attachments: List[str] = []

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: PydanticObjectId
    due_date: datetime
    reminder_date: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    category: Optional[str] = None
    notes: Optional[str] = None

class NoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    is_private: bool = False
    category: Optional[str] = None
    tags: List[str] = []

class BulkAction(BaseModel):
    lead_ids: List[PydanticObjectId]
    action: str  # "update_status", "assign", "add_tag", "remove_tag"
    value: Any  # Status, user_id, tag, etc.

class LeadStats(BaseModel):
    total_leads: int
    new_leads: int
    contacted_leads: int
    qualified_leads: int
    converted_leads: int
    closed_lost_leads: int
    conversion_rate: float
    by_source: Dict[str, int]
    by_category: Dict[str, int]
    by_status: Dict[str, int]
    avg_score: float
    leads_this_month: int
    leads_last_month: int
    growth_rate: float

# Lead CRUD Operations
@router.post("/", response_model=Dict[str, Any])
async def create_lead(
    lead_data: LeadCreate,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Create a new lead"""
    try:
        # Check for duplicate email
        existing_lead = await Lead.find_one(Lead.email == lead_data.email, Lead.is_active == True)
        if existing_lead:
            raise HTTPException(status_code=400, detail="Lead with this email already exists")
        
        # Create lead
        lead = Lead(**lead_data.dict())
        
        # Calculate initial lead score
        scoring_service = LeadScoringService()
        lead.score = await scoring_service.calculate_score(lead)
        lead.score_grade = scoring_service.get_score_grade(lead.score)
        
        await lead.insert()
        
        # Create initial activity
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type=ActivityType.NOTE,
            title="Lead Created",
            description=f"Lead created from {lead_data.lead_source.value}",
            performed_by=current_user['id'],
            is_automated=True
        )
        await activity.insert()
        
        return {
            "success": True,
            "message": "Lead created successfully",
            "lead_id": str(lead.id),
            "score": lead.score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=Dict[str, Any])
async def get_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[LeadStatus] = None,
    category: Optional[LeadCategory] = None,
    source: Optional[LeadSource] = None,
    assigned_to: Optional[PydanticObjectId] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Get leads with filtering, sorting, and pagination"""
    try:
        # Build query
        query = {"is_active": True}
        
        if status:
            query["status"] = status
        if category:
            query["lead_category"] = category
        if source:
            query["lead_source"] = source
        if assigned_to:
            query["assigned_to"] = assigned_to
        if min_score is not None:
            query["score"] = {"$gte": min_score}
        if max_score is not None:
            if "score" in query:
                query["score"]["$lte"] = max_score
            else:
                query["score"] = {"$lte": max_score}
        
        # Search functionality
        if search:
            search_query = {
                "$or": [
                    {"first_name": RegEx(search, "i")},
                    {"last_name": RegEx(search, "i")},
                    {"email": RegEx(search, "i")},
                    {"company": RegEx(search, "i")},
                    {"phone": RegEx(search, "i")}
                ]
            }
            query = {"$and": [query, search_query]}
        
        # Sort configuration
        sort_direction = -1 if sort_order == "desc" else 1
        sort_config = [(sort_by, sort_direction)]
        
        # Get total count
        total = await Lead.find(query).count()
        
        # Get leads with pagination
        skip = (page - 1) * limit
        leads = await Lead.find(query).sort(sort_config).skip(skip).limit(limit).to_list()
        
        return {
            "leads": [lead.dict() for lead in leads],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{lead_id}", response_model=Dict[str, Any])
async def get_lead(
    lead_id: PydanticObjectId,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Get a specific lead with activities, tasks, and notes"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get related data
        activities = await LeadActivity.find(
            LeadActivity.lead_id == lead_id
        ).sort([("performed_at", -1)]).limit(50).to_list()
        
        tasks = await LeadTask.find(
            LeadTask.lead_id == lead_id,
            LeadTask.is_completed == False
        ).sort([("due_date", 1)]).to_list()
        
        notes = await LeadNote.find(
            LeadNote.lead_id == lead_id
        ).sort([("created_at", -1)]).limit(20).to_list()
        
        # Get assigned user info
        assigned_user = None
        if lead.assigned_to:
            assigned_user = await User.get(lead.assigned_to)
        
        return {
            "lead": lead.dict(),
            "activities": [activity.dict() for activity in activities],
            "tasks": [task.dict() for task in tasks],
            "notes": [note.dict() for note in notes],
            "assigned_user": assigned_user.dict() if assigned_user else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{lead_id}", response_model=Dict[str, Any])
async def update_lead(
    lead_id: PydanticObjectId,
    lead_data: LeadUpdate,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Update a lead"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Store old values for activity tracking
        old_status = lead.status
        old_assigned_to = lead.assigned_to
        
        # Update lead
        update_data = {k: v for k, v in lead_data.dict().items() if v is not None}
        for key, value in update_data.items():
            setattr(lead, key, value)
        
        lead.updated_at = datetime.utcnow()
        
        # Recalculate score if relevant fields changed
        scoring_fields = ['lead_category', 'company_size', 'budget', 'industry', 'quality_rating']
        if any(field in update_data for field in scoring_fields):
            scoring_service = LeadScoringService()
            lead.score = await scoring_service.calculate_score(lead)
            lead.score_grade = scoring_service.get_score_grade(lead.score)
        
        await lead.save()
        
        # Create activities for significant changes
        if 'status' in update_data and old_status != lead.status:
            activity = LeadActivity(
                lead_id=lead.id,
                activity_type=ActivityType.STATUS_CHANGE,
                title="Status Changed",
                description=f"Status changed from {old_status.value} to {lead.status.value}",
                performed_by=current_user['id']
            )
            await activity.insert()
        
        if 'assigned_to' in update_data and old_assigned_to != lead.assigned_to:
            assigned_user = await User.get(lead.assigned_to) if lead.assigned_to else None
            activity = LeadActivity(
                lead_id=lead.id,
                activity_type=ActivityType.ASSIGNMENT,
                title="Lead Assigned",
                description=f"Lead assigned to {assigned_user.display_name if assigned_user else 'Unassigned'}",
                performed_by=current_user['id']
            )
            await activity.insert()
        
        return {
            "success": True,
            "message": "Lead updated successfully",
            "lead": lead.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{lead_id}", response_model=Dict[str, Any])
async def delete_lead(
    lead_id: PydanticObjectId,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Soft delete a lead"""
    try:
        lead = await Lead.get(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead.is_active = False
        lead.updated_at = datetime.utcnow()
        await lead.save()
        
        # Create activity
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type=ActivityType.NOTE,
            title="Lead Deleted",
            description="Lead marked as inactive",
            performed_by=current_user['id']
        )
        await activity.insert()
        
        return {"success": True, "message": "Lead deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Lead Assignment
@router.post("/{lead_id}/assign", response_model=Dict[str, Any])
async def assign_lead(
    lead_id: PydanticObjectId,
    assignment: LeadAssignment,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Assign a lead to a user"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Verify assigned user exists
        assigned_user = await User.get(assignment.assigned_to)
        if not assigned_user:
            raise HTTPException(status_code=404, detail="Assigned user not found")
        
        # Update lead
        lead.assigned_to = assignment.assigned_to
        lead.assigned_at = datetime.utcnow()
        lead.assigned_by = current_user['id']
        lead.updated_at = datetime.utcnow()
        await lead.save()
        
        # Create activity
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type=ActivityType.ASSIGNMENT,
            title="Lead Assigned",
            description=f"Lead assigned to {assigned_user.display_name}" + 
                       (f"\nNotes: {assignment.notes}" if assignment.notes else ""),
            performed_by=current_user.id
        )
        await activity.insert()
        
        return {
            "success": True,
            "message": f"Lead assigned to {assigned_user.display_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Lead Activities
@router.post("/{lead_id}/activities", response_model=Dict[str, Any])
async def create_activity(
    lead_id: PydanticObjectId,
    activity_data: ActivityCreate,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Create a new activity for a lead"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        activity = LeadActivity(
            lead_id=lead_id,
            performed_by=current_user['id'],
            **activity_data.dict()
        )
        await activity.insert()
        
        # Update lead's last activity date
        lead.last_activity_date = datetime.utcnow()
        if activity_data.activity_type in [ActivityType.EMAIL, ActivityType.CALL, ActivityType.MEETING]:
            lead.last_contact_date = datetime.utcnow()
        await lead.save()
        
        return {
            "success": True,
            "message": "Activity created successfully",
            "activity_id": str(activity.id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Lead Tasks
@router.post("/{lead_id}/tasks", response_model=Dict[str, Any])
async def create_task(
    lead_id: PydanticObjectId,
    task_data: TaskCreate,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Create a new task for a lead"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        task = LeadTask(
            lead_id=lead_id,
            assigned_by=current_user['id'],
            **task_data.dict()
        )
        await task.insert()
        
        # Create activity
        assigned_user = await User.get(task_data.assigned_to)
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type=ActivityType.TASK,
            title="Task Created",
            description=f"Task '{task_data.title}' assigned to {assigned_user.display_name if assigned_user else 'Unknown'}",
            performed_by=current_user.id
        )
        await activity.insert()
        
        return {
            "success": True,
            "message": "Task created successfully",
            "task_id": str(task.id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Lead Notes
@router.post("/{lead_id}/notes", response_model=Dict[str, Any])
async def create_note(
    lead_id: PydanticObjectId,
    note_data: NoteCreate,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Create a new note for a lead"""
    try:
        lead = await Lead.get(lead_id)
        if not lead or not lead.is_active:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        note = LeadNote(
            lead_id=lead_id,
            created_by=current_user['id'],
            **note_data.dict()
        )
        await note.insert()
        
        return {
            "success": True,
            "message": "Note created successfully",
            "note_id": str(note.id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Bulk Operations
@router.post("/bulk-action", response_model=Dict[str, Any])
async def bulk_action(
    action_data: BulkAction,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Perform bulk actions on leads"""
    try:
        leads = await Lead.find(In(Lead.id, action_data.lead_ids)).to_list()
        if not leads:
            raise HTTPException(status_code=404, detail="No leads found")
        
        updated_count = 0
        
        for lead in leads:
            if action_data.action == "update_status":
                old_status = lead.status
                lead.status = LeadStatus(action_data.value)
                lead.updated_at = datetime.utcnow()
                await lead.save()
                
                # Create activity
                activity = LeadActivity(
                    lead_id=lead.id,
                    activity_type=ActivityType.STATUS_CHANGE,
                    title="Bulk Status Update",
                    description=f"Status changed from {old_status.value} to {lead.status.value}",
                    performed_by=current_user['id']
                )
                await activity.insert()
                updated_count += 1
                
            elif action_data.action == "assign":
                assigned_user = await User.get(PydanticObjectId(action_data.value))
                if assigned_user:
                    lead.assigned_to = assigned_user.id
                    lead.assigned_at = datetime.utcnow()
                    lead.assigned_by = current_user['id']
                    lead.updated_at = datetime.utcnow()
                    await lead.save()
                    
                    # Create activity
                    activity = LeadActivity(
                        lead_id=lead.id,
                        activity_type=ActivityType.ASSIGNMENT,
                        title="Bulk Assignment",
                        description=f"Lead assigned to {assigned_user.display_name}",
                        performed_by=current_user['id']
                    )
                    await activity.insert()
                    updated_count += 1
        
        return {
            "success": True,
            "message": f"Bulk action completed. {updated_count} leads updated."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Lead Statistics
@router.get("/stats/overview", response_model=LeadStats)
async def get_lead_stats(
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Get comprehensive lead statistics"""
    try:
        # Basic counts
        total_leads = await Lead.find(Lead.is_active == True).count()
        new_leads = await Lead.find(Lead.status == LeadStatus.NEW, Lead.is_active == True).count()
        contacted_leads = await Lead.find(Lead.status == LeadStatus.CONTACTED, Lead.is_active == True).count()
        qualified_leads = await Lead.find(Lead.status == LeadStatus.QUALIFIED, Lead.is_active == True).count()
        converted_leads = await Lead.find(Lead.status.in_([LeadStatus.CONVERTED, LeadStatus.CLOSED_WON]), Lead.is_active == True).count()
        closed_lost_leads = await Lead.find(Lead.status == LeadStatus.CLOSED_LOST, Lead.is_active == True).count()
        
        # Conversion rate
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # By source
        by_source = {}
        for source in LeadSource:
            count = await Lead.find(Lead.lead_source == source, Lead.is_active == True).count()
            if count > 0:
                by_source[source.value] = count
        
        # By category
        by_category = {}
        for category in LeadCategory:
            count = await Lead.find(Lead.lead_category == category, Lead.is_active == True).count()
            if count > 0:
                by_category[category.value] = count
        
        # By status
        by_status = {}
        for status in LeadStatus:
            count = await Lead.find(Lead.status == status, Lead.is_active == True).count()
            if count > 0:
                by_status[status.value] = count
        
        # Average score
        leads_with_scores = await Lead.find(Lead.is_active == True, Lead.score > 0).to_list()
        avg_score = sum(lead.score for lead in leads_with_scores) / len(leads_with_scores) if leads_with_scores else 0
        
        # Monthly stats
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        
        leads_this_month = await Lead.find(
            Lead.created_at >= start_of_month,
            Lead.is_active == True
        ).count()
        
        leads_last_month = await Lead.find(
            Lead.created_at >= start_of_last_month,
            Lead.created_at < start_of_month,
            Lead.is_active == True
        ).count()
        
        growth_rate = ((leads_this_month - leads_last_month) / leads_last_month * 100) if leads_last_month > 0 else 0
        
        return LeadStats(
            total_leads=total_leads,
            new_leads=new_leads,
            contacted_leads=contacted_leads,
            qualified_leads=qualified_leads,
            converted_leads=converted_leads,
            closed_lost_leads=closed_lost_leads,
            conversion_rate=round(conversion_rate, 2),
            by_source=by_source,
            by_category=by_category,
            by_status=by_status,
            avg_score=round(avg_score, 1),
            leads_this_month=leads_this_month,
            leads_last_month=leads_last_month,
            growth_rate=round(growth_rate, 2)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Export functionality
@router.get("/export/csv")
async def export_leads_csv(
    status: Optional[LeadStatus] = None,
    category: Optional[LeadCategory] = None,
    source: Optional[LeadSource] = None,
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Export leads to CSV"""
    try:
        # Build query
        query = {"is_active": True}
        if status:
            query["status"] = status
        if category:
            query["lead_category"] = category
        if source:
            query["lead_source"] = source
        
        leads = await Lead.find(query).to_list()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        headers = [
            'ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Company', 'Job Title',
            'Status', 'Category', 'Source', 'Score', 'Created At', 'Last Contact',
            'Assigned To', 'Industry', 'Company Size', 'Budget', 'Timeline'
        ]
        writer.writerow(headers)
        
        # Data
        for lead in leads:
            assigned_user = None
            if lead.assigned_to:
                assigned_user = await User.get(lead.assigned_to)
            
            row = [
                str(lead.id),
                lead.first_name,
                lead.last_name,
                lead.email,
                lead.phone or '',
                lead.company or '',
                lead.job_title or '',
                lead.status.value,
                lead.lead_category.value,
                lead.lead_source.value,
                lead.score,
                lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                lead.last_contact_date.strftime('%Y-%m-%d %H:%M:%S') if lead.last_contact_date else '',
                assigned_user.display_name if assigned_user else '',
                lead.industry or '',
                lead.company_size or '',
                lead.budget or '',
                lead.timeline or ''
            ]
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get employees for assignment
@router.get("/employees", response_model=List[Dict[str, Any]])
async def get_employees(
    current_user: Dict[str, Any] = Depends(get_admin)
):
    """Get list of employees for lead assignment"""
    try:
        employees = await User.find(
            User.role.in_(["admin", "super_admin"]),
            User.is_active == True
        ).to_list()
        
        return [
            {
                "_id": str(employee.id),
                "name": employee.display_name,
                "email": employee.email,
                "role": employee.role.value
            }
            for employee in employees
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))