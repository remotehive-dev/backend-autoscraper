import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import asyncio
import re
from dataclasses import dataclass

import google.generativeai as genai
# from sqlalchemy.orm import Session  # Using MongoDB instead

try:
    from core.config import settings
    from database.models import MLParsingConfig, ScraperConfig, AnalyticsMetrics
    from database.database import get_db_session
except ImportError:
    # Fallback for testing or standalone usage
    class MockSettings:
        GEMINI_API_KEY = None
    settings = MockSettings()
    
    # Mock database classes for testing
    class MLParsingConfig:
        def __init__(self):
            self.gemini_api_enabled = True
            self.field_mapping = '{}'
    
    class ScraperConfig:
        pass
    
    class AnalyticsMetrics:
        pass
    
    def get_db_session():
        return [None]

logger = logging.getLogger(__name__)

@dataclass
class ParsedJobData:
    """Structured representation of parsed job data"""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    description: Optional[str] = None
    requirements: List[str] = None
    benefits: List[str] = None
    is_remote: Optional[bool] = None
    posted_date: Optional[datetime] = None
    application_url: Optional[str] = None
    confidence_score: float = 0.0
    parsing_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.requirements is None:
            self.requirements = []
        if self.benefits is None:
            self.benefits = []
        if self.parsing_metadata is None:
            self.parsing_metadata = {}

class MLParsingService:
    """Service for ML-powered job data parsing using Gemini API"""
    
    def __init__(self):
        self.model = None
        self.available = False
        self._initialize_gemini()
        
    def _initialize_gemini(self):
        """Initialize Gemini API client"""
        try:
            if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.available = True
                logger.info("Gemini API initialized successfully for ML parsing")
            else:
                logger.warning("Gemini API key not found. ML parsing will use fallback methods.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            self.available = False
    
    async def parse_job_data(self, 
                           raw_html: str, 
                           scraper_config_id: str,
                           confidence_threshold: float = 0.7) -> ParsedJobData:
        """Parse job data from raw HTML using ML"""
        try:
            # Get ML parsing configuration
            db = next(get_db_session())
            ml_config = db.query(MLParsingConfig).filter(
                MLParsingConfig.scraper_config_id == scraper_config_id
            ).first()
            
            if not ml_config or not ml_config.gemini_api_enabled:
                return await self._fallback_parse(raw_html)
            
            if not self.available:
                logger.warning("Gemini API not available, using fallback parsing")
                return await self._fallback_parse(raw_html)
            
            # Use Gemini for intelligent parsing
            parsed_data = await self._gemini_parse(raw_html, ml_config)
            
            # Validate confidence score
            if parsed_data.confidence_score < confidence_threshold:
                logger.info(f"Low confidence score ({parsed_data.confidence_score}), using fallback")
                fallback_data = await self._fallback_parse(raw_html)
                # Combine results with preference for high-confidence fields
                parsed_data = self._merge_parsing_results(parsed_data, fallback_data)
            
            # Log analytics
            await self._log_parsing_analytics(scraper_config_id, parsed_data, db)
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error in ML parsing: {e}")
            return await self._fallback_parse(raw_html)
    
    async def _gemini_parse(self, raw_html: str, ml_config: MLParsingConfig) -> ParsedJobData:
        """Use Gemini API to parse job data"""
        try:
            # Clean HTML for better processing
            cleaned_text = self._clean_html(raw_html)
            
            # Build parsing prompt based on configuration
            prompt = self._build_parsing_prompt(cleaned_text, ml_config)
            
            # Generate content with Gemini
            response = self.model.generate_content(prompt)
            
            # Parse response
            parsed_json = json.loads(response.text)
            
            # Convert to ParsedJobData
            parsed_data = self._json_to_parsed_data(parsed_json)
            
            # Calculate confidence score
            parsed_data.confidence_score = self._calculate_confidence_score(parsed_data, parsed_json)
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error in Gemini parsing: {e}")
            # Return low-confidence empty result
            return ParsedJobData(confidence_score=0.0)
    
    def _build_parsing_prompt(self, text: str, ml_config: MLParsingConfig) -> str:
        """Build intelligent parsing prompt for Gemini"""
        field_mapping = json.loads(ml_config.field_mapping) if ml_config.field_mapping else {}
        
        prompt = f"""
You are an expert job posting parser. Extract structured job information from the following text.

Text to parse:
{text[:4000]}  # Limit text length

Extract the following information and return as JSON:
{{
    "title": "Job title",
    "company": "Company name",
    "location": "Job location (city, state/country)",
    "salary_min": "Minimum salary as number (null if not found)",
    "salary_max": "Maximum salary as number (null if not found)",
    "job_type": "Employment type (full-time, part-time, contract, etc.)",
    "experience_level": "Required experience level (entry, mid, senior, etc.)",
    "description": "Brief job description (max 500 chars)",
    "requirements": ["List of key requirements"],
    "benefits": ["List of benefits offered"],
    "is_remote": "true/false if remote work is mentioned",
    "posted_date": "ISO date string if found",
    "application_url": "Application URL if found",
    "confidence_indicators": {{
        "title_confidence": "0.0-1.0 confidence in title extraction",
        "company_confidence": "0.0-1.0 confidence in company extraction",
        "salary_confidence": "0.0-1.0 confidence in salary extraction",
        "overall_structure": "0.0-1.0 confidence in overall parsing"
    }}
}}

Special instructions:
- If salary is mentioned as a range, extract both min and max
- For requirements, focus on skills, education, and experience
- For benefits, include health, vacation, equity, etc.
- Be conservative with confidence scores
- Return null for fields you cannot confidently extract
- Ensure all JSON is properly formatted
"""
        
        # Add custom field mapping instructions if available
        if field_mapping:
            prompt += f"\n\nCustom field mapping preferences:\n{json.dumps(field_mapping, indent=2)}"
        
        return prompt
    
    def _json_to_parsed_data(self, parsed_json: Dict[str, Any]) -> ParsedJobData:
        """Convert JSON response to ParsedJobData object"""
        try:
            # Handle posted_date parsing
            posted_date = None
            if parsed_json.get('posted_date'):
                try:
                    posted_date = datetime.fromisoformat(parsed_json['posted_date'].replace('Z', '+00:00'))
                except:
                    posted_date = None
            
            return ParsedJobData(
                title=parsed_json.get('title'),
                company=parsed_json.get('company'),
                location=parsed_json.get('location'),
                salary_min=parsed_json.get('salary_min'),
                salary_max=parsed_json.get('salary_max'),
                job_type=parsed_json.get('job_type'),
                experience_level=parsed_json.get('experience_level'),
                description=parsed_json.get('description'),
                requirements=parsed_json.get('requirements', []),
                benefits=parsed_json.get('benefits', []),
                is_remote=parsed_json.get('is_remote'),
                posted_date=posted_date,
                application_url=parsed_json.get('application_url'),
                parsing_metadata={
                    'gemini_response': parsed_json,
                    'parsed_at': datetime.utcnow().isoformat(),
                    'parsing_method': 'gemini_api'
                }
            )
        except Exception as e:
            logger.error(f"Error converting JSON to ParsedJobData: {e}")
            return ParsedJobData(confidence_score=0.0)
    
    def _calculate_confidence_score(self, parsed_data: ParsedJobData, raw_json: Dict[str, Any]) -> float:
        """Calculate overall confidence score for parsed data"""
        try:
            confidence_indicators = raw_json.get('confidence_indicators', {})
            
            # Weight different fields by importance
            weights = {
                'title_confidence': 0.3,
                'company_confidence': 0.25,
                'salary_confidence': 0.2,
                'overall_structure': 0.25
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for field, weight in weights.items():
                confidence = confidence_indicators.get(field, 0.5)  # Default to 0.5
                if isinstance(confidence, (int, float)):
                    total_score += confidence * weight
                    total_weight += weight
            
            # Adjust based on data completeness
            completeness_bonus = 0.0
            if parsed_data.title: completeness_bonus += 0.1
            if parsed_data.company: completeness_bonus += 0.1
            if parsed_data.location: completeness_bonus += 0.05
            if parsed_data.salary_min or parsed_data.salary_max: completeness_bonus += 0.1
            
            final_score = (total_score / total_weight if total_weight > 0 else 0.5) + completeness_bonus
            return min(final_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.5
    
    async def _fallback_parse(self, raw_html: str) -> ParsedJobData:
        """Fallback parsing using regex and heuristics"""
        try:
            cleaned_text = self._clean_html(raw_html)
            
            # Basic regex patterns for common job data
            title_patterns = [
                r'<title[^>]*>([^<]+)</title>',
                r'<h1[^>]*>([^<]+)</h1>',
                r'job[_\s]*title["\s]*:["\s]*([^"\n,]+)',
            ]
            
            company_patterns = [
                r'company["\s]*:["\s]*([^"\n,]+)',
                r'<span[^>]*company[^>]*>([^<]+)</span>',
                r'employer["\s]*:["\s]*([^"\n,]+)',
            ]
            
            location_patterns = [
                r'location["\s]*:["\s]*([^"\n,]+)',
                r'<span[^>]*location[^>]*>([^<]+)</span>',
                r'city["\s]*:["\s]*([^"\n,]+)',
            ]
            
            salary_patterns = [
                r'\$([0-9,]+)\s*-\s*\$([0-9,]+)',
                r'salary["\s]*:["\s]*([^"\n,]+)',
                r'\$([0-9,]+)\s*(?:per|/)',
            ]
            
            # Extract data using patterns
            title = self._extract_with_patterns(cleaned_text, title_patterns)
            company = self._extract_with_patterns(cleaned_text, company_patterns)
            location = self._extract_with_patterns(cleaned_text, location_patterns)
            
            # Extract salary range
            salary_min, salary_max = self._extract_salary_range(cleaned_text, salary_patterns)
            
            # Detect remote work
            is_remote = bool(re.search(r'\b(remote|work\s+from\s+home|wfh)\b', cleaned_text, re.IGNORECASE))
            
            return ParsedJobData(
                title=title,
                company=company,
                location=location,
                salary_min=salary_min,
                salary_max=salary_max,
                is_remote=is_remote,
                confidence_score=0.6,  # Medium confidence for fallback
                parsing_metadata={
                    'parsed_at': datetime.utcnow().isoformat(),
                    'parsing_method': 'fallback_regex'
                }
            )
            
        except Exception as e:
            logger.error(f"Error in fallback parsing: {e}")
            return ParsedJobData(confidence_score=0.3)
    
    def _extract_with_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Extract text using multiple regex patterns"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result = match.group(1).strip()
                if result and len(result) > 2:  # Basic validation
                    return result
        return None
    
    def _extract_salary_range(self, text: str, patterns: List[str]) -> Tuple[Optional[float], Optional[float]]:
        """Extract salary range from text"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) >= 2:  # Range pattern
                        min_sal = float(match.group(1).replace(',', ''))
                        max_sal = float(match.group(2).replace(',', ''))
                        return min_sal, max_sal
                    else:  # Single salary
                        salary = float(match.group(1).replace(',', ''))
                        return salary, None
                except ValueError:
                    continue
        return None, None
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML for better text processing"""
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags but keep content
        html = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html)
        
        return html.strip()
    
    def _merge_parsing_results(self, ml_result: ParsedJobData, fallback_result: ParsedJobData) -> ParsedJobData:
        """Merge ML and fallback results, preferring higher confidence fields"""
        merged = ParsedJobData()
        
        # Use ML result as base if confidence is reasonable
        if ml_result.confidence_score > 0.3:
            merged = ml_result
            # Fill in missing fields from fallback
            if not merged.title and fallback_result.title:
                merged.title = fallback_result.title
            if not merged.company and fallback_result.company:
                merged.company = fallback_result.company
            if not merged.location and fallback_result.location:
                merged.location = fallback_result.location
        else:
            # Use fallback as base
            merged = fallback_result
        
        # Update confidence score
        merged.confidence_score = max(ml_result.confidence_score, fallback_result.confidence_score)
        
        return merged
    
    async def _log_parsing_analytics(self, scraper_config_id: str, parsed_data: ParsedJobData, db=None):  # db: Session - Using MongoDB instead
        """Log parsing analytics for monitoring and improvement"""
        try:
            analytics = AnalyticsMetrics(
                scraper_config_id=scraper_config_id,
                metric_name="ml_parsing_confidence",
                metric_value=parsed_data.confidence_score,
                metric_data={
                    'parsing_method': parsed_data.parsing_metadata.get('parsing_method', 'unknown'),
                    'fields_extracted': {
                        'title': bool(parsed_data.title),
                        'company': bool(parsed_data.company),
                        'location': bool(parsed_data.location),
                        'salary': bool(parsed_data.salary_min or parsed_data.salary_max)
                    }
                },
                created_at=datetime.utcnow()
            )
            
            db.add(analytics)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error logging parsing analytics: {e}")
    
    async def validate_job_data(self, parsed_data: ParsedJobData) -> Dict[str, Any]:
        """Validate parsed job data quality"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'quality_score': 0.0
        }
        
        quality_points = 0
        max_points = 10
        
        # Required field validation
        if not parsed_data.title:
            validation_result['errors'].append('Job title is required')
            validation_result['is_valid'] = False
        else:
            quality_points += 2
        
        if not parsed_data.company:
            validation_result['warnings'].append('Company name is missing')
        else:
            quality_points += 2
        
        # Optional field scoring
        if parsed_data.location:
            quality_points += 1
        if parsed_data.salary_min or parsed_data.salary_max:
            quality_points += 2
        if parsed_data.job_type:
            quality_points += 1
        if parsed_data.description:
            quality_points += 1
        if parsed_data.requirements:
            quality_points += 1
        
        # Confidence score validation
        if parsed_data.confidence_score < 0.5:
            validation_result['warnings'].append('Low parsing confidence score')
        
        validation_result['quality_score'] = quality_points / max_points
        
        return validation_result

# Global ML parsing service instance
ml_parsing_service = MLParsingService()