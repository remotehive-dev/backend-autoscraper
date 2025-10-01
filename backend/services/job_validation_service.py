import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# from sqlalchemy.orm import Session  # Using MongoDB instead
from backend.database.database import get_db_session
# TODO: Migrate to MongoDB models - JobPost exists in app.models.mongodb_models, AnalyticsMetrics needs to be created
# from backend.database.models import JobPost, AnalyticsMetrics
from backend.models.mongodb_models import JobPost
# AnalyticsMetrics - needs to be implemented in MongoDB models
from backend.services.ml_parsing_service import ParsedJobData

logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    """Validation issue severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    field: str
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None
    impact_score: float = 0.0  # 0.0 to 1.0, higher means more impact

@dataclass
class ValidationResult:
    """Comprehensive validation result"""
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    completeness_score: float  # 0.0 to 1.0
    accuracy_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    field_scores: Dict[str, float]
    recommendations: List[str]
    metadata: Dict[str, Any]

class JobDataValidator:
    """Comprehensive job data validation and quality assurance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Field validation rules
        self.field_rules = {
            'title': {
                'required': True,
                'min_length': 3,
                'max_length': 200,
                'weight': 0.25,
                'patterns': {
                    'valid': [r'^[A-Za-z0-9\s\-\/\(\)\.,&]+$'],
                    'suspicious': [r'^[A-Z\s]+$', r'\$\d+', r'URGENT', r'IMMEDIATE']
                }
            },
            'company': {
                'required': True,
                'min_length': 2,
                'max_length': 100,
                'weight': 0.20,
                'patterns': {
                    'valid': [r'^[A-Za-z0-9\s\-\.,&\(\)]+$'],
                    'suspicious': [r'^[a-z]+$', r'\d{10,}', r'@']
                }
            },
            'location': {
                'required': True,
                'min_length': 2,
                'max_length': 100,
                'weight': 0.15,
                'patterns': {
                    'valid': [r'^[A-Za-z\s\-,\.]+(?:,\s*[A-Z]{2})?$'],
                    'remote_indicators': [r'(?i)remote', r'(?i)work from home', r'(?i)anywhere']
                }
            },
            'description': {
                'required': False,
                'min_length': 50,
                'max_length': 10000,
                'weight': 0.15,
                'patterns': {
                    'quality_indicators': [r'\b(?:responsibilities|requirements|qualifications|benefits)\b', r'\d+\+?\s*years?']
                }
            },
            'salary_min': {
                'required': False,
                'min_value': 20000,
                'max_value': 1000000,
                'weight': 0.10
            },
            'salary_max': {
                'required': False,
                'min_value': 25000,
                'max_value': 2000000,
                'weight': 0.10
            },
            'job_type': {
                'required': False,
                'valid_values': ['full-time', 'part-time', 'contract', 'temporary', 'internship', 'freelance'],
                'weight': 0.05
            }
        }
        
        # Industry-specific validation rules
        self.industry_rules = {
            'technology': {
                'title_keywords': ['engineer', 'developer', 'programmer', 'architect', 'analyst', 'scientist'],
                'skill_keywords': ['python', 'java', 'javascript', 'react', 'sql', 'aws', 'docker'],
                'salary_ranges': {'min': 60000, 'max': 300000}
            },
            'healthcare': {
                'title_keywords': ['nurse', 'doctor', 'physician', 'therapist', 'technician'],
                'skill_keywords': ['patient care', 'medical', 'clinical', 'healthcare'],
                'salary_ranges': {'min': 40000, 'max': 400000}
            },
            'finance': {
                'title_keywords': ['analyst', 'advisor', 'manager', 'accountant', 'banker'],
                'skill_keywords': ['excel', 'financial', 'accounting', 'investment', 'risk'],
                'salary_ranges': {'min': 50000, 'max': 500000}
            }
        }
        
        # Common data quality issues
        self.quality_patterns = {
            'placeholder_text': [r'lorem ipsum', r'placeholder', r'sample text', r'\[.*\]'],
            'encoding_issues': [r'â€™', r'â€œ', r'â€\x9d', r'Ã¡', r'Ã©'],
            'html_artifacts': [r'<[^>]+>', r'&[a-z]+;', r'\\n', r'\\t'],
            'duplicate_content': [r'(\b\w+\b)(?:\s+\1\b){2,}'],
            'suspicious_urls': [r'bit\.ly', r'tinyurl', r'goo\.gl']
        }
    
    async def validate_job_data(self, job_data: ParsedJobData, config_id: Optional[str] = None) -> ValidationResult:
        """Comprehensive job data validation"""
        issues = []
        field_scores = {}
        recommendations = []
        
        # Validate individual fields
        for field_name, rules in self.field_rules.items():
            field_value = getattr(job_data, field_name, None)
            field_result = await self._validate_field(field_name, field_value, rules)
            
            field_scores[field_name] = field_result['score']
            issues.extend(field_result['issues'])
            recommendations.extend(field_result['recommendations'])
        
        # Cross-field validation
        cross_field_issues = await self._validate_cross_fields(job_data)
        issues.extend(cross_field_issues)
        
        # Industry-specific validation
        industry_issues = await self._validate_industry_context(job_data)
        issues.extend(industry_issues)
        
        # Data quality checks
        quality_issues = await self._validate_data_quality(job_data)
        issues.extend(quality_issues)
        
        # Calculate scores
        completeness_score = self._calculate_completeness_score(job_data, field_scores)
        accuracy_score = self._calculate_accuracy_score(issues)
        quality_score = self._calculate_overall_quality_score(completeness_score, accuracy_score, issues)
        
        # Determine if valid (no critical issues and quality score above threshold)
        is_valid = (
            not any(issue.severity == ValidationSeverity.CRITICAL for issue in issues) and
            quality_score >= 0.6
        )
        
        # Generate additional recommendations
        if quality_score < 0.8:
            recommendations.extend(self._generate_improvement_recommendations(job_data, issues))
        
        # Store validation metrics if config_id provided
        if config_id:
            await self._store_validation_metrics(config_id, quality_score, len(issues), is_valid)
        
        return ValidationResult(
            is_valid=is_valid,
            quality_score=quality_score,
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            issues=issues,
            field_scores=field_scores,
            recommendations=recommendations,
            metadata={
                'total_issues': len(issues),
                'critical_issues': len([i for i in issues if i.severity == ValidationSeverity.CRITICAL]),
                'warning_issues': len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
                'validation_timestamp': datetime.utcnow().isoformat(),
                'config_id': config_id
            }
        )
    
    async def _validate_field(self, field_name: str, field_value: Any, rules: Dict[str, Any]) -> Dict[str, Any]:
        """Validate individual field"""
        issues = []
        recommendations = []
        score = 1.0
        
        # Check if required field is present
        if rules.get('required', False) and not field_value:
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.CRITICAL,
                message=f"Required field '{field_name}' is missing",
                suggestion=f"Ensure {field_name} is extracted from the source",
                impact_score=1.0
            ))
            score = 0.0
        elif not field_value:
            # Optional field is missing
            score = 0.5
        else:
            # Validate field content
            if isinstance(field_value, str):
                score = await self._validate_string_field(field_name, field_value, rules, issues, recommendations)
            elif isinstance(field_value, (int, float)):
                score = await self._validate_numeric_field(field_name, field_value, rules, issues, recommendations)
            elif isinstance(field_value, bool):
                score = 1.0  # Boolean fields are always valid if present
            elif isinstance(field_value, list):
                score = await self._validate_list_field(field_name, field_value, rules, issues, recommendations)
        
        return {
            'score': max(0.0, min(1.0, score)),
            'issues': issues,
            'recommendations': recommendations
        }
    
    async def _validate_string_field(self, field_name: str, value: str, rules: Dict[str, Any], 
                                   issues: List[ValidationIssue], recommendations: List[str]) -> float:
        """Validate string field"""
        score = 1.0
        
        # Length validation
        if 'min_length' in rules and len(value) < rules['min_length']:
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"{field_name} is too short ({len(value)} chars, minimum {rules['min_length']})",
                suggestion=f"Ensure complete {field_name} is extracted",
                impact_score=0.3
            ))
            score -= 0.3
        
        if 'max_length' in rules and len(value) > rules['max_length']:
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"{field_name} is too long ({len(value)} chars, maximum {rules['max_length']})",
                suggestion=f"Truncate or summarize {field_name}",
                impact_score=0.2
            ))
            score -= 0.2
        
        # Pattern validation
        patterns = rules.get('patterns', {})
        
        # Check valid patterns
        if 'valid' in patterns:
            for pattern in patterns['valid']:
                if not re.search(pattern, value):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=f"{field_name} doesn't match expected format",
                        suggestion=f"Verify {field_name} extraction accuracy",
                        impact_score=0.2
                    ))
                    score -= 0.2
                    break
        
        # Check suspicious patterns
        if 'suspicious' in patterns:
            for pattern in patterns['suspicious']:
                if re.search(pattern, value):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=f"{field_name} contains suspicious content",
                        suggestion=f"Review {field_name} for accuracy",
                        impact_score=0.3
                    ))
                    score -= 0.3
                    break
        
        # Check for quality indicators (positive)
        if 'quality_indicators' in patterns:
            quality_found = False
            for pattern in patterns['quality_indicators']:
                if re.search(pattern, value, re.IGNORECASE):
                    quality_found = True
                    break
            
            if field_name == 'description' and not quality_found:
                issues.append(ValidationIssue(
                    field=field_name,
                    severity=ValidationSeverity.INFO,
                    message=f"{field_name} lacks detailed structure",
                    suggestion="Look for more detailed job descriptions",
                    impact_score=0.1
                ))
                score -= 0.1
        
        # Check for remote work indicators
        if field_name == 'location' and 'remote_indicators' in patterns:
            for pattern in patterns['remote_indicators']:
                if re.search(pattern, value, re.IGNORECASE):
                    recommendations.append(f"Consider setting is_remote=True for this job")
                    break
        
        return max(0.0, score)
    
    async def _validate_numeric_field(self, field_name: str, value: float, rules: Dict[str, Any],
                                    issues: List[ValidationIssue], recommendations: List[str]) -> float:
        """Validate numeric field"""
        score = 1.0
        
        # Range validation
        if 'min_value' in rules and value < rules['min_value']:
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"{field_name} is below expected range ({value} < {rules['min_value']})",
                suggestion=f"Verify {field_name} extraction accuracy",
                impact_score=0.4
            ))
            score -= 0.4
        
        if 'max_value' in rules and value > rules['max_value']:
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"{field_name} is above expected range ({value} > {rules['max_value']})",
                suggestion=f"Verify {field_name} extraction accuracy",
                impact_score=0.4
            ))
            score -= 0.4
        
        return max(0.0, score)
    
    async def _validate_list_field(self, field_name: str, value: List[Any], rules: Dict[str, Any],
                                 issues: List[ValidationIssue], recommendations: List[str]) -> float:
        """Validate list field"""
        score = 1.0
        
        if not value:
            score = 0.5
        elif len(value) > 20:  # Too many items might indicate parsing issues
            issues.append(ValidationIssue(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"{field_name} has unusually many items ({len(value)})",
                suggestion=f"Review {field_name} parsing logic",
                impact_score=0.2
            ))
            score -= 0.2
        
        return max(0.0, score)
    
    async def _validate_cross_fields(self, job_data: ParsedJobData) -> List[ValidationIssue]:
        """Validate relationships between fields"""
        issues = []
        
        # Salary range validation
        if job_data.salary_min and job_data.salary_max:
            if job_data.salary_min > job_data.salary_max:
                issues.append(ValidationIssue(
                    field="salary_range",
                    severity=ValidationSeverity.ERROR,
                    message="Minimum salary is greater than maximum salary",
                    suggestion="Swap or correct salary values",
                    impact_score=0.5
                ))
            elif job_data.salary_max - job_data.salary_min > 200000:
                issues.append(ValidationIssue(
                    field="salary_range",
                    severity=ValidationSeverity.WARNING,
                    message="Salary range is unusually wide",
                    suggestion="Verify salary extraction accuracy",
                    impact_score=0.2
                ))
        
        # Remote work consistency
        if job_data.is_remote and job_data.location:
            remote_indicators = ['remote', 'anywhere', 'work from home']
            if not any(indicator in job_data.location.lower() for indicator in remote_indicators):
                issues.append(ValidationIssue(
                    field="remote_consistency",
                    severity=ValidationSeverity.INFO,
                    message="Job marked as remote but location doesn't indicate remote work",
                    suggestion="Verify remote work status",
                    impact_score=0.1
                ))
        
        # Title-description consistency
        if job_data.title and job_data.description:
            title_words = set(job_data.title.lower().split())
            description_words = set(job_data.description.lower().split())
            
            # Check if key title words appear in description
            key_words = [word for word in title_words if len(word) > 3]
            if key_words:
                overlap = len(title_words.intersection(description_words)) / len(key_words)
                if overlap < 0.3:
                    issues.append(ValidationIssue(
                        field="title_description_consistency",
                        severity=ValidationSeverity.INFO,
                        message="Title and description have low content overlap",
                        suggestion="Verify job data extraction accuracy",
                        impact_score=0.1
                    ))
        
        return issues
    
    async def _validate_industry_context(self, job_data: ParsedJobData) -> List[ValidationIssue]:
        """Validate job data against industry-specific rules"""
        issues = []
        
        if not job_data.title:
            return issues
        
        # Detect industry based on title
        detected_industry = None
        title_lower = job_data.title.lower()
        
        for industry, rules in self.industry_rules.items():
            if any(keyword in title_lower for keyword in rules['title_keywords']):
                detected_industry = industry
                break
        
        if detected_industry:
            industry_rules = self.industry_rules[detected_industry]
            
            # Validate salary against industry standards
            if job_data.salary_min or job_data.salary_max:
                salary_to_check = job_data.salary_min or job_data.salary_max
                industry_min = industry_rules['salary_ranges']['min']
                industry_max = industry_rules['salary_ranges']['max']
                
                if salary_to_check < industry_min * 0.7:  # 30% below industry minimum
                    issues.append(ValidationIssue(
                        field="industry_salary",
                        severity=ValidationSeverity.WARNING,
                        message=f"Salary appears low for {detected_industry} industry",
                        suggestion="Verify salary extraction and currency",
                        impact_score=0.3
                    ))
                elif salary_to_check > industry_max * 1.5:  # 50% above industry maximum
                    issues.append(ValidationIssue(
                        field="industry_salary",
                        severity=ValidationSeverity.WARNING,
                        message=f"Salary appears high for {detected_industry} industry",
                        suggestion="Verify salary extraction and currency",
                        impact_score=0.2
                    ))
        
        return issues
    
    async def _validate_data_quality(self, job_data: ParsedJobData) -> List[ValidationIssue]:
        """Check for common data quality issues"""
        issues = []
        
        # Check all string fields for quality issues
        string_fields = ['title', 'company', 'location', 'description']
        
        for field_name in string_fields:
            field_value = getattr(job_data, field_name, None)
            if not field_value or not isinstance(field_value, str):
                continue
            
            # Check for placeholder text
            for pattern in self.quality_patterns['placeholder_text']:
                if re.search(pattern, field_value, re.IGNORECASE):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.ERROR,
                        message=f"{field_name} contains placeholder text",
                        suggestion="Extract actual content instead of placeholders",
                        impact_score=0.8
                    ))
                    break
            
            # Check for encoding issues
            for pattern in self.quality_patterns['encoding_issues']:
                if re.search(pattern, field_value):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=f"{field_name} has encoding issues",
                        suggestion="Fix text encoding during extraction",
                        impact_score=0.4
                    ))
                    break
            
            # Check for HTML artifacts
            for pattern in self.quality_patterns['html_artifacts']:
                if re.search(pattern, field_value):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=f"{field_name} contains HTML artifacts",
                        suggestion="Clean HTML tags during extraction",
                        impact_score=0.3
                    ))
                    break
            
            # Check for duplicate content
            for pattern in self.quality_patterns['duplicate_content']:
                if re.search(pattern, field_value):
                    issues.append(ValidationIssue(
                        field=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=f"{field_name} has duplicate content",
                        suggestion="Remove duplicate text during extraction",
                        impact_score=0.3
                    ))
                    break
        
        # Check for suspicious URLs in application_url
        if job_data.application_url:
            for pattern in self.quality_patterns['suspicious_urls']:
                if re.search(pattern, job_data.application_url):
                    issues.append(ValidationIssue(
                        field="application_url",
                        severity=ValidationSeverity.WARNING,
                        message="Application URL uses URL shortener",
                        suggestion="Extract direct application URLs when possible",
                        impact_score=0.2
                    ))
                    break
        
        return issues
    
    def _calculate_completeness_score(self, job_data: ParsedJobData, field_scores: Dict[str, float]) -> float:
        """Calculate data completeness score"""
        total_weight = 0.0
        weighted_score = 0.0
        
        for field_name, rules in self.field_rules.items():
            weight = rules.get('weight', 0.1)
            score = field_scores.get(field_name, 0.0)
            
            total_weight += weight
            weighted_score += score * weight
        
        return weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _calculate_accuracy_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate data accuracy score based on issues"""
        if not issues:
            return 1.0
        
        total_impact = sum(issue.impact_score for issue in issues)
        max_possible_impact = len(issues) * 1.0  # Maximum impact per issue is 1.0
        
        accuracy_score = 1.0 - (total_impact / max_possible_impact)
        return max(0.0, accuracy_score)
    
    def _calculate_overall_quality_score(self, completeness_score: float, accuracy_score: float, 
                                       issues: List[ValidationIssue]) -> float:
        """Calculate overall quality score"""
        # Base score from completeness and accuracy
        base_score = (completeness_score * 0.6) + (accuracy_score * 0.4)
        
        # Apply penalties for critical issues
        critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        if critical_issues:
            base_score *= 0.5  # 50% penalty for critical issues
        
        # Apply smaller penalties for errors
        error_issues = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        if error_issues:
            penalty = min(0.3, len(error_issues) * 0.1)  # Up to 30% penalty
            base_score *= (1.0 - penalty)
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_improvement_recommendations(self, job_data: ParsedJobData, 
                                            issues: List[ValidationIssue]) -> List[str]:
        """Generate recommendations for improving data quality"""
        recommendations = []
        
        # Group issues by severity
        critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        error_issues = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warning_issues = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        
        if critical_issues:
            recommendations.append("Address critical data issues before processing")
        
        if error_issues:
            recommendations.append("Fix data extraction errors to improve quality")
        
        if len(warning_issues) > 5:
            recommendations.append("Review extraction logic to reduce data quality warnings")
        
        # Field-specific recommendations
        if not job_data.description or len(job_data.description) < 100:
            recommendations.append("Extract more detailed job descriptions when available")
        
        if not job_data.salary_min and not job_data.salary_max:
            recommendations.append("Improve salary extraction to capture compensation information")
        
        if not job_data.requirements:
            recommendations.append("Extract job requirements and qualifications when available")
        
        return recommendations
    
    async def _store_validation_metrics(self, config_id: str, quality_score: float, 
                                      issue_count: int, is_valid: bool):
        """Store validation metrics for analytics"""
        try:
            db = next(get_db_session())
            
            metrics = AnalyticsMetrics(
                scraper_config_id=config_id,
                metric_name="job_validation_quality",
                metric_value=quality_score,
                metric_data={
                    'issue_count': issue_count,
                    'is_valid': is_valid,
                    'validation_timestamp': datetime.utcnow().isoformat()
                },
                created_at=datetime.utcnow()
            )
            
            db.add(metrics)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Error storing validation metrics: {e}")
    
    async def validate_job_batch(self, jobs: List[ParsedJobData], 
                               config_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate a batch of jobs and return aggregate statistics"""
        results = []
        total_quality_score = 0.0
        valid_jobs = 0
        
        for job in jobs:
            result = await self.validate_job_data(job, config_id)
            results.append(result)
            total_quality_score += result.quality_score
            if result.is_valid:
                valid_jobs += 1
        
        avg_quality_score = total_quality_score / len(jobs) if jobs else 0.0
        validation_rate = valid_jobs / len(jobs) if jobs else 0.0
        
        # Aggregate issues by severity
        all_issues = []
        for result in results:
            all_issues.extend(result.issues)
        
        issue_summary = {
            'critical': len([i for i in all_issues if i.severity == ValidationSeverity.CRITICAL]),
            'error': len([i for i in all_issues if i.severity == ValidationSeverity.ERROR]),
            'warning': len([i for i in all_issues if i.severity == ValidationSeverity.WARNING]),
            'info': len([i for i in all_issues if i.severity == ValidationSeverity.INFO])
        }
        
        return {
            'total_jobs': len(jobs),
            'valid_jobs': valid_jobs,
            'validation_rate': validation_rate,
            'avg_quality_score': avg_quality_score,
            'issue_summary': issue_summary,
            'individual_results': results
        }
    
    async def get_validation_statistics(self, config_id: str, 
                                      days: int = 7) -> Dict[str, Any]:
        """Get validation statistics for a scraper configuration"""
        try:
            db = next(get_db_session())
            
            # Get validation metrics from the last N days
            since_date = datetime.utcnow() - timedelta(days=days)
            
            metrics = db.query(AnalyticsMetrics).filter(
                AnalyticsMetrics.scraper_config_id == config_id,
                AnalyticsMetrics.metric_name == "job_validation_quality",
                AnalyticsMetrics.created_at >= since_date
            ).all()
            
            if not metrics:
                return {
                    'config_id': config_id,
                    'period_days': days,
                    'total_validations': 0,
                    'avg_quality_score': 0.0,
                    'validation_rate': 0.0
                }
            
            total_validations = len(metrics)
            avg_quality_score = sum(m.metric_value for m in metrics) / total_validations
            valid_jobs = sum(1 for m in metrics if m.metric_data.get('is_valid', False))
            validation_rate = valid_jobs / total_validations
            
            return {
                'config_id': config_id,
                'period_days': days,
                'total_validations': total_validations,
                'avg_quality_score': avg_quality_score,
                'validation_rate': validation_rate,
                'quality_trend': [m.metric_value for m in metrics[-10:]]  # Last 10 scores
            }
            
        except Exception as e:
            self.logger.error(f"Error getting validation statistics: {e}")
            return {
                'config_id': config_id,
                'error': str(e)
            }

# Global job data validator instance
job_validator = JobDataValidator()