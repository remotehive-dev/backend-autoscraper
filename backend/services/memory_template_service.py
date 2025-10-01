from typing import Dict, List
import csv
import io
from datetime import datetime

class MemoryTemplateService:
    """
    Service for generating CSV templates for memory uploads.
    Supports website patterns, scraping rules, and content templates.
    """
    
    def __init__(self):
        # Define template structures for each memory type
        self.templates = {
            "website_patterns": {
                "filename": "website_patterns_template.csv",
                "headers": [
                    "website_url",
                    "pattern_name", 
                    "content_type",
                    "css_selector",
                    "xpath_selector",
                    "extraction_rules",
                    "priority",
                    "active"
                ],
                "sample_data": [
                    {
                        "website_url": "https://example-jobboard.com",
                        "pattern_name": "Job Title Extraction",
                        "content_type": "job_title",
                        "css_selector": ".job-title h1",
                        "xpath_selector": "//h1[@class='job-title']/text()",
                        "extraction_rules": "trim|lowercase",
                        "priority": "high",
                        "active": "true"
                    },
                    {
                        "website_url": "https://another-site.com",
                        "pattern_name": "Company Name Pattern",
                        "content_type": "company_name",
                        "css_selector": ".company-info .name",
                        "xpath_selector": "//div[@class='company-info']//span[@class='name']/text()",
                        "extraction_rules": "trim",
                        "priority": "medium",
                        "active": "true"
                    }
                ]
            },
            "scraping_rules": {
                "filename": "scraping_rules_template.csv",
                "headers": [
                    "rule_name",
                    "target_field",
                    "css_selector",
                    "xpath_selector",
                    "regex_pattern",
                    "validation_rule",
                    "fallback_selector",
                    "confidence_threshold"
                ],
                "sample_data": [
                    {
                        "rule_name": "Extract Job Description",
                        "target_field": "job_description",
                        "css_selector": ".job-description p",
                        "xpath_selector": "//div[@class='job-description']//p/text()",
                        "regex_pattern": r"\b[A-Za-z\s]{10,}\b",
                        "validation_rule": "min_length:50",
                        "fallback_selector": ".description, .job-details",
                        "confidence_threshold": "0.8"
                    },
                    {
                        "rule_name": "Extract Salary Range",
                        "target_field": "salary_range",
                        "css_selector": ".salary-info",
                        "xpath_selector": "//span[@class='salary']/text()",
                        "regex_pattern": r"\$[\d,]+\s*-\s*\$[\d,]+",
                        "validation_rule": "contains:$",
                        "fallback_selector": ".compensation, .pay-range",
                        "confidence_threshold": "0.9"
                    }
                ]
            },
            "content_templates": {
                "filename": "content_templates_template.csv",
                "headers": [
                    "template_name",
                    "content_type",
                    "template_structure",
                    "required_fields",
                    "optional_fields",
                    "validation_schema",
                    "ml_enhancement"
                ],
                "sample_data": [
                    {
                        "template_name": "Standard Job Posting",
                        "content_type": "job_posting",
                        "template_structure": "title|company|location|description|requirements|salary",
                        "required_fields": "title,company,description",
                        "optional_fields": "location,requirements,salary,benefits",
                        "validation_schema": '{"title":{"min_length":5},"description":{"min_length":50}}',
                        "ml_enhancement": "true"
                    },
                    {
                        "template_name": "Company Profile",
                        "content_type": "company_profile",
                        "template_structure": "name|industry|size|location|description|website",
                        "required_fields": "name,industry",
                        "optional_fields": "size,location,description,website,founded",
                        "validation_schema": '{"name":{"min_length":2},"industry":{"enum":["tech","finance","healthcare"]}}',
                        "ml_enhancement": "false"
                    }
                ]
            }
        }
    
    def generate_template(self, memory_type: str, include_sample_data: bool = True) -> str:
        """
        Generate CSV template for the specified memory type.
        
        Args:
            memory_type: Type of memory template to generate
            include_sample_data: Whether to include sample rows
        
        Returns:
            CSV content as string
        """
        if memory_type not in self.templates:
            raise ValueError(f"Unknown memory type: {memory_type}")
        
        template = self.templates[memory_type]
        headers = template["headers"]
        sample_data = template["sample_data"] if include_sample_data else []
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        
        # Write headers
        writer.writeheader()
        
        # Write sample data if requested
        if include_sample_data:
            for row in sample_data:
                # Ensure all headers are present in the row
                complete_row = {header: row.get(header, "") for header in headers}
                writer.writerow(complete_row)
        
        return output.getvalue()
    
    def get_template_filename(self, memory_type: str) -> str:
        """
        Get the suggested filename for a memory type template.
        
        Args:
            memory_type: Type of memory template
        
        Returns:
            Suggested filename
        """
        if memory_type not in self.templates:
            raise ValueError(f"Unknown memory type: {memory_type}")
        
        return self.templates[memory_type]["filename"]
    
    def get_template_info(self, memory_type: str) -> Dict:
        """
        Get information about a template including headers and descriptions.
        
        Args:
            memory_type: Type of memory template
        
        Returns:
            Dictionary with template information
        """
        if memory_type not in self.templates:
            raise ValueError(f"Unknown memory type: {memory_type}")
        
        template = self.templates[memory_type]
        
        # Field descriptions for each memory type
        field_descriptions = {
            "website_patterns": {
                "website_url": "Full URL of the target website (required)",
                "pattern_name": "Descriptive name for this pattern (required)",
                "content_type": "Type of content to extract (e.g., job_title, company_name) (required)",
                "css_selector": "CSS selector for content extraction (optional if xpath_selector provided)",
                "xpath_selector": "XPath selector for content extraction (optional if css_selector provided)",
                "extraction_rules": "Processing rules (e.g., trim, lowercase, remove_html) (optional)",
                "priority": "Extraction priority: low, medium, high (optional, default: medium)",
                "active": "Whether this pattern is active: true/false (optional, default: true)"
            },
            "scraping_rules": {
                "rule_name": "Descriptive name for this scraping rule (required)",
                "target_field": "Database field to populate with extracted data (required)",
                "css_selector": "CSS selector for data extraction (required if no xpath_selector)",
                "xpath_selector": "XPath selector for data extraction (optional)",
                "regex_pattern": "Regular expression for data validation/extraction (optional)",
                "validation_rule": "Validation rules (e.g., min_length:10, contains:$) (optional)",
                "fallback_selector": "Alternative selectors if primary fails (optional)",
                "confidence_threshold": "ML confidence threshold (0.0-1.0) (optional, default: 0.7)"
            },
            "content_templates": {
                "template_name": "Descriptive name for this template (required)",
                "content_type": "Type of content this template handles (required)",
                "template_structure": "Field structure separated by | (required)",
                "required_fields": "Comma-separated list of required fields (optional)",
                "optional_fields": "Comma-separated list of optional fields (optional)",
                "validation_schema": "JSON schema for field validation (optional)",
                "ml_enhancement": "Enable ML enhancement: true/false (optional, default: false)"
            }
        }
        
        return {
            "memory_type": memory_type,
            "filename": template["filename"],
            "headers": template["headers"],
            "descriptions": field_descriptions.get(memory_type, {}),
            "sample_count": len(template["sample_data"])
        }
    
    def get_available_memory_types(self) -> List[str]:
        """
        Get list of available memory types.
        
        Returns:
            List of memory type names
        """
        return list(self.templates.keys())
    
    def validate_memory_type(self, memory_type: str) -> bool:
        """
        Check if a memory type is valid.
        
        Args:
            memory_type: Memory type to validate
        
        Returns:
            True if valid, False otherwise
        """
        return memory_type in self.templates