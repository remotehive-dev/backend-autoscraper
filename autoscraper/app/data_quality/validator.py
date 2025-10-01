import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import re
import json
from urllib.parse import urlparse
from loguru import logger
import hashlib
from statistics import mean
import difflib

from ..models.mongodb_models import JobPosting
from ..ai.decision_engine import get_ai_decision_engine
from ..monitoring.dashboard import get_monitoring_dashboard

class ValidationRule(str, Enum):
    """Data validation rules"""
    REQUIRED_FIELDS = "required_fields"
    FIELD_FORMAT = "field_format"
    FIELD_LENGTH = "field_length"
    URL_VALIDITY = "url_validity"
    DATE_VALIDITY = "date_validity"
    SALARY_RANGE = "salary_range"
    DUPLICATE_DETECTION = "duplicate_detection"
    CONTENT_QUALITY = "content_quality"
    LANGUAGE_DETECTION = "language_detection"
    SPAM_DETECTION = "spam_detection"

class ValidationSeverity(str, Enum):
    """Validation issue severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class EnrichmentType(str, Enum):
    """Content enrichment types"""
    SKILL_EXTRACTION = "skill_extraction"
    SALARY_NORMALIZATION = "salary_normalization"
    LOCATION_STANDARDIZATION = "location_standardization"
    COMPANY_INFO = "company_info"
    JOB_CATEGORY = "job_category"
    EXPERIENCE_LEVEL = "experience_level"
    REMOTE_WORK_TYPE = "remote_work_type"
    BENEFITS_EXTRACTION = "benefits_extraction"
    REQUIREMENTS_PARSING = "requirements_parsing"
    SENTIMENT_ANALYSIS = "sentiment_analysis"

@dataclass
class ValidationIssue:
    """Data validation issue"""
    rule: ValidationRule
    severity: ValidationSeverity
    field: str
    message: str
    value: Any = None
    suggestion: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ValidationResult:
    """Validation result for a job posting"""
    job_id: str
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    validated_at: datetime
    processing_time: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class EnrichmentResult:
    """Content enrichment result"""
    job_id: str
    enrichments: Dict[EnrichmentType, Any]
    confidence_scores: Dict[EnrichmentType, float]
    enriched_at: datetime
    processing_time: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class DataQualityValidator:
    """AI-powered data quality validation and content enrichment"""
    
    def __init__(self):
        self.ai_decision_engine = get_ai_decision_engine()
        self.monitoring_dashboard = None
        
        # Validation rules configuration
        self.required_fields = {
            'title': ValidationSeverity.CRITICAL,
            'company': ValidationSeverity.ERROR,
            'location': ValidationSeverity.WARNING,
            'description': ValidationSeverity.ERROR,
            'url': ValidationSeverity.CRITICAL
        }
        
        # Field format patterns
        self.format_patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'phone': re.compile(r'^[\+]?[1-9]?[0-9]{7,15}$'),
            'url': re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
            'salary': re.compile(r'\$?[\d,]+(?:\.\d{2})?(?:\s*-\s*\$?[\d,]+(?:\.\d{2})?)?')
        }
        
        # Content quality thresholds
        self.quality_thresholds = {
            'min_title_length': 10,
            'max_title_length': 200,
            'min_description_length': 50,
            'max_description_length': 10000,
            'min_company_length': 2,
            'max_company_length': 100
        }
        
        # Spam detection keywords
        self.spam_keywords = {
            'high_risk': ['make money fast', 'work from home easy', 'no experience required', 'guaranteed income'],
            'medium_risk': ['urgent hiring', 'immediate start', 'no interview', 'cash payment'],
            'low_risk': ['flexible hours', 'part time', 'remote work', 'competitive salary']
        }
        
        # Common skills database (simplified)
        self.common_skills = {
            'programming': ['python', 'javascript', 'java', 'c++', 'c#', 'php', 'ruby', 'go', 'rust', 'swift'],
            'web': ['html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask'],
            'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch'],
            'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform'],
            'tools': ['git', 'jenkins', 'jira', 'confluence', 'slack', 'figma', 'photoshop']
        }
        
        # Duplicate detection cache
        self.duplicate_cache: Dict[str, str] = {}  # hash -> job_id
    
    async def initialize(self):
        """Initialize the data quality validator"""
        try:
            self.monitoring_dashboard = await get_monitoring_dashboard()
            logger.info("Data quality validator initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize data quality validator: {e}")
            raise
    
    async def validate_job_posting(self, job_posting: JobPosting) -> ValidationResult:
        """Validate a job posting"""
        start_time = datetime.now()
        issues = []
        
        try:
            # Required fields validation
            issues.extend(await self._validate_required_fields(job_posting))
            
            # Field format validation
            issues.extend(await self._validate_field_formats(job_posting))
            
            # Field length validation
            issues.extend(await self._validate_field_lengths(job_posting))
            
            # URL validity validation
            issues.extend(await self._validate_urls(job_posting))
            
            # Date validity validation
            issues.extend(await self._validate_dates(job_posting))
            
            # Salary range validation
            issues.extend(await self._validate_salary_range(job_posting))
            
            # Duplicate detection
            issues.extend(await self._detect_duplicates(job_posting))
            
            # Content quality validation
            issues.extend(await self._validate_content_quality(job_posting))
            
            # Language detection
            issues.extend(await self._detect_language(job_posting))
            
            # Spam detection
            issues.extend(await self._detect_spam(job_posting))
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(issues)
            
            # Determine if valid
            is_valid = not any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = ValidationResult(
                job_id=str(job_posting.id),
                is_valid=is_valid,
                quality_score=quality_score,
                issues=issues,
                validated_at=datetime.now(),
                processing_time=processing_time,
                metadata={
                    'job_board': job_posting.job_board,
                    'scraped_at': job_posting.scraped_at.isoformat() if job_posting.scraped_at else None
                }
            )
            
            # Record metrics
            if self.monitoring_dashboard:
                await self.monitoring_dashboard.record_data_quality_score(
                    quality_score, 
                    job_posting.job_board
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate job posting {job_posting.id}: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ValidationResult(
                job_id=str(job_posting.id),
                is_valid=False,
                quality_score=0.0,
                issues=[ValidationIssue(
                    rule=ValidationRule.CONTENT_QUALITY,
                    severity=ValidationSeverity.CRITICAL,
                    field="validation",
                    message=f"Validation failed: {str(e)}"
                )],
                validated_at=datetime.now(),
                processing_time=processing_time
            )
    
    async def _validate_required_fields(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate required fields"""
        issues = []
        
        for field, severity in self.required_fields.items():
            value = getattr(job_posting, field, None)
            
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(ValidationIssue(
                    rule=ValidationRule.REQUIRED_FIELDS,
                    severity=severity,
                    field=field,
                    message=f"Required field '{field}' is missing or empty",
                    suggestion=f"Ensure '{field}' is properly extracted from the source"
                ))
        
        return issues
    
    async def _validate_field_formats(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate field formats"""
        issues = []
        
        # Validate URL format
        if job_posting.url and not self.format_patterns['url'].match(job_posting.url):
            issues.append(ValidationIssue(
                rule=ValidationRule.FIELD_FORMAT,
                severity=ValidationSeverity.ERROR,
                field="url",
                message="Invalid URL format",
                value=job_posting.url,
                suggestion="Ensure URL starts with http:// or https://"
            ))
        
        # Validate email in description (if present)
        if job_posting.description:
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', job_posting.description)
            for email in emails:
                if not self.format_patterns['email'].match(email):
                    issues.append(ValidationIssue(
                        rule=ValidationRule.FIELD_FORMAT,
                        severity=ValidationSeverity.WARNING,
                        field="description",
                        message=f"Invalid email format found: {email}",
                        value=email
                    ))
        
        return issues
    
    async def _validate_field_lengths(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate field lengths"""
        issues = []
        
        # Title length
        if job_posting.title:
            title_len = len(job_posting.title)
            if title_len < self.quality_thresholds['min_title_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.WARNING,
                    field="title",
                    message=f"Title too short ({title_len} chars, minimum {self.quality_thresholds['min_title_length']})",
                    value=job_posting.title
                ))
            elif title_len > self.quality_thresholds['max_title_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.WARNING,
                    field="title",
                    message=f"Title too long ({title_len} chars, maximum {self.quality_thresholds['max_title_length']})",
                    value=job_posting.title[:100] + "..."
                ))
        
        # Description length
        if job_posting.description:
            desc_len = len(job_posting.description)
            if desc_len < self.quality_thresholds['min_description_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.WARNING,
                    field="description",
                    message=f"Description too short ({desc_len} chars, minimum {self.quality_thresholds['min_description_length']})",
                ))
            elif desc_len > self.quality_thresholds['max_description_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.INFO,
                    field="description",
                    message=f"Description very long ({desc_len} chars, maximum recommended {self.quality_thresholds['max_description_length']})"
                ))
        
        # Company name length
        if job_posting.company:
            company_len = len(job_posting.company)
            if company_len < self.quality_thresholds['min_company_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.WARNING,
                    field="company",
                    message=f"Company name too short ({company_len} chars)",
                    value=job_posting.company
                ))
            elif company_len > self.quality_thresholds['max_company_length']:
                issues.append(ValidationIssue(
                    rule=ValidationRule.FIELD_LENGTH,
                    severity=ValidationSeverity.WARNING,
                    field="company",
                    message=f"Company name too long ({company_len} chars)",
                    value=job_posting.company
                ))
        
        return issues
    
    async def _validate_urls(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate URL fields"""
        issues = []
        
        if job_posting.url:
            try:
                parsed = urlparse(job_posting.url)
                if not parsed.scheme or not parsed.netloc:
                    issues.append(ValidationIssue(
                        rule=ValidationRule.URL_VALIDITY,
                        severity=ValidationSeverity.ERROR,
                        field="url",
                        message="Invalid URL structure",
                        value=job_posting.url,
                        suggestion="URL must include protocol (http/https) and domain"
                    ))
            except Exception as e:
                issues.append(ValidationIssue(
                    rule=ValidationRule.URL_VALIDITY,
                    severity=ValidationSeverity.ERROR,
                    field="url",
                    message=f"URL parsing failed: {str(e)}",
                    value=job_posting.url
                ))
        
        return issues
    
    async def _validate_dates(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate date fields"""
        issues = []
        
        now = datetime.now()
        
        # Check scraped_at date
        if job_posting.scraped_at:
            if job_posting.scraped_at > now + timedelta(hours=1):  # Allow 1 hour tolerance
                issues.append(ValidationIssue(
                    rule=ValidationRule.DATE_VALIDITY,
                    severity=ValidationSeverity.WARNING,
                    field="scraped_at",
                    message="Scraped date is in the future",
                    value=job_posting.scraped_at.isoformat()
                ))
            elif job_posting.scraped_at < now - timedelta(days=365):  # More than 1 year old
                issues.append(ValidationIssue(
                    rule=ValidationRule.DATE_VALIDITY,
                    severity=ValidationSeverity.INFO,
                    field="scraped_at",
                    message="Job posting is very old (>1 year)",
                    value=job_posting.scraped_at.isoformat()
                ))
        
        # Check posted_date if available
        if hasattr(job_posting, 'posted_date') and job_posting.posted_date:
            if job_posting.posted_date > now + timedelta(days=1):
                issues.append(ValidationIssue(
                    rule=ValidationRule.DATE_VALIDITY,
                    severity=ValidationSeverity.WARNING,
                    field="posted_date",
                    message="Posted date is in the future",
                    value=job_posting.posted_date.isoformat()
                ))
        
        return issues
    
    async def _validate_salary_range(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate salary information"""
        issues = []
        
        if hasattr(job_posting, 'salary') and job_posting.salary:
            salary_text = str(job_posting.salary).lower()
            
            # Check for unrealistic salary ranges
            salary_numbers = re.findall(r'[\d,]+', salary_text)
            if salary_numbers:
                try:
                    amounts = [int(num.replace(',', '')) for num in salary_numbers]
                    max_amount = max(amounts)
                    min_amount = min(amounts)
                    
                    # Check for unrealistic values
                    if max_amount > 1000000:  # > $1M
                        issues.append(ValidationIssue(
                            rule=ValidationRule.SALARY_RANGE,
                            severity=ValidationSeverity.WARNING,
                            field="salary",
                            message=f"Unusually high salary amount: ${max_amount:,}",
                            value=job_posting.salary
                        ))
                    
                    if min_amount < 1000 and 'hour' not in salary_text:  # < $1K annual
                        issues.append(ValidationIssue(
                            rule=ValidationRule.SALARY_RANGE,
                            severity=ValidationSeverity.WARNING,
                            field="salary",
                            message=f"Unusually low salary amount: ${min_amount:,}",
                            value=job_posting.salary
                        ))
                    
                    # Check for inverted ranges
                    if len(amounts) >= 2 and min_amount > max_amount:
                        issues.append(ValidationIssue(
                            rule=ValidationRule.SALARY_RANGE,
                            severity=ValidationSeverity.ERROR,
                            field="salary",
                            message="Salary range appears inverted (min > max)",
                            value=job_posting.salary
                        ))
                        
                except ValueError:
                    issues.append(ValidationIssue(
                        rule=ValidationRule.SALARY_RANGE,
                        severity=ValidationSeverity.WARNING,
                        field="salary",
                        message="Could not parse salary amounts",
                        value=job_posting.salary
                    ))
        
        return issues
    
    async def _detect_duplicates(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Detect duplicate job postings"""
        issues = []
        
        try:
            # Create content hash for duplicate detection
            content_parts = [
                job_posting.title or '',
                job_posting.company or '',
                job_posting.location or '',
                (job_posting.description or '')[:500]  # First 500 chars
            ]
            
            content_string = '|'.join(content_parts).lower().strip()
            content_hash = hashlib.md5(content_string.encode()).hexdigest()
            
            if content_hash in self.duplicate_cache:
                existing_job_id = self.duplicate_cache[content_hash]
                if existing_job_id != str(job_posting.id):
                    issues.append(ValidationIssue(
                        rule=ValidationRule.DUPLICATE_DETECTION,
                        severity=ValidationSeverity.WARNING,
                        field="content",
                        message=f"Potential duplicate of job {existing_job_id}",
                        metadata={'duplicate_job_id': existing_job_id, 'content_hash': content_hash}
                    ))
            else:
                self.duplicate_cache[content_hash] = str(job_posting.id)
                
                # Clean old entries (keep last 10000)
                if len(self.duplicate_cache) > 10000:
                    # Remove oldest 1000 entries (simple cleanup)
                    old_keys = list(self.duplicate_cache.keys())[:1000]
                    for key in old_keys:
                        del self.duplicate_cache[key]
        
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
        
        return issues
    
    async def _validate_content_quality(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Validate content quality using AI"""
        issues = []
        
        try:
            # Basic content quality checks
            if job_posting.description:
                desc = job_posting.description.strip()
                
                # Check for placeholder text
                placeholder_patterns = [
                    r'lorem ipsum',
                    r'placeholder',
                    r'sample text',
                    r'test description',
                    r'\[.*\]',  # Text in brackets
                    r'xxx+',    # Multiple x's
                ]
                
                for pattern in placeholder_patterns:
                    if re.search(pattern, desc, re.IGNORECASE):
                        issues.append(ValidationIssue(
                            rule=ValidationRule.CONTENT_QUALITY,
                            severity=ValidationSeverity.ERROR,
                            field="description",
                            message=f"Placeholder text detected: {pattern}",
                            suggestion="Remove placeholder content"
                        ))
                
                # Check for excessive repetition
                words = desc.lower().split()
                if len(words) > 10:
                    word_counts = {}
                    for word in words:
                        if len(word) > 3:  # Only check longer words
                            word_counts[word] = word_counts.get(word, 0) + 1
                    
                    total_words = len(words)
                    for word, count in word_counts.items():
                        if count / total_words > 0.1:  # Word appears in >10% of text
                            issues.append(ValidationIssue(
                                rule=ValidationRule.CONTENT_QUALITY,
                                severity=ValidationSeverity.WARNING,
                                field="description",
                                message=f"Excessive repetition of word '{word}' ({count} times)",
                                metadata={'word': word, 'count': count, 'percentage': count/total_words}
                            ))
                
                # Check for minimum meaningful content
                meaningful_words = [w for w in words if len(w) > 3 and w.isalpha()]
                if len(meaningful_words) < 10:
                    issues.append(ValidationIssue(
                        rule=ValidationRule.CONTENT_QUALITY,
                        severity=ValidationSeverity.WARNING,
                        field="description",
                        message=f"Low meaningful content ({len(meaningful_words)} meaningful words)",
                        suggestion="Ensure description contains substantial job information"
                    ))
        
        except Exception as e:
            logger.error(f"Content quality validation failed: {e}")
        
        return issues
    
    async def _detect_language(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Detect content language"""
        issues = []
        
        try:
            # Simple language detection based on common words
            if job_posting.description:
                desc = job_posting.description.lower()
                
                # English indicators
                english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
                english_count = sum(1 for word in english_words if word in desc)
                
                # Non-English indicators (basic check)
                non_english_patterns = [
                    r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]',  # Accented characters
                    r'[αβγδεζηθικλμνξοπρστυφχψω]',  # Greek
                    r'[а-я]',  # Cyrillic
                    r'[一-龯]',  # Chinese
                    r'[ひらがなカタカナ]',  # Japanese
                ]
                
                has_non_english = any(re.search(pattern, desc) for pattern in non_english_patterns)
                
                if english_count < 3 and has_non_english:
                    issues.append(ValidationIssue(
                        rule=ValidationRule.LANGUAGE_DETECTION,
                        severity=ValidationSeverity.INFO,
                        field="description",
                        message="Content appears to be in non-English language",
                        metadata={'english_word_count': english_count}
                    ))
        
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
        
        return issues
    
    async def _detect_spam(self, job_posting: JobPosting) -> List[ValidationIssue]:
        """Detect spam content"""
        issues = []
        
        try:
            content = ' '.join([
                job_posting.title or '',
                job_posting.description or '',
                job_posting.company or ''
            ]).lower()
            
            spam_score = 0
            detected_keywords = []
            
            # Check for spam keywords
            for risk_level, keywords in self.spam_keywords.items():
                for keyword in keywords:
                    if keyword in content:
                        detected_keywords.append((keyword, risk_level))
                        if risk_level == 'high_risk':
                            spam_score += 3
                        elif risk_level == 'medium_risk':
                            spam_score += 2
                        else:
                            spam_score += 1
            
            # Check for excessive capitalization
            if job_posting.title:
                caps_ratio = sum(1 for c in job_posting.title if c.isupper()) / len(job_posting.title)
                if caps_ratio > 0.7:
                    spam_score += 2
                    detected_keywords.append(('excessive_caps', 'formatting'))
            
            # Check for excessive punctuation
            if job_posting.description:
                punct_count = sum(1 for c in job_posting.description if c in '!?')
                if punct_count > 10:
                    spam_score += 1
                    detected_keywords.append(('excessive_punctuation', 'formatting'))
            
            # Determine spam level
            if spam_score >= 5:
                severity = ValidationSeverity.ERROR
                message = "High spam probability detected"
            elif spam_score >= 3:
                severity = ValidationSeverity.WARNING
                message = "Medium spam probability detected"
            elif spam_score >= 1:
                severity = ValidationSeverity.INFO
                message = "Low spam probability detected"
            else:
                return issues  # No spam detected
            
            issues.append(ValidationIssue(
                rule=ValidationRule.SPAM_DETECTION,
                severity=severity,
                field="content",
                message=message,
                metadata={
                    'spam_score': spam_score,
                    'detected_keywords': detected_keywords
                }
            ))
        
        except Exception as e:
            logger.error(f"Spam detection failed: {e}")
        
        return issues
    
    def _calculate_quality_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall quality score based on validation issues"""
        try:
            if not issues:
                return 1.0
            
            # Penalty weights by severity
            penalty_weights = {
                ValidationSeverity.INFO: 0.05,
                ValidationSeverity.WARNING: 0.15,
                ValidationSeverity.ERROR: 0.30,
                ValidationSeverity.CRITICAL: 0.50
            }
            
            total_penalty = 0
            for issue in issues:
                total_penalty += penalty_weights.get(issue.severity, 0.1)
            
            # Calculate score (1.0 - penalties, minimum 0.0)
            score = max(0.0, 1.0 - total_penalty)
            
            return round(score, 3)
            
        except Exception as e:
            logger.error(f"Quality score calculation failed: {e}")
            return 0.0
    
    async def enrich_job_posting(self, job_posting: JobPosting) -> EnrichmentResult:
        """Enrich job posting with AI-powered analysis"""
        start_time = datetime.now()
        enrichments = {}
        confidence_scores = {}
        
        try:
            # Extract skills
            skills, skills_confidence = await self._extract_skills(job_posting)
            enrichments[EnrichmentType.SKILL_EXTRACTION] = skills
            confidence_scores[EnrichmentType.SKILL_EXTRACTION] = skills_confidence
            
            # Normalize salary
            salary_info, salary_confidence = await self._normalize_salary(job_posting)
            enrichments[EnrichmentType.SALARY_NORMALIZATION] = salary_info
            confidence_scores[EnrichmentType.SALARY_NORMALIZATION] = salary_confidence
            
            # Standardize location
            location_info, location_confidence = await self._standardize_location(job_posting)
            enrichments[EnrichmentType.LOCATION_STANDARDIZATION] = location_info
            confidence_scores[EnrichmentType.LOCATION_STANDARDIZATION] = location_confidence
            
            # Determine job category
            category, category_confidence = await self._determine_job_category(job_posting)
            enrichments[EnrichmentType.JOB_CATEGORY] = category
            confidence_scores[EnrichmentType.JOB_CATEGORY] = category_confidence
            
            # Determine experience level
            experience, experience_confidence = await self._determine_experience_level(job_posting)
            enrichments[EnrichmentType.EXPERIENCE_LEVEL] = experience
            confidence_scores[EnrichmentType.EXPERIENCE_LEVEL] = experience_confidence
            
            # Detect remote work type
            remote_type, remote_confidence = await self._detect_remote_work_type(job_posting)
            enrichments[EnrichmentType.REMOTE_WORK_TYPE] = remote_type
            confidence_scores[EnrichmentType.REMOTE_WORK_TYPE] = remote_confidence
            
            # Extract benefits
            benefits, benefits_confidence = await self._extract_benefits(job_posting)
            enrichments[EnrichmentType.BENEFITS_EXTRACTION] = benefits
            confidence_scores[EnrichmentType.BENEFITS_EXTRACTION] = benefits_confidence
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return EnrichmentResult(
                job_id=str(job_posting.id),
                enrichments=enrichments,
                confidence_scores=confidence_scores,
                enriched_at=datetime.now(),
                processing_time=processing_time,
                metadata={
                    'job_board': job_posting.job_board,
                    'enrichment_count': len(enrichments)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to enrich job posting {job_posting.id}: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return EnrichmentResult(
                job_id=str(job_posting.id),
                enrichments={},
                confidence_scores={},
                enriched_at=datetime.now(),
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    async def _extract_skills(self, job_posting: JobPosting) -> Tuple[List[str], float]:
        """Extract skills from job posting"""
        try:
            content = ' '.join([
                job_posting.title or '',
                job_posting.description or ''
            ]).lower()
            
            found_skills = []
            
            # Check against known skills
            for category, skills in self.common_skills.items():
                for skill in skills:
                    if skill in content:
                        found_skills.append(skill)
            
            # Remove duplicates and sort
            found_skills = sorted(list(set(found_skills)))
            
            # Calculate confidence based on number of skills found
            confidence = min(1.0, len(found_skills) / 10.0)  # Max confidence at 10+ skills
            
            return found_skills, confidence
            
        except Exception as e:
            logger.error(f"Skill extraction failed: {e}")
            return [], 0.0
    
    async def _normalize_salary(self, job_posting: JobPosting) -> Tuple[Dict[str, Any], float]:
        """Normalize salary information"""
        try:
            if not hasattr(job_posting, 'salary') or not job_posting.salary:
                return {}, 0.0
            
            salary_text = str(job_posting.salary).lower()
            
            # Extract numbers
            numbers = re.findall(r'[\d,]+', salary_text)
            if not numbers:
                return {}, 0.0
            
            amounts = [int(num.replace(',', '')) for num in numbers]
            
            # Determine currency
            currency = 'USD'  # Default
            if '€' in salary_text or 'eur' in salary_text:
                currency = 'EUR'
            elif '£' in salary_text or 'gbp' in salary_text:
                currency = 'GBP'
            
            # Determine period
            period = 'year'  # Default
            if 'hour' in salary_text or '/hr' in salary_text:
                period = 'hour'
            elif 'month' in salary_text or '/mo' in salary_text:
                period = 'month'
            elif 'week' in salary_text or '/wk' in salary_text:
                period = 'week'
            
            # Create normalized salary info
            salary_info = {
                'currency': currency,
                'period': period,
                'min_amount': min(amounts) if amounts else None,
                'max_amount': max(amounts) if len(amounts) > 1 else None,
                'original_text': job_posting.salary
            }
            
            # Calculate confidence
            confidence = 0.8 if len(amounts) >= 2 else 0.6
            
            return salary_info, confidence
            
        except Exception as e:
            logger.error(f"Salary normalization failed: {e}")
            return {}, 0.0
    
    async def _standardize_location(self, job_posting: JobPosting) -> Tuple[Dict[str, Any], float]:
        """Standardize location information"""
        try:
            if not job_posting.location:
                return {}, 0.0
            
            location = job_posting.location.strip()
            
            # Simple location parsing
            parts = [part.strip() for part in location.split(',')]
            
            location_info = {
                'original': location,
                'city': parts[0] if parts else None,
                'state': parts[1] if len(parts) > 1 else None,
                'country': parts[-1] if len(parts) > 2 else None,
                'is_remote': 'remote' in location.lower()
            }
            
            # Calculate confidence based on structure
            confidence = 0.7 if len(parts) >= 2 else 0.5
            
            return location_info, confidence
            
        except Exception as e:
            logger.error(f"Location standardization failed: {e}")
            return {}, 0.0
    
    async def _determine_job_category(self, job_posting: JobPosting) -> Tuple[str, float]:
        """Determine job category"""
        try:
            content = ' '.join([
                job_posting.title or '',
                job_posting.description or ''
            ]).lower()
            
            # Category keywords
            categories = {
                'software_engineering': ['software', 'developer', 'engineer', 'programming', 'coding'],
                'data_science': ['data scientist', 'data analyst', 'machine learning', 'ai', 'analytics'],
                'product_management': ['product manager', 'product owner', 'pm', 'product'],
                'design': ['designer', 'ux', 'ui', 'design', 'creative'],
                'marketing': ['marketing', 'seo', 'social media', 'content', 'brand'],
                'sales': ['sales', 'account manager', 'business development', 'revenue'],
                'operations': ['operations', 'ops', 'logistics', 'supply chain'],
                'finance': ['finance', 'accounting', 'financial', 'cfo', 'analyst'],
                'hr': ['human resources', 'hr', 'recruiter', 'talent', 'people'],
                'customer_support': ['support', 'customer service', 'help desk', 'customer success']
            }
            
            best_category = 'other'
            best_score = 0
            
            for category, keywords in categories.items():
                score = sum(1 for keyword in keywords if keyword in content)
                if score > best_score:
                    best_score = score
                    best_category = category
            
            confidence = min(1.0, best_score / 3.0)  # Max confidence at 3+ keyword matches
            
            return best_category, confidence
            
        except Exception as e:
            logger.error(f"Job category determination failed: {e}")
            return 'other', 0.0
    
    async def _determine_experience_level(self, job_posting: JobPosting) -> Tuple[str, float]:
        """Determine experience level"""
        try:
            content = ' '.join([
                job_posting.title or '',
                job_posting.description or ''
            ]).lower()
            
            # Experience level indicators
            levels = {
                'entry': ['entry', 'junior', 'graduate', 'intern', '0-2 years', 'new grad'],
                'mid': ['mid', 'intermediate', '2-5 years', '3-7 years', 'experienced'],
                'senior': ['senior', 'sr', 'lead', '5+ years', '7+ years', 'expert'],
                'executive': ['director', 'vp', 'cto', 'ceo', 'head of', 'chief']
            }
            
            best_level = 'mid'  # Default
            best_score = 0
            
            for level, keywords in levels.items():
                score = sum(1 for keyword in keywords if keyword in content)
                if score > best_score:
                    best_score = score
                    best_level = level
            
            confidence = min(1.0, best_score / 2.0)  # Max confidence at 2+ keyword matches
            
            return best_level, confidence
            
        except Exception as e:
            logger.error(f"Experience level determination failed: {e}")
            return 'mid', 0.0
    
    async def _detect_remote_work_type(self, job_posting: JobPosting) -> Tuple[str, float]:
        """Detect remote work type"""
        try:
            content = ' '.join([
                job_posting.title or '',
                job_posting.description or '',
                job_posting.location or ''
            ]).lower()
            
            # Remote work indicators
            if any(keyword in content for keyword in ['fully remote', '100% remote', 'remote only']):
                return 'fully_remote', 0.9
            elif any(keyword in content for keyword in ['hybrid', 'flexible', 'remote/office']):
                return 'hybrid', 0.8
            elif any(keyword in content for keyword in ['remote', 'work from home', 'wfh']):
                return 'remote_friendly', 0.7
            else:
                return 'on_site', 0.6
                
        except Exception as e:
            logger.error(f"Remote work type detection failed: {e}")
            return 'on_site', 0.0
    
    async def _extract_benefits(self, job_posting: JobPosting) -> Tuple[List[str], float]:
        """Extract benefits from job posting"""
        try:
            content = ' '.join([
                job_posting.description or ''
            ]).lower()
            
            # Common benefits
            benefit_keywords = {
                'health_insurance': ['health insurance', 'medical', 'dental', 'vision'],
                'retirement': ['401k', 'pension', 'retirement', 'ira'],
                'pto': ['pto', 'vacation', 'paid time off', 'holidays'],
                'flexible_hours': ['flexible hours', 'flex time', 'work life balance'],
                'stock_options': ['stock options', 'equity', 'rsu', 'espp'],
                'professional_development': ['training', 'conference', 'learning', 'development'],
                'gym': ['gym', 'fitness', 'wellness'],
                'food': ['free lunch', 'snacks', 'catered', 'kitchen']
            }
            
            found_benefits = []
            
            for benefit, keywords in benefit_keywords.items():
                if any(keyword in content for keyword in keywords):
                    found_benefits.append(benefit)
            
            confidence = min(1.0, len(found_benefits) / 5.0)  # Max confidence at 5+ benefits
            
            return found_benefits, confidence
            
        except Exception as e:
            logger.error(f"Benefits extraction failed: {e}")
            return [], 0.0
    
    async def batch_validate(self, job_postings: List[JobPosting], max_concurrent: int = 10) -> List[ValidationResult]:
        """Validate multiple job postings concurrently"""
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def validate_single(job_posting: JobPosting) -> ValidationResult:
                async with semaphore:
                    return await self.validate_job_posting(job_posting)
            
            tasks = [validate_single(job) for job in job_postings]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = [r for r in results if isinstance(r, ValidationResult)]
            
            logger.info(f"Batch validation complete: {len(valid_results)}/{len(job_postings)} successful")
            return valid_results
            
        except Exception as e:
            logger.error(f"Batch validation failed: {e}")
            return []
    
    async def batch_enrich(self, job_postings: List[JobPosting], max_concurrent: int = 5) -> List[EnrichmentResult]:
        """Enrich multiple job postings concurrently"""
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def enrich_single(job_posting: JobPosting) -> EnrichmentResult:
                async with semaphore:
                    return await self.enrich_job_posting(job_posting)
            
            tasks = [enrich_single(job) for job in job_postings]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = [r for r in results if isinstance(r, EnrichmentResult)]
            
            logger.info(f"Batch enrichment complete: {len(valid_results)}/{len(job_postings)} successful")
            return valid_results
            
        except Exception as e:
            logger.error(f"Batch enrichment failed: {e}")
            return []

# Global instance
_data_quality_validator = None

async def get_data_quality_validator() -> DataQualityValidator:
    """Get global data quality validator instance"""
    global _data_quality_validator
    if _data_quality_validator is None:
        _data_quality_validator = DataQualityValidator()
        await _data_quality_validator.initialize()
    return _data_quality_validator