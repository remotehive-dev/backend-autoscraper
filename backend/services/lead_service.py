from typing import Optional, Dict, Any
from datetime import datetime
from beanie import PydanticObjectId
from loguru import logger

from backend.models.mongodb_models import (
    Lead, LeadSource, LeadCategory, LeadStatus, Priority,
    User, UserRole, JobSeeker, Employer, Freelancer
)

class LeadService:
    """Service for managing lead creation and operations"""
    
    @staticmethod
    async def create_lead_from_signup(
        email: str,
        name: str,
        role: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Lead]:
        """
        Create a lead from signup data (used by auth endpoints)
        
        Args:
            email: User email
            name: User full name
            role: User role (employer, job_seeker, freelancer)
            source: Signup source (clerk_auth, direct_signup, etc.)
            metadata: Additional metadata
        
        Returns:
            Created Lead object or None if failed
        """
        try:
            # Check if lead already exists for this email
            existing_lead = await Lead.find_one(Lead.email == email)
            if existing_lead:
                logger.info(f"Lead already exists for email: {email}")
                return existing_lead
            
            # Map string role to LeadCategory
            role_mapping = {
                "employer": LeadCategory.EMPLOYER,
                "job_seeker": LeadCategory.JOB_SEEKER,
                "freelancer": LeadCategory.FREELANCER,
                "admin": LeadCategory.CORPORATE_SIGNUP,
                "super_admin": LeadCategory.CORPORATE_SIGNUP
            }
            category = role_mapping.get(role.lower(), LeadCategory.JOB_SEEKER)
            
            # Map string source to LeadSource
            source_mapping = {
                "clerk_auth": LeadSource.GOOGLE_AUTH,
                "google_auth": LeadSource.GOOGLE_AUTH,
                "linkedin_signup": LeadSource.LINKEDIN_SIGNUP,
                "direct_signup": LeadSource.DIRECT_SIGNUP,
                "normal_auth": LeadSource.NORMAL_AUTH,
                "sso": LeadSource.SSO
            }
            lead_source = source_mapping.get(source.lower(), LeadSource.DIRECT_SIGNUP)
            
            # Calculate initial score
            score = LeadService._calculate_initial_score_from_data(role, source, metadata)
            
            # Prepare metadata
            lead_metadata = metadata or {}
            lead_metadata.update({
                "signup_date": datetime.utcnow().isoformat(),
                "user_role": role,
                "signup_source": source
            })
            
            # Create the lead
            lead = Lead(
                name=name or email.split('@')[0],
                email=email,
                phone=metadata.get("phone") if metadata else None,
                company_name=metadata.get("company_name") if metadata else None,
                source=lead_source,
                category=category,
                status=LeadStatus.NEW,
                priority=Priority.MEDIUM,
                score=score,
                notes=f"Lead created from {source} signup",
                tags=["auto-generated", source, category.value],
                metadata=lead_metadata
            )
            
            await lead.insert()
            logger.info(f"Created lead for email: {email} from source: {source}")
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead from signup: {str(e)}")
            return None
    
    @staticmethod
    async def create_lead_from_user_signup(
        user: User,
        source: LeadSource,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Lead]:
        """
        Create a lead from user signup
        
        Args:
            user: The user who signed up
            source: The source of the signup (google_auth, normal_auth, etc.)
            metadata: Additional metadata (IP, user agent, referrer, etc.)
        
        Returns:
            Created Lead object or None if failed
        """
        try:
            # Check if lead already exists for this email
            existing_lead = await Lead.find_one(Lead.email == user.email)
            if existing_lead:
                logger.info(f"Lead already exists for email: {user.email}")
                return existing_lead
            
            # Determine lead category based on user role
            category = LeadService._get_category_from_user_role(user.role)
            
            # Get additional user information
            company_name = None
            phone = None
            
            # Try to get company name from employer profile
            if user.role == UserRole.EMPLOYER:
                employer = await Employer.find_one(Employer.user_id == user.id)
                if employer:
                    company_name = employer.company_name
                    phone = employer.phone
            
            # Try to get phone from job seeker profile
            elif user.role == UserRole.JOB_SEEKER:
                job_seeker = await JobSeeker.find_one(JobSeeker.user_id == user.id)
                if job_seeker:
                    phone = job_seeker.phone
            
            # Try to get phone from freelancer profile
            elif user.role == UserRole.FREELANCER:
                freelancer = await Freelancer.find_one(Freelancer.user_id == user.id)
                if freelancer:
                    phone = freelancer.phone
            
            # Prepare metadata
            lead_metadata = metadata or {}
            lead_metadata.update({
                "user_id": str(user.id),
                "signup_date": datetime.utcnow().isoformat(),
                "user_role": user.role.value,
                "is_verified": user.is_verified,
                "is_active": user.is_active
            })
            
            # Create the lead
            lead = Lead(
                name=f"{user.first_name} {user.last_name}".strip() or user.email.split('@')[0],
                email=user.email,
                phone=phone,
                company_name=company_name,
                source=source,
                category=category,
                status=LeadStatus.NEW,
                priority=Priority.MEDIUM,
                score=LeadService._calculate_initial_score(user, source),
                notes=f"Lead created from {source.value} signup",
                tags=["auto-generated", source.value, category.value],
                metadata=lead_metadata
            )
            
            await lead.insert()
            logger.info(f"Created lead for user: {user.email} from source: {source.value}")
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead from user signup: {str(e)}")
            return None
    
    @staticmethod
    def _get_category_from_user_role(role: UserRole) -> LeadCategory:
        """Map user role to lead category"""
        role_mapping = {
            UserRole.EMPLOYER: LeadCategory.EMPLOYER,
            UserRole.JOB_SEEKER: LeadCategory.JOBSEEKER,
            UserRole.FREELANCER: LeadCategory.FREELANCER,
            UserRole.ADMIN: LeadCategory.CORPORATE_SIGNUP,
            UserRole.SUPER_ADMIN: LeadCategory.CORPORATE_SIGNUP
        }
        return role_mapping.get(role, LeadCategory.JOBSEEKER)
    
    @staticmethod
    def _calculate_initial_score(user: User, source: LeadSource) -> int:
        """
        Calculate initial lead score based on user data and source
        
        Scoring criteria:
        - Source: Google/LinkedIn (80), SSO (70), Normal (60)
        - Role: Employer (90), Freelancer (70), JobSeeker (50)
        - Verification: +20 if verified
        - Profile completeness: +10 if has name
        """
        score = 0
        
        # Source scoring
        source_scores = {
            LeadSource.GOOGLE_AUTH: 80,
            LeadSource.LINKEDIN_SIGNUP: 80,
            LeadSource.SSO: 70,
            LeadSource.NORMAL_AUTH: 60,
            LeadSource.DIRECT_SIGNUP: 50
        }
        score += source_scores.get(source, 50)
        
        # Role scoring
        role_scores = {
            UserRole.EMPLOYER: 90,
            UserRole.FREELANCER: 70,
            UserRole.JOB_SEEKER: 50,
            UserRole.ADMIN: 30,
            UserRole.SUPER_ADMIN: 30
        }
        score += role_scores.get(user.role, 50)
        
        # Verification bonus
        if user.is_verified:
            score += 20
        
        # Profile completeness bonus
        if user.first_name and user.last_name:
            score += 10
        
        # Ensure score is within reasonable bounds
        return min(max(score, 0), 200)
    
    @staticmethod
    def _calculate_initial_score_from_data(role: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Calculate initial lead score from signup data
        
        Args:
            role: User role string
            source: Signup source string
            metadata: Additional metadata
        
        Returns:
            Calculated score (0-200)
        """
        score = 0
        
        # Source scoring
        source_scores = {
            "clerk_auth": 80,
            "google_auth": 80,
            "linkedin_signup": 80,
            "sso": 70,
            "normal_auth": 60,
            "direct_signup": 50
        }
        score += source_scores.get(source.lower(), 50)
        
        # Role scoring
        role_scores = {
            "employer": 90,
            "freelancer": 70,
            "job_seeker": 50,
            "admin": 30,
            "super_admin": 30
        }
        score += role_scores.get(role.lower(), 50)
        
        # Metadata bonuses
        if metadata:
            # Phone number bonus
            if metadata.get("phone"):
                score += 10
            
            # Company name bonus (for employers)
            if metadata.get("company_name") and role.lower() == "employer":
                score += 15
            
            # Skills bonus (for job seekers/freelancers)
            if metadata.get("skills") and len(metadata.get("skills", [])) > 0:
                score += 10
        
        # Ensure score is within reasonable bounds
        return min(max(score, 0), 200)
    
    @staticmethod
    async def update_lead_activity(lead_id: PydanticObjectId, activity_type: str, description: str):
        """
        Update lead's last activity timestamp and add activity note
        
        Args:
            lead_id: Lead ID
            activity_type: Type of activity (login, profile_update, job_application, etc.)
            description: Activity description
        """
        try:
            lead = await Lead.get(lead_id)
            if lead:
                lead.last_activity = datetime.utcnow()
                
                # Add activity to notes
                activity_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {activity_type}: {description}"
                if lead.notes:
                    lead.notes += f"\n{activity_note}"
                else:
                    lead.notes = activity_note
                
                await lead.save()
                logger.info(f"Updated activity for lead: {lead_id}")
        
        except Exception as e:
            logger.error(f"Error updating lead activity: {str(e)}")
    
    @staticmethod
    async def find_lead_by_email(email: str) -> Optional[Lead]:
        """
        Find lead by email address
        
        Args:
            email: Email address to search for
        
        Returns:
            Lead object if found, None otherwise
        """
        try:
            return await Lead.find_one(Lead.email == email)
        except Exception as e:
            logger.error(f"Error finding lead by email: {str(e)}")
            return None
    
    @staticmethod
    async def update_lead_score(lead_id: PydanticObjectId, score_change: int, reason: str):
        """
        Update lead score with a change and reason
        
        Args:
            lead_id: Lead ID
            score_change: Score change (positive or negative)
            reason: Reason for score change
        """
        try:
            lead = await Lead.get(lead_id)
            if lead:
                old_score = lead.score
                lead.score = max(0, min(200, lead.score + score_change))
                
                # Add score change to notes
                score_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] Score changed from {old_score} to {lead.score} ({score_change:+d}): {reason}"
                if lead.notes:
                    lead.notes += f"\n{score_note}"
                else:
                    lead.notes = score_note
                
                lead.last_activity = datetime.utcnow()
                await lead.save()
                
                logger.info(f"Updated score for lead {lead_id}: {old_score} -> {lead.score} ({reason})")
        
        except Exception as e:
            logger.error(f"Error updating lead score: {str(e)}")
    
    @staticmethod
    async def convert_lead(lead_id: PydanticObjectId, conversion_type: str, notes: str = ""):
        """
        Mark a lead as converted
        
        Args:
            lead_id: Lead ID
            conversion_type: Type of conversion (job_posted, profile_completed, subscription, etc.)
            notes: Additional conversion notes
        """
        try:
            lead = await Lead.get(lead_id)
            if lead:
                lead.status = LeadStatus.CONVERTED
                lead.last_activity = datetime.utcnow()
                
                # Add conversion note
                conversion_note = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] CONVERTED - {conversion_type}"
                if notes:
                    conversion_note += f": {notes}"
                
                if lead.notes:
                    lead.notes += f"\n{conversion_note}"
                else:
                    lead.notes = conversion_note
                
                # Add conversion metadata
                if not lead.metadata:
                    lead.metadata = {}
                lead.metadata["conversion_date"] = datetime.utcnow().isoformat()
                lead.metadata["conversion_type"] = conversion_type
                
                await lead.save()
                logger.info(f"Converted lead {lead_id}: {conversion_type}")
        
        except Exception as e:
            logger.error(f"Error converting lead: {str(e)}")