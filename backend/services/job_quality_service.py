from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import re
import hashlib
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class JobQualityService:
    """Service for job deduplication, quality scoring, and content enhancement."""
    
    def __init__(self, db=None):
        self.db = db
        
        # Quality scoring weights
        self.quality_weights = {
            'title_quality': 0.2,
            'description_quality': 0.3,
            'company_info': 0.15,
            'salary_info': 0.15,
            'location_info': 0.1,
            'freshness': 0.1
        }
        
        # Common spam/low-quality indicators
        self.spam_indicators = [
            r'work from home.*easy money',
            r'make.*\$\d+.*per (day|week|hour).*guaranteed',
            r'no experience.*high pay',
            r'click here.*earn',
            r'pyramid.*scheme',
            r'multi.*level.*marketing',
            r'mlm',
            r'get rich quick'
        ]
        
        # High-quality job indicators
        self.quality_indicators = [
            r'benefits.*package',
            r'health.*insurance',
            r'401k|retirement',
            r'professional.*development',
            r'career.*growth',
            r'competitive.*salary',
            r'equity|stock.*options'
        ]
    
    def generate_job_fingerprint(self, job_data: Dict) -> str:
        """Generate a unique fingerprint for job deduplication."""
        try:
            # Normalize key fields for comparison
            title = self._normalize_text(job_data.get('title', ''))
            company = self._normalize_text(job_data.get('company', ''))
            location = self._normalize_text(job_data.get('location', ''))
            
            # Create fingerprint from key components
            fingerprint_data = f"{title}|{company}|{location}"
            
            # Generate hash
            return hashlib.md5(fingerprint_data.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating job fingerprint: {str(e)}")
            return hashlib.md5(str(job_data).encode()).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ''
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common variations
        text = re.sub(r'[^a-z0-9\s]', '', text)
        
        # Remove common job title variations
        text = re.sub(r'\b(jr|sr|senior|junior|lead|principal)\b', '', text)
        text = re.sub(r'\b(remote|hybrid|onsite|on-site)\b', '', text)
        
        return text.strip()
    
    def check_duplicate(self, job_data: Dict, similarity_threshold: float = 0.85) -> Optional[Dict]:
        """Check if a job is a duplicate of existing jobs."""
        try:
            if not self.db:
                return {'is_duplicate': False, 'error': 'No database connection'}
                
            fingerprint = self.generate_job_fingerprint(job_data)
            
            # First check exact fingerprint match
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            exact_match = await self.db.job_posts.find_one({
                'fingerprint': fingerprint,
                'created_at': {'$gte': thirty_days_ago}
            })
            
            if exact_match:
                return {
                    'is_duplicate': True,
                    'match_type': 'exact',
                    'existing_job_id': str(exact_match['_id']),
                    'similarity_score': 1.0,
                    'existing_job': {
                        'title': exact_match['title'],
                        'company': exact_match['company'],
                        'location': exact_match['location'],
                        'created_at': exact_match['created_at']
                    }
                }
            
            # Check for similar jobs using fuzzy matching
            company = job_data.get('company', '')
            if not company:
                return {'is_duplicate': False}
            
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            similar_jobs = await self.db.job_posts.find({
                'company': {'$regex': company, '$options': 'i'},
                'created_at': {'$gte': seven_days_ago}
            }).sort('created_at', -1).limit(20).to_list()
            
            # Check similarity with each job
            for job in similar_jobs:
                similarity = self._calculate_similarity(job_data, {
                    'title': job['title'],
                    'company': job['company'],
                    'location': job['location']
                })
                
                if similarity >= similarity_threshold:
                    return {
                        'is_duplicate': True,
                        'match_type': 'similar',
                        'existing_job_id': str(job['_id']),
                        'similarity_score': similarity,
                        'existing_job': {
                            'title': job['title'],
                            'company': job['company'],
                            'location': job['location'],
                            'created_at': job['created_at']
                        }
                    }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            logger.error(f"Error checking duplicate: {str(e)}")
            return {'is_duplicate': False, 'error': str(e)}
    
    def _calculate_similarity(self, job1: Dict, job2: Dict) -> float:
        """Calculate similarity score between two jobs."""
        try:
            # Normalize texts
            title1 = self._normalize_text(job1.get('title', ''))
            title2 = self._normalize_text(job2.get('title', ''))
            
            company1 = self._normalize_text(job1.get('company', ''))
            company2 = self._normalize_text(job2.get('company', ''))
            
            location1 = self._normalize_text(job1.get('location', ''))
            location2 = self._normalize_text(job2.get('location', ''))
            
            # Calculate individual similarities
            title_sim = SequenceMatcher(None, title1, title2).ratio()
            company_sim = SequenceMatcher(None, company1, company2).ratio()
            location_sim = SequenceMatcher(None, location1, location2).ratio()
            
            # Weighted average (title is most important)
            similarity = (title_sim * 0.6 + company_sim * 0.3 + location_sim * 0.1)
            
            return similarity
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    def calculate_quality_score(self, job_data: Dict) -> Dict:
        """Calculate comprehensive quality score for a job posting."""
        try:
            scores = {}
            
            # Title quality (0-100)
            scores['title_quality'] = self._score_title_quality(job_data.get('title', ''))
            
            # Description quality (0-100)
            scores['description_quality'] = self._score_description_quality(job_data.get('description', ''))
            
            # Company information completeness (0-100)
            scores['company_info'] = self._score_company_info(job_data)
            
            # Salary information (0-100)
            scores['salary_info'] = self._score_salary_info(job_data.get('salary', ''))
            
            # Location information (0-100)
            scores['location_info'] = self._score_location_info(job_data.get('location', ''))
            
            # Freshness score (0-100)
            scores['freshness'] = self._score_freshness(job_data.get('posted_date'))
            
            # Calculate weighted overall score
            overall_score = sum(
                scores[key] * self.quality_weights[key] 
                for key in scores.keys()
            )
            
            # Check for spam indicators
            spam_score = self._check_spam_indicators(job_data)
            
            # Apply spam penalty
            if spam_score > 0.3:
                overall_score *= (1 - spam_score)
            
            return {
                'overall_score': round(overall_score, 2),
                'component_scores': scores,
                'spam_score': round(spam_score, 2),
                'quality_grade': self._get_quality_grade(overall_score),
                'recommendations': self._get_quality_recommendations(scores)
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {str(e)}")
            return {
                'overall_score': 50.0,
                'component_scores': {},
                'spam_score': 0.0,
                'quality_grade': 'C',
                'recommendations': [],
                'error': str(e)
            }
    
    def _score_title_quality(self, title: str) -> float:
        """Score job title quality."""
        if not title:
            return 0.0
        
        score = 50.0  # Base score
        
        # Length check
        if 10 <= len(title) <= 80:
            score += 20
        elif len(title) < 5:
            score -= 30
        
        # Check for specific role indicators
        if re.search(r'\b(developer|engineer|manager|analyst|specialist|coordinator)\b', title, re.I):
            score += 15
        
        # Check for seniority level
        if re.search(r'\b(senior|lead|principal|junior|entry)\b', title, re.I):
            score += 10
        
        # Penalize vague titles
        if re.search(r'\b(opportunity|position|role|job)\b$', title, re.I):
            score -= 15
        
        # Penalize excessive capitalization
        if title.isupper():
            score -= 10
        
        return max(0, min(100, score))
    
    def _score_description_quality(self, description: str) -> float:
        """Score job description quality."""
        if not description:
            return 0.0
        
        score = 30.0  # Base score
        
        # Length check
        word_count = len(description.split())
        if 100 <= word_count <= 1000:
            score += 30
        elif word_count < 50:
            score -= 20
        elif word_count > 2000:
            score -= 10
        
        # Check for key sections
        sections = [
            r'responsibilities|duties|role',
            r'requirements|qualifications|skills',
            r'benefits|perks|compensation',
            r'about (us|the company|our team)'
        ]
        
        for section in sections:
            if re.search(section, description, re.I):
                score += 10
        
        # Check for quality indicators
        for indicator in self.quality_indicators:
            if re.search(indicator, description, re.I):
                score += 5
        
        # Check for technical skills (for tech jobs)
        tech_skills = r'\b(python|java|javascript|react|sql|aws|docker|kubernetes|git)\b'
        if re.search(tech_skills, description, re.I):
            score += 10
        
        return max(0, min(100, score))
    
    def _score_company_info(self, job_data: Dict) -> float:
        """Score company information completeness."""
        score = 0.0
        
        # Company name
        if job_data.get('company'):
            score += 40
            
            # Penalize generic company names
            company = job_data['company'].lower()
            if company in ['confidential', 'private', 'undisclosed', 'various']:
                score -= 20
        
        # Company size/type indicators
        description = job_data.get('description', '').lower()
        if re.search(r'\b(startup|fortune 500|enterprise|small business)\b', description):
            score += 15
        
        # Industry information
        if re.search(r'\b(technology|healthcare|finance|education|retail)\b', description):
            score += 15
        
        # Company website/contact
        if re.search(r'(www\.|http|@.*\.com)', description):
            score += 15
        
        # Company description
        if re.search(r'about (us|the company|our team)', description, re.I):
            score += 15
        
        return max(0, min(100, score))
    
    def _score_salary_info(self, salary: str) -> float:
        """Score salary information quality."""
        if not salary or salary.lower() in ['not specified', 'competitive', 'negotiable']:
            return 20.0  # Some points for transparency
        
        score = 40.0  # Base score for having salary info
        
        # Check for specific salary range
        if re.search(r'\$[\d,]+\s*-\s*\$[\d,]+', salary):
            score += 30
        elif re.search(r'\$[\d,]+', salary):
            score += 20
        
        # Check for time period
        if re.search(r'\b(per year|annually|per hour|hourly)\b', salary, re.I):
            score += 15
        
        # Check for benefits mention
        if re.search(r'\b(benefits|bonus|equity|stock)\b', salary, re.I):
            score += 15
        
        return max(0, min(100, score))
    
    def _score_location_info(self, location: str) -> float:
        """Score location information quality."""
        if not location:
            return 0.0
        
        score = 40.0  # Base score
        
        # Check for city and state/country
        if re.search(r'.+,\s*.+', location):
            score += 30
        
        # Check for remote indicators
        if re.search(r'\b(remote|work from home|wfh|anywhere)\b', location, re.I):
            score += 20
        
        # Check for specific address details
        if re.search(r'\b\d+\b', location):  # Street number or zip code
            score += 10
        
        return max(0, min(100, score))
    
    def _score_freshness(self, posted_date) -> float:
        """Score job posting freshness."""
        if not posted_date:
            return 50.0  # Neutral score if unknown
        
        try:
            if isinstance(posted_date, str):
                # Try to parse string date
                posted_date = datetime.fromisoformat(posted_date.replace('Z', '+00:00'))
            
            days_old = (datetime.now() - posted_date.replace(tzinfo=None)).days
            
            if days_old <= 1:
                return 100.0
            elif days_old <= 3:
                return 90.0
            elif days_old <= 7:
                return 80.0
            elif days_old <= 14:
                return 60.0
            elif days_old <= 30:
                return 40.0
            else:
                return 20.0
                
        except Exception as e:
            logger.error(f"Error scoring freshness: {str(e)}")
            return 50.0
    
    def _check_spam_indicators(self, job_data: Dict) -> float:
        """Check for spam/low-quality indicators."""
        spam_score = 0.0
        
        # Combine all text fields
        all_text = ' '.join([
            job_data.get('title', ''),
            job_data.get('description', ''),
            job_data.get('company', ''),
            job_data.get('location', '')
        ]).lower()
        
        # Check spam indicators
        for indicator in self.spam_indicators:
            if re.search(indicator, all_text, re.I):
                spam_score += 0.2
        
        # Check for excessive punctuation
        if len(re.findall(r'[!]{2,}', all_text)) > 0:
            spam_score += 0.1
        
        # Check for excessive capitalization
        caps_ratio = len(re.findall(r'[A-Z]', all_text)) / max(len(all_text), 1)
        if caps_ratio > 0.3:
            spam_score += 0.15
        
        # Check for suspicious URLs
        if re.search(r'bit\.ly|tinyurl|goo\.gl', all_text):
            spam_score += 0.2
        
        return min(1.0, spam_score)
    
    def _get_quality_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A+'
        elif score >= 85:
            return 'A'
        elif score >= 80:
            return 'A-'
        elif score >= 75:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 65:
            return 'B-'
        elif score >= 60:
            return 'C+'
        elif score >= 55:
            return 'C'
        elif score >= 50:
            return 'C-'
        elif score >= 40:
            return 'D'
        else:
            return 'F'
    
    def _get_quality_recommendations(self, scores: Dict) -> List[str]:
        """Generate recommendations for improving job quality."""
        recommendations = []
        
        if scores.get('title_quality', 0) < 60:
            recommendations.append("Improve job title clarity and specificity")
        
        if scores.get('description_quality', 0) < 60:
            recommendations.append("Enhance job description with more details about responsibilities and requirements")
        
        if scores.get('company_info', 0) < 60:
            recommendations.append("Add more company information and background")
        
        if scores.get('salary_info', 0) < 60:
            recommendations.append("Include salary range or compensation details")
        
        if scores.get('location_info', 0) < 60:
            recommendations.append("Provide more specific location information")
        
        return recommendations
    
    def enhance_job_data(self, job_data: Dict) -> Dict:
        """Enhance job data with additional processing and standardization."""
        try:
            enhanced_data = job_data.copy()
            
            # Generate fingerprint
            enhanced_data['fingerprint'] = self.generate_job_fingerprint(job_data)
            
            # Calculate quality score
            quality_info = self.calculate_quality_score(job_data)
            enhanced_data['quality_score'] = quality_info['overall_score']
            enhanced_data['quality_grade'] = quality_info['quality_grade']
            enhanced_data['spam_score'] = quality_info['spam_score']
            
            # Standardize job type
            enhanced_data['job_type'] = self._standardize_job_type(job_data.get('job_type', ''))
            
            # Extract and standardize skills
            enhanced_data['extracted_skills'] = self._extract_skills(job_data.get('description', ''))
            
            # Standardize remote work status
            enhanced_data['remote_work'] = self._determine_remote_status(job_data)
            
            # Extract experience level
            enhanced_data['experience_level'] = self._extract_experience_level(job_data)
            
            # Add processing metadata
            enhanced_data['processed_at'] = datetime.now().isoformat()
            enhanced_data['enhancement_version'] = '1.0'
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error enhancing job data: {str(e)}")
            return job_data
    
    def _standardize_job_type(self, job_type: str) -> str:
        """Standardize job type to common categories."""
        if not job_type:
            return 'Not Specified'
        
        job_type_lower = job_type.lower()
        
        if 'full' in job_type_lower and 'time' in job_type_lower:
            return 'Full-time'
        elif 'part' in job_type_lower and 'time' in job_type_lower:
            return 'Part-time'
        elif 'contract' in job_type_lower or 'freelance' in job_type_lower:
            return 'Contract'
        elif 'intern' in job_type_lower:
            return 'Internship'
        elif 'temporary' in job_type_lower or 'temp' in job_type_lower:
            return 'Temporary'
        else:
            return job_type.title()
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract technical skills from job description."""
        if not description:
            return []
        
        # Common technical skills
        skills_patterns = {
            'Programming Languages': r'\b(python|java|javascript|typescript|c\+\+|c#|php|ruby|go|rust|swift|kotlin)\b',
            'Web Technologies': r'\b(html|css|react|angular|vue|node\.js|express|django|flask|spring)\b',
            'Databases': r'\b(sql|mysql|postgresql|mongodb|redis|elasticsearch|oracle)\b',
            'Cloud Platforms': r'\b(aws|azure|gcp|google cloud|docker|kubernetes|terraform)\b',
            'Tools': r'\b(git|jenkins|jira|confluence|slack|figma|photoshop)\b'
        }
        
        extracted_skills = []
        description_lower = description.lower()
        
        for category, pattern in skills_patterns.items():
            matches = re.findall(pattern, description_lower, re.I)
            extracted_skills.extend([match.upper() if len(match) <= 3 else match.title() for match in matches])
        
        # Remove duplicates and return
        return list(set(extracted_skills))
    
    def _determine_remote_status(self, job_data: Dict) -> str:
        """Determine remote work status."""
        # Check location field
        location = job_data.get('location', '').lower()
        if re.search(r'\b(remote|anywhere|work from home|wfh)\b', location):
            return 'Remote'
        
        # Check description
        description = job_data.get('description', '').lower()
        if re.search(r'\b(remote|work from home|wfh|distributed team)\b', description):
            if re.search(r'\b(hybrid|occasional office|some travel)\b', description):
                return 'Hybrid'
            else:
                return 'Remote'
        
        # Check for on-site indicators
        if re.search(r'\b(on-site|onsite|office|in-person)\b', description):
            return 'On-site'
        
        return 'Not Specified'
    
    def _extract_experience_level(self, job_data: Dict) -> str:
        """Extract experience level from job data."""
        # Combine title and description
        text = ' '.join([
            job_data.get('title', ''),
            job_data.get('description', '')
        ]).lower()
        
        # Check for experience indicators
        if re.search(r'\b(entry.level|junior|0.2 years|new grad|recent graduate)\b', text):
            return 'Entry Level'
        elif re.search(r'\b(senior|lead|principal|5\+ years|7\+ years)\b', text):
            return 'Senior Level'
        elif re.search(r'\b(mid.level|3.5 years|4.6 years)\b', text):
            return 'Mid Level'
        elif re.search(r'\b(director|vp|vice president|head of|chief)\b', text):
            return 'Executive'
        elif re.search(r'\b(manager|team lead|supervisor)\b', text):
            return 'Management'
        else:
            return 'Not Specified'