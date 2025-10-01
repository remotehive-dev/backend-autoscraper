"""Lead Scoring Service for RemoteHive CRM"""

from typing import Dict, Any
from datetime import datetime, timedelta
from backend.models.mongodb_models import Lead, LeadCategory, LeadSource, LeadScore

class LeadScoringService:
    """Service for calculating and managing lead scores"""
    
    def __init__(self):
        # Scoring weights and rules
        self.category_scores = {
            LeadCategory.EMPLOYER: 85,
            LeadCategory.CORPORATE_SIGNUP: 90,
            LeadCategory.JOB_SEEKER: 60,
            LeadCategory.FREELANCER: 70
        }
        
        self.source_scores = {
            LeadSource.DIRECT_SIGNUP: 80,
            LeadSource.GOOGLE_AUTH: 75,
            LeadSource.LINKEDIN_SIGNUP: 85,
            LeadSource.SSO: 90,
            LeadSource.NORMAL_AUTH: 70,
            LeadSource.REFERRAL: 95,
            LeadSource.SOCIAL_MEDIA: 60,
            LeadSource.EMAIL_CAMPAIGN: 55,
            LeadSource.WEBSITE_FORM: 65,
            LeadSource.API: 70,
            LeadSource.IMPORT: 50,
            LeadSource.OTHER: 50
        }
        
        self.company_size_scores = {
            "1-10": 60,
            "11-50": 70,
            "51-200": 80,
            "201-1000": 85,
            "1000+": 90
        }
        
        self.budget_scores = {
            "< $1,000": 40,
            "$1,000 - $5,000": 60,
            "$5,000 - $10,000": 75,
            "$10,000 - $50,000": 85,
            "$50,000+": 95
        }
        
        self.timeline_scores = {
            "Immediate (< 1 month)": 95,
            "Short-term (1-3 months)": 85,
            "Medium-term (3-6 months)": 70,
            "Long-term (6+ months)": 50,
            "Just researching": 30
        }
    
    async def calculate_score(self, lead: Lead) -> int:
        """Calculate comprehensive lead score based on multiple factors"""
        score = 0
        
        # Base score from category (30% weight)
        category_score = self.category_scores.get(lead.lead_category, 50)
        score += category_score * 0.3
        
        # Source score (20% weight)
        source_score = self.source_scores.get(lead.lead_source, 50)
        score += source_score * 0.2
        
        # Company information (25% weight)
        company_info_score = 0
        if lead.company:
            company_info_score += 20  # Has company name
        if lead.job_title:
            company_info_score += 15  # Has job title
        if lead.industry:
            company_info_score += 10  # Has industry
        if lead.company_size:
            size_score = self.company_size_scores.get(lead.company_size, 50)
            company_info_score += size_score * 0.55  # Company size weight
        else:
            company_info_score += 25  # Default if no size specified
        
        score += min(company_info_score, 100) * 0.25
        
        # Budget and timeline (15% weight)
        budget_timeline_score = 0
        if lead.budget:
            budget_score = self.budget_scores.get(lead.budget, 50)
            budget_timeline_score += budget_score * 0.6
        if lead.timeline:
            timeline_score = self.timeline_scores.get(lead.timeline, 50)
            budget_timeline_score += timeline_score * 0.4
        else:
            budget_timeline_score = 60  # Default score
        
        score += budget_timeline_score * 0.15
        
        # Contact completeness (10% weight)
        contact_score = 0
        if lead.email:
            contact_score += 40  # Email is required
        if lead.phone:
            contact_score += 30  # Phone adds value
        if lead.linkedin_url:
            contact_score += 20  # LinkedIn profile
        if lead.website:
            contact_score += 10  # Company website
        
        score += contact_score * 0.1
        
        # Quality rating bonus (if manually set)
        if lead.quality_rating:
            quality_bonus = (lead.quality_rating - 3) * 5  # -10 to +10 bonus
            score += quality_bonus
        
        # Engagement factors
        engagement_bonus = await self._calculate_engagement_bonus(lead)
        score += engagement_bonus
        
        # Ensure score is within bounds
        return max(0, min(100, int(score)))
    
    async def _calculate_engagement_bonus(self, lead: Lead) -> float:
        """Calculate bonus points based on lead engagement"""
        bonus = 0
        
        # Recent activity bonus
        if lead.last_activity_date:
            days_since_activity = (datetime.utcnow() - lead.last_activity_date).days
            if days_since_activity <= 1:
                bonus += 5
            elif days_since_activity <= 7:
                bonus += 3
            elif days_since_activity <= 30:
                bonus += 1
        
        # Contact frequency bonus
        if lead.last_contact_date:
            days_since_contact = (datetime.utcnow() - lead.last_contact_date).days
            if days_since_contact <= 3:
                bonus += 3
            elif days_since_contact <= 14:
                bonus += 1
        
        # Multiple touchpoints bonus
        touchpoints = 0
        if lead.email:
            touchpoints += 1
        if lead.phone:
            touchpoints += 1
        if lead.linkedin_url:
            touchpoints += 1
        if lead.website:
            touchpoints += 1
        
        if touchpoints >= 3:
            bonus += 2
        elif touchpoints >= 2:
            bonus += 1
        
        return bonus
    
    def get_score_grade(self, score: int) -> LeadScore:
        """Convert numeric score to grade"""
        if score >= 76:
            return LeadScore.BURNING
        elif score >= 51:
            return LeadScore.HOT
        elif score >= 26:
            return LeadScore.WARM
        else:
            return LeadScore.COLD
    
    def get_score_insights(self, lead: Lead, score: int) -> Dict[str, Any]:
        """Get insights about why a lead received a particular score"""
        insights = {
            "score": score,
            "grade": self.get_score_grade(score).value,
            "factors": [],
            "recommendations": []
        }
        
        # Analyze factors
        category_score = self.category_scores.get(lead.lead_category, 50)
        if category_score >= 80:
            insights["factors"].append(f"High-value category: {lead.lead_category.value}")
        elif category_score <= 60:
            insights["factors"].append(f"Lower-value category: {lead.lead_category.value}")
        
        source_score = self.source_scores.get(lead.lead_source, 50)
        if source_score >= 80:
            insights["factors"].append(f"High-quality source: {lead.lead_source.value}")
        elif source_score <= 60:
            insights["factors"].append(f"Lower-quality source: {lead.lead_source.value}")
        
        # Recommendations
        if not lead.phone:
            insights["recommendations"].append("Obtain phone number for better contact options")
        
        if not lead.company_size:
            insights["recommendations"].append("Gather company size information")
        
        if not lead.budget:
            insights["recommendations"].append("Qualify budget requirements")
        
        if not lead.timeline:
            insights["recommendations"].append("Understand project timeline")
        
        if not lead.last_contact_date:
            insights["recommendations"].append("Initiate contact to build relationship")
        elif lead.last_contact_date and (datetime.utcnow() - lead.last_contact_date).days > 14:
            insights["recommendations"].append("Follow up - it's been a while since last contact")
        
        if score < 60:
            insights["recommendations"].append("Consider nurturing campaign to improve qualification")
        elif score >= 80:
            insights["recommendations"].append("High-priority lead - schedule immediate follow-up")
        
        return insights
    
    async def recalculate_all_scores(self) -> Dict[str, int]:
        """Recalculate scores for all active leads"""
        from backend.models.mongodb_models import Lead
        
        leads = await Lead.find(Lead.is_active == True).to_list()
        updated_count = 0
        
        for lead in leads:
            old_score = lead.score
            new_score = await self.calculate_score(lead)
            
            if old_score != new_score:
                lead.score = new_score
                lead.score_grade = self.get_score_grade(new_score)
                await lead.save()
                updated_count += 1
        
        return {
            "total_leads": len(leads),
            "updated_count": updated_count
        }
    
    def get_scoring_rules(self) -> Dict[str, Any]:
        """Get current scoring rules and weights"""
        return {
            "weights": {
                "category": "30%",
                "source": "20%",
                "company_info": "25%",
                "budget_timeline": "15%",
                "contact_completeness": "10%"
            },
            "category_scores": {k.value: v for k, v in self.category_scores.items()},
            "source_scores": {k.value: v for k, v in self.source_scores.items()},
            "company_size_scores": self.company_size_scores,
            "budget_scores": self.budget_scores,
            "timeline_scores": self.timeline_scores,
            "grade_thresholds": {
                "BURNING": "76-100",
                "HOT": "51-75",
                "WARM": "26-50",
                "COLD": "0-25"
            }
        }