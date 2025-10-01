import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None

from backend.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    """AI service for providing intelligent recommendations and insights"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.available = False
        
        if genai and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                self.available = True
                logger.info("AI Service initialized successfully with Gemini")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI: {e}")
                self.available = False
        else:
            logger.warning("Gemini AI not available - API key missing or library not installed")
    
    async def generate_job_recommendations(self, db: AsyncIOMotorDatabase, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate personalized job recommendations for a user"""
        try:
            # Get user profile and preferences
            user = await db.users.find_one({"_id": user_id})
            if not user or not user.get("job_seeker"):
                return []
            
            job_seeker = user.get("job_seeker")
            
            # Get recent job applications to understand preferences
            recent_applications = await db.job_applications.find(
                {"job_seeker_id": job_seeker.get("_id")}
            ).sort("created_at", -1).limit(5).to_list(length=5)
            
            # Get saved jobs
            saved_jobs = await db.saved_jobs.find(
                {"user_id": user_id}
            ).limit(5).to_list(length=5)
            
            # Get available jobs (excluding already applied)
            applied_job_ids = [app.get("job_post_id") for app in recent_applications]
            saved_job_ids = [saved.get("job_post_id") for saved in saved_jobs]
            excluded_ids = list(set(applied_job_ids + saved_job_ids))
            
            query_filter = {"status": "active"}
            if excluded_ids:
                query_filter["_id"] = {"$nin": excluded_ids}
            
            # Apply basic filtering based on user preferences
            if job_seeker.get("preferred_job_types"):
                try:
                    job_types = json.loads(job_seeker.get("preferred_job_types"))
                    if job_types:
                        query_filter["job_type"] = {"$in": job_types}
                except:
                    pass
            
            if job_seeker.get("remote_work_preference"):
                query_filter["is_remote"] = True
            
            if job_seeker.get("min_salary"):
                query_filter["salary_min"] = {"$gte": job_seeker.get("min_salary")}
            
            available_jobs = await db.job_posts.find(query_filter).sort("created_at", -1).limit(50).to_list(length=50)
            
            if not available_jobs:
                return []
            
            # Use AI to rank and recommend jobs if available
            if self.available:
                return await self._ai_rank_jobs(job_seeker, available_jobs, limit)
            else:
                # Fallback to simple scoring
                return self._simple_rank_jobs(job_seeker, available_jobs, limit)
                
        except Exception as e:
            logger.error(f"Error generating job recommendations: {e}")
            return []
    
    async def _ai_rank_jobs(self, job_seeker: Dict[str, Any], jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Use AI to rank jobs based on user profile"""
        try:
            # Prepare user profile for AI
            user_profile = {
                "current_title": job_seeker.get("current_title"),
                "experience_level": job_seeker.get("experience_level"),
                "years_of_experience": job_seeker.get("years_of_experience"),
                "skills": job_seeker.get("skills"),
                "preferred_job_types": job_seeker.get("preferred_job_types"),
                "preferred_locations": job_seeker.get("preferred_locations"),
                "remote_preference": job_seeker.get("remote_work_preference"),
                "salary_range": f"{job_seeker.get('min_salary')}-{job_seeker.get('max_salary')}" if job_seeker.get("min_salary") else None
            }
            
            # Prepare jobs data for AI
            jobs_data = []
            for job in jobs[:20]:  # Limit to avoid token limits
                jobs_data.append({
                    "id": str(job.get("_id")),
                    "title": job.get("title"),
                    "company": job.get("company_name"),
                    "description": job.get("description", "")[:500],
                    "requirements": job.get("requirements", "")[:300],
                    "job_type": job.get("job_type"),
                    "location": job.get("location"),
                    "is_remote": job.get("is_remote"),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max")
                })
            
            prompt = f"""
            You are an AI career advisor. Based on the user profile and available jobs, rank the jobs by relevance and fit.
            
            User Profile:
            {json.dumps(user_profile, indent=2)}
            
            Available Jobs:
            {json.dumps(jobs_data, indent=2)}
            
            Please rank these jobs from most relevant to least relevant for this user. Consider:
            1. Skills match
            2. Experience level alignment
            3. Job type preferences
            4. Location/remote preferences
            5. Salary expectations
            6. Career progression potential
            
            Return a JSON array with job IDs in order of relevance, along with a brief reason for each recommendation.
            Format: [{"job_id": "id", "score": 0-100, "reason": "explanation"}]
            
            Limit to top {limit} recommendations.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse AI response
            try:
                ai_rankings = json.loads(response.text)
                
                # Convert to final format
                recommendations = []
                for ranking in ai_rankings[:limit]:
                    job = next((j for j in jobs if str(j.get("_id")) == ranking["job_id"]), None)
                    if job:
                        recommendations.append({
                            "id": str(job.get("_id")),
                            "title": job.get("title"),
                            "company_name": job.get("company_name"),
                            "location": job.get("location"),
                            "job_type": job.get("job_type"),
                            "is_remote": job.get("is_remote"),
                            "salary_min": job.get("salary_min"),
                            "salary_max": job.get("salary_max"),
                            "created_at": job.get("created_at").isoformat() if job.get("created_at") else None,
                            "ai_score": ranking.get("score", 0),
                            "ai_reason": ranking.get("reason", "Good match based on your profile")
                        })
                
                return recommendations
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse AI response, falling back to simple ranking")
                return self._simple_rank_jobs(job_seeker, jobs, limit)
                
        except Exception as e:
            logger.error(f"Error in AI job ranking: {e}")
            return self._simple_rank_jobs(job_seeker, jobs, limit)
    
    def _simple_rank_jobs(self, job_seeker: Dict[str, Any], jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Simple fallback ranking algorithm"""
        scored_jobs = []
        
        for job in jobs:
            score = 0
            
            # Score based on job type preference
            if job_seeker.get("preferred_job_types"):
                try:
                    preferred_types = json.loads(job_seeker.get("preferred_job_types"))
                    if job.get("job_type") in preferred_types:
                        score += 30
                except:
                    pass
            
            # Score based on remote preference
            if job_seeker.get("remote_work_preference") and job.get("is_remote"):
                score += 20
            
            # Score based on salary
            if job_seeker.get("min_salary") and job.get("salary_min"):
                if job.get("salary_min") >= job_seeker.get("min_salary"):
                    score += 15
            
            # Score based on recency
            if job.get("created_at"):
                days_old = (datetime.utcnow() - job.get("created_at")).days
                if days_old < 7:
                    score += 10
                elif days_old < 30:
                    score += 5
            
            scored_jobs.append((job, score))
        
        # Sort by score and return top recommendations
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        recommendations = []
        for job, score in scored_jobs[:limit]:
            recommendations.append({
                "id": str(job.get("_id")),
                "title": job.get("title"),
                "company_name": job.get("company_name"),
                "location": job.get("location"),
                "job_type": job.get("job_type"),
                "is_remote": job.get("is_remote"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "created_at": job.get("created_at").isoformat() if job.get("created_at") else None,
                "ai_score": score,
                "ai_reason": "Matched based on your preferences"
            })
        
        return recommendations
    
    async def analyze_profile_strength(self, db: AsyncIOMotorDatabase, user_id: str) -> Dict[str, Any]:
        """Analyze user profile completeness and provide suggestions"""
        try:
            user = await db.users.find_one({"_id": user_id})
            if not user or not user.get("job_seeker"):
                return {"score": 0, "suggestions": ["Profile not found"]}
            
            job_seeker = user.get("job_seeker")
            score = 0
            suggestions = []
            
            # Check profile completeness
            if job_seeker.get("current_title"):
                score += 15
            else:
                suggestions.append("Add your current job title")
            
            if job_seeker.get("skills"):
                score += 20
            else:
                suggestions.append("Add your skills")
            
            if job_seeker.get("resume_url"):
                score += 25
            else:
                suggestions.append("Upload your resume")
            
            if job_seeker.get("experience_level"):
                score += 10
            else:
                suggestions.append("Specify your experience level")
            
            if job_seeker.get("preferred_job_types"):
                score += 10
            else:
                suggestions.append("Set your preferred job types")
            
            if job_seeker.get("preferred_locations"):
                score += 10
            else:
                suggestions.append("Add preferred work locations")
            
            if job_seeker.get("portfolio_url"):
                score += 10
            else:
                suggestions.append("Add a portfolio URL to showcase your work")
            
            # Use AI for advanced suggestions if available
            if self.available and score > 50:
                ai_suggestions = await self._get_ai_profile_suggestions(job_seeker)
                suggestions.extend(ai_suggestions)
            
            return {
                "score": min(score, 100),
                "suggestions": suggestions[:5],  # Limit to top 5 suggestions
                "completeness_percentage": min(score, 100)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing profile strength: {e}")
            return {"score": 0, "suggestions": ["Error analyzing profile"]}
    
    async def _get_ai_profile_suggestions(self, job_seeker: Dict[str, Any]) -> List[str]:
        """Get AI-powered profile improvement suggestions"""
        try:
            profile_data = {
                "current_title": job_seeker.get("current_title"),
                "experience_level": job_seeker.get("experience_level"),
                "skills": job_seeker.get("skills"),
                "years_of_experience": job_seeker.get("years_of_experience")
            }
            
            prompt = f"""
            You are a career advisor. Based on this job seeker profile, provide 3 specific suggestions to improve their profile attractiveness to employers.
            
            Profile:
            {json.dumps(profile_data, indent=2)}
            
            Provide actionable suggestions that would make this profile more appealing. Focus on:
            1. Skills enhancement
            2. Profile presentation
            3. Career positioning
            
            Return as a JSON array of strings, each being a specific suggestion.
            Example: ["Add cloud computing skills to match current market demand", "Include quantifiable achievements in your experience"]
            """
            
            response = self.model.generate_content(prompt)
            suggestions = json.loads(response.text)
            return suggestions if isinstance(suggestions, list) else []
            
        except Exception as e:
            logger.error(f"Error getting AI profile suggestions: {e}")
            return []
    
    async def generate_career_advice(self, db: AsyncIOMotorDatabase, user_id: str, query: str) -> str:
        """Generate personalized career advice based on user query"""
        try:
            if not self.available:
                return "AI career advisor is currently unavailable. Please try again later."
            
            user = await db.users.find_one({"_id": user_id})
            if not user or not user.get("job_seeker"):
                return "Please complete your profile to get personalized advice."
            
            job_seeker = user.get("job_seeker")
            
            # Get recent applications for context
            recent_applications = await db.job_applications.find(
                {"job_seeker_id": user_id}
            ).sort("created_at", -1).limit(3).to_list(length=3)
            
            context = {
                "profile": {
                    "current_title": job_seeker.get("current_title"),
                    "experience_level": job_seeker.get("experience_level"),
                    "years_of_experience": job_seeker.get("years_of_experience"),
                    "skills": job_seeker.get("skills")
                },
                "recent_applications": len(recent_applications),
                "query": query
            }
            
            prompt = f"""
            You are an expert career advisor. Provide personalized, actionable advice based on the user's profile and question.
            
            User Context:
            {json.dumps(context, indent=2)}
            
            Provide a helpful, encouraging response that:
            1. Addresses their specific question
            2. Takes into account their experience level and background
            3. Offers concrete next steps
            4. Is motivational and supportive
            
            Keep the response concise but comprehensive (2-3 paragraphs).
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating career advice: {e}")
            return "I'm having trouble generating advice right now. Please try again later."


# Global AI service instance
ai_service = AIService()