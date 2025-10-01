import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.core.database import get_db
from backend.models.ml_parsing_config import MLParsingConfig
from backend.models.scraper_config import ScraperConfig
from backend.models.analytics_metrics import AnalyticsMetrics
# from bson import ObjectId  # Removed to fix Pydantic schema generation
from core.config import settings

logger = logging.getLogger(__name__)

class MLConfigStatus(Enum):
    """ML configuration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"

@dataclass
class FieldMappingRule:
    """Field mapping configuration"""
    source_field: str
    target_field: str
    extraction_pattern: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = None
    transformation_rules: Optional[Dict[str, Any]] = None
    priority: int = 1  # Higher priority rules are applied first
    is_required: bool = False

@dataclass
class MLConfigTemplate:
    """ML configuration template"""
    name: str
    description: str
    field_mappings: List[FieldMappingRule]
    confidence_threshold: float
    gemini_settings: Dict[str, Any]
    validation_rules: Dict[str, Any]
    industry_specific: bool = False
    target_industries: List[str] = None

class MLConfigurationService:
    """Service for managing ML parsing configurations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Default field mappings for different job sources
        self.default_field_mappings = {
            'indeed': [
                FieldMappingRule('h1[data-jk]', 'title', priority=1, is_required=True),
                FieldMappingRule('.companyName', 'company', priority=1, is_required=True),
                FieldMappingRule('.companyLocation', 'location', priority=1, is_required=True),
                FieldMappingRule('.salary-snippet', 'salary', priority=2),
                FieldMappingRule('.jobsearch-JobComponent-description', 'description', priority=1),
                FieldMappingRule('.jobMetadataHeader-item', 'job_type', priority=2)
            ],
            'linkedin': [
                FieldMappingRule('.top-card-layout__title', 'title', priority=1, is_required=True),
                FieldMappingRule('.topcard__org-name-link', 'company', priority=1, is_required=True),
                FieldMappingRule('.topcard__flavor--bullet', 'location', priority=1, is_required=True),
                FieldMappingRule('.compensation__salary', 'salary', priority=2),
                FieldMappingRule('.show-more-less-html__markup', 'description', priority=1),
                FieldMappingRule('.description__job-criteria-text', 'job_type', priority=2)
            ],
            'glassdoor': [
                FieldMappingRule('[data-test="job-title"]', 'title', priority=1, is_required=True),
                FieldMappingRule('[data-test="employer-name"]', 'company', priority=1, is_required=True),
                FieldMappingRule('[data-test="job-location"]', 'location', priority=1, is_required=True),
                FieldMappingRule('[data-test="detailSalary"]', 'salary', priority=2),
                FieldMappingRule('.jobDescriptionContent', 'description', priority=1),
                FieldMappingRule('.jobDetailsHeader', 'job_type', priority=2)
            ],
            'generic': [
                FieldMappingRule('title, h1, .title, .job-title', 'title', priority=1, is_required=True),
                FieldMappingRule('.company, .employer, .company-name', 'company', priority=1, is_required=True),
                FieldMappingRule('.location, .job-location', 'location', priority=1, is_required=True),
                FieldMappingRule('.salary, .compensation, .pay', 'salary', priority=2),
                FieldMappingRule('.description, .job-description', 'description', priority=1),
                FieldMappingRule('.job-type, .employment-type', 'job_type', priority=2)
            ]
        }
        
        # Industry-specific configuration templates
        self.industry_templates = {
            'technology': MLConfigTemplate(
                name="Technology Jobs",
                description="Optimized for tech industry job postings",
                field_mappings=[
                    FieldMappingRule('skills', 'technical_skills', priority=1),
                    FieldMappingRule('experience', 'experience_level', priority=1),
                    FieldMappingRule('remote', 'is_remote', priority=1)
                ],
                confidence_threshold=0.75,
                gemini_settings={
                    'temperature': 0.3,
                    'max_tokens': 2048,
                    'focus_areas': ['technical_skills', 'experience_requirements', 'tech_stack']
                },
                validation_rules={
                    'required_fields': ['title', 'company', 'technical_skills'],
                    'salary_range': {'min': 50000, 'max': 400000}
                },
                industry_specific=True,
                target_industries=['software', 'technology', 'engineering']
            ),
            'healthcare': MLConfigTemplate(
                name="Healthcare Jobs",
                description="Optimized for healthcare industry job postings",
                field_mappings=[
                    FieldMappingRule('certifications', 'required_certifications', priority=1),
                    FieldMappingRule('license', 'license_requirements', priority=1),
                    FieldMappingRule('shift', 'work_schedule', priority=2)
                ],
                confidence_threshold=0.8,
                gemini_settings={
                    'temperature': 0.2,
                    'max_tokens': 1536,
                    'focus_areas': ['certifications', 'patient_care', 'medical_specialties']
                },
                validation_rules={
                    'required_fields': ['title', 'company', 'license_requirements'],
                    'salary_range': {'min': 40000, 'max': 300000}
                },
                industry_specific=True,
                target_industries=['healthcare', 'medical', 'nursing']
            ),
            'finance': MLConfigTemplate(
                name="Finance Jobs",
                description="Optimized for finance industry job postings",
                field_mappings=[
                    FieldMappingRule('qualifications', 'financial_qualifications', priority=1),
                    FieldMappingRule('regulations', 'compliance_requirements', priority=1),
                    FieldMappingRule('analysis', 'analytical_skills', priority=2)
                ],
                confidence_threshold=0.8,
                gemini_settings={
                    'temperature': 0.25,
                    'max_tokens': 1792,
                    'focus_areas': ['financial_analysis', 'compliance', 'certifications']
                },
                validation_rules={
                    'required_fields': ['title', 'company', 'financial_qualifications'],
                    'salary_range': {'min': 45000, 'max': 500000}
                },
                industry_specific=True,
                target_industries=['finance', 'banking', 'investment']
            )
        }
    
    async def create_ml_config(self, scraper_config_id: str, 
                             config_data: Dict[str, Any], db: AsyncIOMotorDatabase) -> MLParsingConfig:
        """Create new ML parsing configuration"""
        try:
            # Validate scraper config exists
            scraper_config = await db.scraper_configs.find_one(
                {"_id": scraper_config_id}
            )
            
            if not scraper_config:
                raise ValueError(f"Scraper configuration {scraper_config_id} not found")
            
            # Apply default mappings based on source
            source = scraper_config.source.lower()
            default_mappings = self.default_field_mappings.get(source, 
                                                              self.default_field_mappings['generic'])
            
            # Merge with provided field mappings
            field_mappings = config_data.get('field_mappings', [])
            if not field_mappings:
                field_mappings = [asdict(mapping) for mapping in default_mappings]
            
            # Apply industry template if specified
            industry = config_data.get('industry')
            if industry and industry in self.industry_templates:
                template = self.industry_templates[industry]
                field_mappings.extend([asdict(mapping) for mapping in template.field_mappings])
                
                # Use template settings as defaults
                config_data.setdefault('confidence_threshold', template.confidence_threshold)
                config_data.setdefault('gemini_settings', template.gemini_settings)
                config_data.setdefault('validation_rules', template.validation_rules)
            
            # Create ML config document
            ml_config_data = {
                "scraper_config_id": scraper_config_id,
                "gemini_api_enabled": config_data.get('gemini_api_enabled', True),
                "confidence_threshold": config_data.get('confidence_threshold', 0.7),
                "field_mappings": field_mappings,
                "custom_prompts": config_data.get('custom_prompts', {}),
                "validation_rules": config_data.get('validation_rules', {}),
                "fallback_enabled": config_data.get('fallback_enabled', True),
                "retry_attempts": config_data.get('retry_attempts', 3),
                "timeout_seconds": config_data.get('timeout_seconds', 30),
                "status": config_data.get('status', MLConfigStatus.ACTIVE.value),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db.ml_parsing_configs.insert_one(ml_config_data)
            ml_config_data["_id"] = result.inserted_id
            ml_config = MLParsingConfig(**ml_config_data)
            
            # Log configuration creation
            await self._log_config_event(
                scraper_config_id, "ML_CONFIG_CREATED",
                f"ML parsing configuration created with {len(field_mappings)} field mappings",
                {'config_id': str(ml_config_data["_id"]), 'industry': industry}, db
            )
            
            return ml_config
            
        except Exception as e:
            self.logger.error(f"Error creating ML config: {e}")
            raise
    
    async def update_ml_config(self, config_id: str, 
                             updates: Dict[str, Any], db: AsyncIOMotorDatabase) -> MLParsingConfig:
        """Update existing ML parsing configuration"""
        try:
            ml_config = await db.ml_parsing_configs.find_one(
                {"_id": config_id}
            )
            
            if not ml_config:
                raise ValueError(f"ML configuration {config_id} not found")
            
            # Update fields
            update_data = {}
            for field, value in updates.items():
                update_data[field] = value
            
            update_data["updated_at"] = datetime.utcnow()
            
            await db.ml_parsing_configs.update_one(
                {"_id": config_id},
                {"$set": update_data}
            )
            
            # Get updated document
            updated_config = await db.ml_parsing_configs.find_one(
                {"_id": config_id}
            )
            
            # Log configuration update
            await self._log_config_event(
                updated_config["scraper_config_id"], "ML_CONFIG_UPDATED",
                f"ML parsing configuration updated",
                {'config_id': config_id, 'updated_fields': list(updates.keys())}, db
            )
            
            return MLParsingConfig(**updated_config)
            
        except Exception as e:
            self.logger.error(f"Error updating ML config: {e}")
            raise
    
    async def get_ml_config(self, scraper_config_id: str, db: AsyncIOMotorDatabase) -> Optional[MLParsingConfig]:
        """Get ML parsing configuration for scraper"""
        try:
            config_data = await db.ml_parsing_configs.find_one({
                "scraper_config_id": scraper_config_id,
                "status": MLConfigStatus.ACTIVE.value
            })
            
            if config_data:
                return MLParsingConfig(**config_data)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting ML config: {e}")
            return None
    
    async def validate_ml_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate ML configuration data"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        # Validate confidence threshold
        confidence_threshold = config_data.get('confidence_threshold', 0.7)
        if not 0.0 <= confidence_threshold <= 1.0:
            validation_result['errors'].append(
                "Confidence threshold must be between 0.0 and 1.0"
            )
            validation_result['is_valid'] = False
        elif confidence_threshold < 0.5:
            validation_result['warnings'].append(
                "Low confidence threshold may result in poor quality data"
            )
        
        # Validate field mappings
        field_mappings = config_data.get('field_mappings', [])
        if not field_mappings:
            validation_result['warnings'].append(
                "No field mappings specified, will use defaults"
            )
        else:
            required_fields = ['title', 'company']
            mapped_fields = [mapping.get('target_field') for mapping in field_mappings]
            
            for required_field in required_fields:
                if required_field not in mapped_fields:
                    validation_result['warnings'].append(
                        f"Required field '{required_field}' not mapped"
                    )
        
        # Validate Gemini settings
        gemini_settings = config_data.get('gemini_settings', {})
        if gemini_settings:
            temperature = gemini_settings.get('temperature', 0.3)
            if not 0.0 <= temperature <= 1.0:
                validation_result['errors'].append(
                    "Gemini temperature must be between 0.0 and 1.0"
                )
                validation_result['is_valid'] = False
            
            max_tokens = gemini_settings.get('max_tokens', 2048)
            if max_tokens > 4096:
                validation_result['warnings'].append(
                    "High max_tokens setting may increase API costs"
                )
        
        # Validate retry settings
        retry_attempts = config_data.get('retry_attempts', 3)
        if retry_attempts > 5:
            validation_result['warnings'].append(
                "High retry attempts may slow down scraping"
            )
        
        timeout_seconds = config_data.get('timeout_seconds', 30)
        if timeout_seconds > 60:
            validation_result['warnings'].append(
                "High timeout may slow down scraping process"
            )
        
        # Generate suggestions
        if confidence_threshold > 0.9:
            validation_result['suggestions'].append(
                "Consider lowering confidence threshold to capture more data"
            )
        
        if not config_data.get('fallback_enabled', True):
            validation_result['suggestions'].append(
                "Enable fallback parsing to ensure data extraction when ML fails"
            )
        
        return validation_result
    
    async def get_field_mapping_suggestions(self, scraper_config_id: str, 
                                          sample_html: str) -> List[Dict[str, Any]]:
        """Generate field mapping suggestions based on HTML analysis"""
        try:
            # Analyze HTML structure to suggest field mappings
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(sample_html, 'html.parser')
            suggestions = []
            
            # Common patterns for job fields
            field_patterns = {
                'title': [
                    {'selector': 'h1', 'confidence': 0.9},
                    {'selector': '.job-title, .title', 'confidence': 0.8},
                    {'selector': '[data-testid*="title"]', 'confidence': 0.7},
                    {'selector': '.position, .role', 'confidence': 0.6}
                ],
                'company': [
                    {'selector': '.company, .employer', 'confidence': 0.9},
                    {'selector': '[data-testid*="company"]', 'confidence': 0.8},
                    {'selector': '.org, .organization', 'confidence': 0.7}
                ],
                'location': [
                    {'selector': '.location, .job-location', 'confidence': 0.9},
                    {'selector': '[data-testid*="location"]', 'confidence': 0.8},
                    {'selector': '.address, .city', 'confidence': 0.7}
                ],
                'salary': [
                    {'selector': '.salary, .compensation', 'confidence': 0.9},
                    {'selector': '[data-testid*="salary"]', 'confidence': 0.8},
                    {'selector': '.pay, .wage', 'confidence': 0.7}
                ],
                'description': [
                    {'selector': '.description, .job-description', 'confidence': 0.9},
                    {'selector': '[data-testid*="description"]', 'confidence': 0.8},
                    {'selector': '.content, .details', 'confidence': 0.7}
                ]
            }
            
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    elements = soup.select(pattern['selector'])
                    if elements:
                        suggestions.append({
                            'target_field': field,
                            'source_selector': pattern['selector'],
                            'confidence': pattern['confidence'],
                            'sample_content': elements[0].get_text()[:100] if elements[0].get_text() else None,
                            'element_count': len(elements)
                        })
                        break  # Use first matching pattern
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error generating field mapping suggestions: {e}")
            return []
    
    async def test_ml_config(self, config_id: str, 
                           sample_data: List[str], db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Test ML configuration with sample data"""
        try:
            ml_config = await db.ml_parsing_configs.find_one(
                {"_id": config_id}
            )
            
            if not ml_config:
                raise ValueError(f"ML configuration {config_id} not found")
            
            # Import ML parsing service for testing
            from services.ml_parsing_service import ml_parsing_service
            
            test_results = {
                'config_id': config_id,
                'total_samples': len(sample_data),
                'successful_parses': 0,
                'failed_parses': 0,
                'avg_confidence': 0.0,
                'confidence_scores': [],
                'parsing_times': [],
                'sample_results': []
            }
            
            for i, html_sample in enumerate(sample_data[:5]):  # Test max 5 samples
                try:
                    start_time = datetime.utcnow()
                    
                    # Parse using ML service
                    parsed_job = await ml_parsing_service.parse_job_data(
                        html_sample, ml_config["scraper_config_id"], 
                        ml_config["confidence_threshold"]
                    )
                    
                    parsing_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    test_results['successful_parses'] += 1
                    test_results['confidence_scores'].append(parsed_job.confidence_score)
                    test_results['parsing_times'].append(parsing_time)
                    
                    test_results['sample_results'].append({
                        'sample_index': i,
                        'success': True,
                        'confidence_score': parsed_job.confidence_score,
                        'parsing_time': parsing_time,
                        'extracted_fields': {
                            'title': parsed_job.title,
                            'company': parsed_job.company,
                            'location': parsed_job.location,
                            'has_salary': bool(parsed_job.salary_min or parsed_job.salary_max)
                        }
                    })
                    
                except Exception as parse_error:
                    test_results['failed_parses'] += 1
                    test_results['sample_results'].append({
                        'sample_index': i,
                        'success': False,
                        'error': str(parse_error)
                    })
            
            # Calculate averages
            if test_results['confidence_scores']:
                test_results['avg_confidence'] = (
                    sum(test_results['confidence_scores']) / 
                    len(test_results['confidence_scores'])
                )
            
            if test_results['parsing_times']:
                test_results['avg_parsing_time'] = (
                    sum(test_results['parsing_times']) / 
                    len(test_results['parsing_times'])
                )
            
            test_results['success_rate'] = (
                test_results['successful_parses'] / test_results['total_samples']
            )
            
            # Store test results
            await self._store_test_results(config_id, test_results, db)
            
            return test_results
            
        except Exception as e:
            self.logger.error(f"Error testing ML config: {e}")
            raise
    
    async def get_config_performance_metrics(self, config_id: str, 
                                           days: int = 7, db: AsyncIOMotorDatabase = None) -> Dict[str, Any]:
        """Get performance metrics for ML configuration"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get ML parsing config first
            ml_config = await db.ml_parsing_configs.find_one(
                {"_id": config_id}
            )
            
            if not ml_config:
                return {'config_id': config_id, 'error': 'Configuration not found'}
            
            # Get ML parsing metrics
            metrics = await db.analytics_metrics.find({
                "scraper_config_id": ml_config["scraper_config_id"],
                "metric_name": {
                    "$in": ['ml_parsing_confidence', 'ml_parsing_success_rate', 'ml_parsing_time']
                },
                "created_at": {"$gte": since_date}
            }).to_list(length=None)
            
            if not metrics:
                return {
                    'config_id': config_id,
                    'period_days': days,
                    'no_data': True
                }
            
            # Group metrics by type
            confidence_metrics = [m for m in metrics if m["metric_name"] == 'ml_parsing_confidence']
            success_metrics = [m for m in metrics if m["metric_name"] == 'ml_parsing_success_rate']
            time_metrics = [m for m in metrics if m["metric_name"] == 'ml_parsing_time']
            
            result = {
                'config_id': config_id,
                'period_days': days,
                'total_parsing_sessions': len(metrics)
            }
            
            if confidence_metrics:
                result['avg_confidence'] = sum(m["metric_value"] for m in confidence_metrics) / len(confidence_metrics)
                result['confidence_trend'] = [m["metric_value"] for m in confidence_metrics[-10:]]
            
            if success_metrics:
                result['avg_success_rate'] = sum(m["metric_value"] for m in success_metrics) / len(success_metrics)
            
            if time_metrics:
                result['avg_parsing_time'] = sum(m["metric_value"] for m in time_metrics) / len(time_metrics)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting config performance metrics: {e}")
            return {'config_id': config_id, 'error': str(e)}
    
    async def clone_ml_config(self, source_config_id: str, 
                            target_scraper_config_id: str,
                            modifications: Optional[Dict[str, Any]] = None, 
                            db: AsyncIOMotorDatabase = None) -> MLParsingConfig:
        """Clone ML configuration to another scraper"""
        try:
            source_config = await db.ml_parsing_configs.find_one(
                {"_id": source_config_id}
            )
            
            if not source_config:
                raise ValueError(f"Source ML configuration {source_config_id} not found")
            
            # Create new config with cloned settings
            cloned_data = {
                'gemini_api_enabled': source_config["gemini_api_enabled"],
                'confidence_threshold': source_config["confidence_threshold"],
                'field_mappings': source_config["field_mappings"],
                'custom_prompts': source_config["custom_prompts"],
                'validation_rules': source_config["validation_rules"],
                'fallback_enabled': source_config["fallback_enabled"],
                'retry_attempts': source_config["retry_attempts"],
                'timeout_seconds': source_config["timeout_seconds"]
            }
            
            # Apply modifications if provided
            if modifications:
                cloned_data.update(modifications)
            
            # Create new ML config
            new_config = await self.create_ml_config(target_scraper_config_id, cloned_data, db)
            
            # Log cloning
            await self._log_config_event(
                target_scraper_config_id, "ML_CONFIG_CLONED",
                f"ML configuration cloned from {source_config_id}",
                {'source_config_id': source_config_id, 'new_config_id': str(new_config._id)}, db
            )
            
            return new_config
            
        except Exception as e:
            self.logger.error(f"Error cloning ML config: {e}")
            raise
    
    async def _log_config_event(self, scraper_config_id: str, event_type: str, 
                              message: str, metadata: Dict[str, Any], db: AsyncIOMotorDatabase):
        """Log ML configuration events"""
        try:
            log_entry_data = {
                "scraper_config_id": scraper_config_id,
                "status": event_type,
                "message": message,
                "metadata": metadata,
                "created_at": datetime.utcnow()
            }
            
            await db.scraper_logs.insert_one(log_entry_data)
            
        except Exception as e:
            self.logger.error(f"Error logging config event: {e}")
    
    async def _store_test_results(self, config_id: str, test_results: Dict[str, Any], db: AsyncIOMotorDatabase):
        """Store ML configuration test results"""
        try:
            # Get scraper config ID
            ml_config = await db.ml_parsing_configs.find_one(
                {"_id": config_id}
            )
            
            if ml_config:
                metrics_data = {
                    "scraper_config_id": ml_config["scraper_config_id"],
                    "metric_name": "ml_config_test_results",
                    "metric_value": test_results['success_rate'],
                    "metric_data": test_results,
                    "created_at": datetime.utcnow()
                }
                
                await db.analytics_metrics.insert_one(metrics_data)
            
        except Exception as e:
            self.logger.error(f"Error storing test results: {e}")
    
    def get_available_templates(self) -> Dict[str, MLConfigTemplate]:
        """Get available ML configuration templates"""
        return self.industry_templates
    
    def get_default_field_mappings(self, source: str) -> List[FieldMappingRule]:
        """Get default field mappings for a source"""
        source_key = source.lower() if source else 'generic'
        return self.default_field_mappings.get(source_key, self.default_field_mappings['generic'])

# Global ML configuration service instance
ml_config_service = MLConfigurationService()