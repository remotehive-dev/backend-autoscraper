import json
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai

try:
    from backend.core.config import settings
except ImportError:
    # Fallback for testing or standalone usage
    class MockSettings:
        GEMINI_API_KEY = None
    settings = MockSettings()

logger = logging.getLogger(__name__)

class GeminiClient:
    """Client for interacting with Google's Gemini API for job data parsing"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', None)
        self.model = None
        self.available = False
        self._initialize()
    
    def _initialize(self):
        """Initialize the Gemini API client"""
        try:
            if self.api_key:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.available = True
                logger.info("Gemini client initialized successfully")
            else:
                logger.warning("Gemini API key not provided")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.available = False
    
    async def parse_job_data(self, html_content: str, field_mapping: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parse job data from HTML content using Gemini API"""
        if not self.available:
            raise Exception("Gemini client not available")
        
        try:
            # Build parsing prompt
            prompt = self._build_parsing_prompt(html_content, field_mapping)
            
            # Generate content with Gemini
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            parsed_data = json.loads(response.text)
            
            # Add confidence score if not present
            if 'confidence' not in parsed_data:
                parsed_data['confidence'] = self._calculate_confidence(parsed_data)
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            raise Exception("Invalid JSON response from Gemini")
        except Exception as e:
            logger.error(f"Error parsing job data with Gemini: {e}")
            raise
    
    def _build_parsing_prompt(self, html_content: str, field_mapping: Dict[str, Any] = None) -> str:
        """Build the parsing prompt for Gemini"""
        # Clean HTML content
        cleaned_content = self._clean_html(html_content)
        
        # Base prompt
        prompt = f"""
You are an expert job posting parser. Extract structured job information from the following HTML content.

HTML Content:
{cleaned_content[:4000]}  # Limit content length

Extract the following information and return it as a JSON object:
{{
    "job_title": "extracted job title",
    "company_name": "extracted company name",
    "job_location": "extracted job location",
    "job_description": "extracted job description",
    "salary_range": "extracted salary range (if available)",
    "job_type": "extracted job type (Full-time, Part-time, Contract, etc.)",
    "experience_level": "extracted experience level (Entry, Junior, Mid, Senior, etc.)",
    "skills_required": ["list", "of", "required", "skills"],
    "remote_option": true/false,
    "application_url": "extracted application URL (if available)",
    "posted_date": "extracted posting date (if available)",
    "confidence": 0.95
}}

Important:
- Return only valid JSON
- Use null for missing information
- Confidence should be between 0.0 and 1.0
- Be as accurate as possible
"""
        
        # Add field mapping instructions if provided
        if field_mapping:
            prompt += "\n\nField mapping guidelines:\n"
            for field, mapping in field_mapping.items():
                prompt += f"- {field}: {mapping}\n"
        
        return prompt
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content for better parsing"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            logger.warning(f"Failed to clean HTML with BeautifulSoup: {e}")
            return html_content
    
    def _calculate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data completeness"""
        required_fields = ['job_title', 'company_name', 'job_location']
        optional_fields = ['job_description', 'salary_range', 'job_type', 'experience_level']
        
        # Check required fields
        required_score = sum(1 for field in required_fields if parsed_data.get(field))
        required_weight = required_score / len(required_fields) * 0.7
        
        # Check optional fields
        optional_score = sum(1 for field in optional_fields if parsed_data.get(field))
        optional_weight = optional_score / len(optional_fields) * 0.3
        
        return min(required_weight + optional_weight, 1.0)
    
    async def test_connection(self) -> bool:
        """Test the Gemini API connection"""
        if not self.available:
            return False
        
        try:
            # Simple test prompt
            response = self.model.generate_content("Return the JSON: {\"test\": \"success\"}")
            test_data = json.loads(response.text)
            return test_data.get('test') == 'success'
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "model_name": "gemini-1.5-flash",
            "available": self.available,
            "api_key_configured": bool(self.api_key)
        }