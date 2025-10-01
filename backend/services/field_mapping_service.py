from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import re
from datetime import datetime
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation

class FieldType(Enum):
    """Supported field types for mapping"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    URL = "url"
    EMAIL = "email"
    LIST = "list"
    BOOLEAN = "boolean"
    CURRENCY = "currency"

class ExtractionMethod(Enum):
    """Methods for extracting field values"""
    CSS_SELECTOR = "css_selector"
    XPATH = "xpath"
    REGEX = "regex"
    TEXT_CONTAINS = "text_contains"
    ATTRIBUTE = "attribute"
    ML_EXTRACTION = "ml_extraction"

class ValidationRule(Enum):
    """Validation rules for field values"""
    REQUIRED = "required"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    PATTERN = "pattern"
    RANGE = "range"
    ENUM = "enum"
    CUSTOM = "custom"

@dataclass
class FieldExtractor:
    """Configuration for extracting a specific field"""
    method: ExtractionMethod
    selector: str
    attribute: Optional[str] = None
    regex_pattern: Optional[str] = None
    fallback_selectors: Optional[List[str]] = None
    transform_function: Optional[str] = None  # JavaScript-like function for transformation
    priority: int = 1  # Higher priority extractors are tried first

@dataclass
class FieldValidator:
    """Validation configuration for a field"""
    rule: ValidationRule
    value: Any
    error_message: Optional[str] = None
    severity: str = "error"  # error, warning, info

@dataclass
class FieldMapping:
    """Complete field mapping configuration"""
    field_name: str
    field_type: FieldType
    extractors: List[FieldExtractor]
    validators: List[FieldValidator]
    default_value: Any = None
    is_required: bool = True
    weight: float = 1.0  # Importance weight for quality scoring
    description: Optional[str] = None

@dataclass
class MappingTemplate:
    """Template for field mappings for a specific source"""
    name: str
    source: str
    description: str
    field_mappings: Dict[str, FieldMapping]
    created_at: datetime
    updated_at: datetime
    version: str = "1.0"
    is_active: bool = True

class FieldMappingService:
    """Service for managing field mapping configurations"""
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.logger = logging.getLogger(__name__)
        self.db = db
        self._templates = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default field mapping templates"""
        # Indeed template
        indeed_mappings = {
            "title": FieldMapping(
                field_name="title",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector="h1[data-jk] span[title], .jobsearch-JobInfoHeader-title span[title]",
                        priority=1
                    ),
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".jobsearch-JobInfoHeader-title, h1.jobsearch-JobInfoHeader-title",
                        priority=2
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Job title is required"),
                    FieldValidator(ValidationRule.MIN_LENGTH, 3, "Title too short"),
                    FieldValidator(ValidationRule.MAX_LENGTH, 200, "Title too long")
                ],
                weight=1.0,
                description="Job title from Indeed listings"
            ),
            "company": FieldMapping(
                field_name="company",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector="[data-testid='inlineHeader-companyName'] a, .jobsearch-InlineCompanyRating div[data-testid='inlineHeader-companyName']",
                        priority=1
                    ),
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".jobsearch-InlineCompanyRating a span",
                        priority=2
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Company name is required"),
                    FieldValidator(ValidationRule.MIN_LENGTH, 2, "Company name too short")
                ],
                weight=0.9
            ),
            "location": FieldMapping(
                field_name="location",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector="[data-testid='job-location'], .jobsearch-JobInfoHeader-subtitle div",
                        priority=1
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.MIN_LENGTH, 2, "Location too short")
                ],
                weight=0.7
            ),
            "salary": FieldMapping(
                field_name="salary",
                field_type=FieldType.CURRENCY,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".jobsearch-JobMetadataHeader-item span[data-testid='detailText'], .icl-u-xs-mr--xs",
                        regex_pattern=r"\$[\d,]+(?:\.\d{2})?(?:\s*-\s*\$[\d,]+(?:\.\d{2})?)?(?:\s*(?:per|/)?\s*(?:hour|hr|year|yr|month|mo)?)?",
                        priority=1
                    )
                ],
                validators=[],
                is_required=False,
                weight=0.8
            ),
            "description": FieldMapping(
                field_name="description",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector="#jobDescriptionText, .jobsearch-jobDescriptionText",
                        priority=1
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.MIN_LENGTH, 50, "Description too short")
                ],
                weight=0.6
            )
        }
        
        # LinkedIn template
        linkedin_mappings = {
            "title": FieldMapping(
                field_name="title",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".top-card-layout__title, h1.t-24",
                        priority=1
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Job title is required"),
                    FieldValidator(ValidationRule.MIN_LENGTH, 3, "Title too short")
                ],
                weight=1.0
            ),
            "company": FieldMapping(
                field_name="company",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".top-card-layout__card .topcard__org-name-link, .job-details-jobs-unified-top-card__company-name a",
                        priority=1
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Company name is required")
                ],
                weight=0.9
            ),
            "location": FieldMapping(
                field_name="location",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".top-card-layout__card .topcard__flavor--bullet, .job-details-jobs-unified-top-card__bullet",
                        priority=1
                    )
                ],
                validators=[],
                weight=0.7
            )
        }
        
        # Generic template
        generic_mappings = {
            "title": FieldMapping(
                field_name="title",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector="h1, .job-title, .title, [class*='title'], [class*='job-title']",
                        priority=1
                    ),
                    FieldExtractor(
                        method=ExtractionMethod.XPATH,
                        selector="//h1[contains(@class, 'title') or contains(@class, 'job')]//text()",
                        priority=2
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Job title is required")
                ],
                weight=1.0
            ),
            "company": FieldMapping(
                field_name="company",
                field_type=FieldType.TEXT,
                extractors=[
                    FieldExtractor(
                        method=ExtractionMethod.CSS_SELECTOR,
                        selector=".company, .company-name, [class*='company'], [class*='employer']",
                        priority=1
                    )
                ],
                validators=[
                    FieldValidator(ValidationRule.REQUIRED, True, "Company name is required")
                ],
                weight=0.9
            )
        }
        
        # Store templates
        self._templates = {
            "indeed": MappingTemplate(
                name="Indeed Default",
                source="indeed",
                description="Default field mappings for Indeed job listings",
                field_mappings=indeed_mappings,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            "linkedin": MappingTemplate(
                name="LinkedIn Default",
                source="linkedin",
                description="Default field mappings for LinkedIn job listings",
                field_mappings=linkedin_mappings,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            "generic": MappingTemplate(
                name="Generic Default",
                source="generic",
                description="Generic field mappings for any job site",
                field_mappings=generic_mappings,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        }
    
    async def create_field_mapping(self, config_id: str, field_mapping: FieldMapping) -> Dict[str, Any]:
        """Create a new field mapping for a scraper configuration"""
        try:
            # Convert enum values to strings for MongoDB storage
            extractors_data = []
            for extractor in field_mapping.extractors:
                extractor_dict = asdict(extractor)
                extractor_dict['method'] = extractor.method.value
                extractors_data.append(extractor_dict)
            
            validators_data = []
            for validator in field_mapping.validators:
                validator_dict = asdict(validator)
                validator_dict['rule'] = validator.rule.value
                validators_data.append(validator_dict)
            
            mapping_data = {
                'config_id': config_id,
                'field_name': field_mapping.field_name,
                'field_type': field_mapping.field_type.value,
                'extractors': extractors_data,
                'validators': validators_data,
                'default_value': field_mapping.default_value,
                'is_required': field_mapping.is_required,
                'weight': field_mapping.weight,
                'description': field_mapping.description,
                'created_at': datetime.now()
            }
            
            if self.db:
                result = await self.db.field_mappings.insert_one(mapping_data)
                mapping_id = str(result.inserted_id)
            else:
                mapping_id = f"{config_id}_{field_mapping.field_name}"
            
            self.logger.info(f"Created field mapping for config {config_id}: {field_mapping.field_name}")
            return {'success': True, 'mapping_id': mapping_id, 'data': mapping_data}
            
        except Exception as e:
            self.logger.error(f"Error creating field mapping: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def get_field_mappings(self, config_id: str) -> Dict[str, FieldMapping]:
        """Get all field mappings for a scraper configuration"""
        try:
            # Fetch from MongoDB
            if self.db:
                config = await self.db.scraper_configs.find_one({"_id": config_id})
                if config and config.get('source'):
                    source = config['source'].lower()
                    if source in self._templates:
                        return self._templates[source].field_mappings
            
            # Fallback to generic template
            return self._templates["generic"].field_mappings
            
        except Exception as e:
            self.logger.error(f"Error getting field mappings for config {config_id}: {str(e)}")
            return self._templates["generic"].field_mappings
    
    async def update_field_mapping(self, config_id: str, field_name: str, field_mapping: FieldMapping) -> Dict[str, Any]:
        """Update an existing field mapping"""
        try:
            # Convert enum values to strings for MongoDB storage
            extractors_data = []
            for extractor in field_mapping.extractors:
                extractor_dict = asdict(extractor)
                extractor_dict['method'] = extractor.method.value
                extractors_data.append(extractor_dict)
            
            validators_data = []
            for validator in field_mapping.validators:
                validator_dict = asdict(validator)
                validator_dict['rule'] = validator.rule.value
                validators_data.append(validator_dict)
            
            mapping_data = {
                'field_name': field_mapping.field_name,
                'field_type': field_mapping.field_type.value,
                'extractors': extractors_data,
                'validators': validators_data,
                'default_value': field_mapping.default_value,
                'is_required': field_mapping.is_required,
                'weight': field_mapping.weight,
                'description': field_mapping.description,
                'updated_at': datetime.now()
            }
            
            if self.db:
                result = await self.db.field_mappings.update_one(
                    {'config_id': config_id, 'field_name': field_name},
                    {'$set': mapping_data}
                )
                if result.matched_count == 0:
                    return {'success': False, 'error': 'Field mapping not found'}
            
            self.logger.info(f"Updated field mapping for config {config_id}: {field_name}")
            return {'success': True, 'data': mapping_data}
            
        except Exception as e:
            self.logger.error(f"Error updating field mapping: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def delete_field_mapping(self, config_id: str, field_name: str) -> Dict[str, Any]:
        """Delete a field mapping"""
        try:
            if self.db:
                result = await self.db.field_mappings.delete_one(
                    {'config_id': config_id, 'field_name': field_name}
                )
                if result.deleted_count == 0:
                    return {'success': False, 'error': 'Field mapping not found'}
            
            self.logger.info(f"Deleted field mapping for config {config_id}: {field_name}")
            return {'success': True, 'message': f'Field mapping {field_name} deleted successfully'}
            
        except Exception as e:
            self.logger.error(f"Error deleting field mapping: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def validate_field_mapping(self, field_mapping: FieldMapping) -> Dict[str, Any]:
        """Validate a field mapping configuration"""
        issues = []
        
        try:
            # Validate field name
            if not field_mapping.field_name or not field_mapping.field_name.strip():
                issues.append("Field name is required")
            
            # Validate extractors
            if not field_mapping.extractors:
                issues.append("At least one extractor is required")
            else:
                for i, extractor in enumerate(field_mapping.extractors):
                    if not extractor.selector:
                        issues.append(f"Extractor {i+1}: Selector is required")
                    
                    # Validate CSS selectors
                    if extractor.method == ExtractionMethod.CSS_SELECTOR:
                        try:
                            # Basic CSS selector validation
                            if not re.match(r'^[a-zA-Z0-9\s\[\]="\'\-_#.:,>+~*()]+$', extractor.selector):
                                issues.append(f"Extractor {i+1}: Invalid CSS selector format")
                        except Exception:
                            issues.append(f"Extractor {i+1}: Invalid CSS selector")
                    
                    # Validate regex patterns
                    if extractor.method == ExtractionMethod.REGEX and extractor.regex_pattern:
                        try:
                            re.compile(extractor.regex_pattern)
                        except re.error:
                            issues.append(f"Extractor {i+1}: Invalid regex pattern")
            
            # Validate validators
            for i, validator in enumerate(field_mapping.validators):
                if validator.rule == ValidationRule.PATTERN and validator.value:
                    try:
                        re.compile(validator.value)
                    except re.error:
                        issues.append(f"Validator {i+1}: Invalid regex pattern")
                
                if validator.rule == ValidationRule.RANGE and not isinstance(validator.value, (list, tuple)):
                    issues.append(f"Validator {i+1}: Range validator requires list/tuple value")
            
            # Validate weight
            if field_mapping.weight < 0 or field_mapping.weight > 1:
                issues.append("Weight must be between 0 and 1")
            
            return {
                'valid': len(issues) == 0,
                'issues': issues,
                'score': max(0, 1 - (len(issues) * 0.1))  # Quality score
            }
            
        except Exception as e:
            self.logger.error(f"Error validating field mapping: {str(e)}")
            return {'valid': False, 'issues': [f"Validation error: {str(e)}"], 'score': 0}
    
    async def get_template(self, source: str) -> Optional[MappingTemplate]:
        """Get a field mapping template for a specific source"""
        source_key = source.lower()
        return self._templates.get(source_key, self._templates.get("generic"))
    
    async def create_template(self, template: MappingTemplate) -> Dict[str, Any]:
        """Create a new field mapping template"""
        try:
            template_key = template.source.lower()
            self._templates[template_key] = template
            
            self.logger.info(f"Created field mapping template: {template.name}")
            return {'success': True, 'template_id': template_key}
            
        except Exception as e:
            self.logger.error(f"Error creating template: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all available field mapping templates"""
        try:
            templates = []
            for key, template in self._templates.items():
                templates.append({
                    'id': key,
                    'name': template.name,
                    'source': template.source,
                    'description': template.description,
                    'field_count': len(template.field_mappings),
                    'version': template.version,
                    'is_active': template.is_active,
                    'created_at': template.created_at.isoformat(),
                    'updated_at': template.updated_at.isoformat()
                })
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Error listing templates: {str(e)}")
            return []
    
    async def test_field_extraction(self, field_mapping: FieldMapping, html_content: str) -> Dict[str, Any]:
        """Test field extraction with sample HTML content"""
        try:
            from bs4 import BeautifulSoup
            import lxml
            
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            for extractor in sorted(field_mapping.extractors, key=lambda x: x.priority):
                try:
                    extracted_value = None
                    
                    if extractor.method == ExtractionMethod.CSS_SELECTOR:
                        elements = soup.select(extractor.selector)
                        if elements:
                            if extractor.attribute:
                                extracted_value = elements[0].get(extractor.attribute)
                            else:
                                extracted_value = elements[0].get_text(strip=True)
                    
                    elif extractor.method == ExtractionMethod.REGEX and extractor.regex_pattern:
                        matches = re.findall(extractor.regex_pattern, html_content)
                        if matches:
                            extracted_value = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    
                    elif extractor.method == ExtractionMethod.TEXT_CONTAINS:
                        if extractor.selector.lower() in html_content.lower():
                            # Find surrounding text
                            start = html_content.lower().find(extractor.selector.lower())
                            extracted_value = html_content[start:start+100]  # Extract surrounding context
                    
                    results.append({
                        'extractor': asdict(extractor),
                        'extracted_value': extracted_value,
                        'success': extracted_value is not None
                    })
                    
                    # If we found a value, we can stop (unless we want to test all extractors)
                    if extracted_value is not None:
                        break
                        
                except Exception as e:
                    results.append({
                        'extractor': asdict(extractor),
                        'extracted_value': None,
                        'success': False,
                        'error': str(e)
                    })
            
            # Get the best result
            successful_results = [r for r in results if r['success']]
            best_result = successful_results[0] if successful_results else None
            
            return {
                'field_name': field_mapping.field_name,
                'extracted_value': best_result['extracted_value'] if best_result else None,
                'success': best_result is not None,
                'all_results': results,
                'extraction_count': len(successful_results)
            }
            
        except Exception as e:
            self.logger.error(f"Error testing field extraction: {str(e)}")
            return {
                'field_name': field_mapping.field_name,
                'extracted_value': None,
                'success': False,
                'error': str(e)
            }

# Global instance
field_mapping_service = FieldMappingService()