import csv
import io
from datetime import datetime
from typing import Dict, List, Any

class WebsiteTemplateService:
    """Service for generating website CSV templates and providing template information."""
    
    def __init__(self):
        self.template_headers = [
            'name',
            'url', 
            'category',
            'scraping_enabled',
            'rate_limit',
            'max_pages',
            'custom_headers',
            'selectors'
        ]
        
        self.sample_data = [
            {
                'name': 'Example Job Board',
                'url': 'https://example-jobs.com',
                'category': 'job_boards',
                'scraping_enabled': 'true',
                'rate_limit': '5',
                'max_pages': '100',
                'custom_headers': '{"User-Agent": "CustomBot/1.0"}',
                'selectors': '{"title": ".job-title", "company": ".company-name"}'
            },
            {
                'name': 'Tech News Site',
                'url': 'https://tech-news.com',
                'category': 'news_media',
                'scraping_enabled': 'true',
                'rate_limit': '3',
                'max_pages': '50',
                'custom_headers': '{}',
                'selectors': '{"headline": "h1", "content": ".article-body"}'
            },
            {
                'name': 'E-commerce Store',
                'url': 'https://online-store.com',
                'category': 'ecommerce',
                'scraping_enabled': 'false',
                'rate_limit': '10',
                'max_pages': '200',
                'custom_headers': '{}',
                'selectors': '{"product": ".product-name", "price": ".price"}'
            }
        ]
        
        self.field_descriptions = {
            'name': {
                'description': 'Display name for the website',
                'required': True,
                'type': 'string',
                'example': 'Example Job Board'
            },
            'url': {
                'description': 'Full URL of the website to scrape',
                'required': True,
                'type': 'string',
                'example': 'https://example.com'
            },
            'category': {
                'description': 'Website category for organization',
                'required': True,
                'type': 'string',
                'options': ['job_boards', 'news_media', 'ecommerce', 'social_media', 'education', 'general'],
                'example': 'job_boards'
            },
            'scraping_enabled': {
                'description': 'Whether scraping is enabled for this website',
                'required': False,
                'type': 'boolean',
                'default': 'true',
                'options': ['true', 'false', '1', '0', 'yes', 'no'],
                'example': 'true'
            },
            'rate_limit': {
                'description': 'Delay between requests in seconds',
                'required': False,
                'type': 'integer',
                'default': '5',
                'range': '1-60',
                'example': '5'
            },
            'max_pages': {
                'description': 'Maximum number of pages to scrape',
                'required': False,
                'type': 'integer',
                'default': '100',
                'range': '1-10000',
                'example': '100'
            },
            'custom_headers': {
                'description': 'Custom HTTP headers as JSON object',
                'required': False,
                'type': 'json',
                'default': '{}',
                'example': '{"User-Agent": "CustomBot/1.0", "Accept": "text/html"}'
            },
            'selectors': {
                'description': 'CSS selectors for data extraction as JSON object',
                'required': False,
                'type': 'json',
                'default': '{}',
                'example': '{"title": ".job-title", "company": ".company-name"}'
            }
        }
        
        self.categories = [
            {
                'value': 'job_boards',
                'label': 'Job Boards',
                'description': 'Employment and career websites'
            },
            {
                'value': 'news_media',
                'label': 'News & Media',
                'description': 'News websites, blogs, and media outlets'
            },
            {
                'value': 'ecommerce',
                'label': 'E-commerce',
                'description': 'Online stores and shopping websites'
            },
            {
                'value': 'social_media',
                'label': 'Social Media',
                'description': 'Social networks and community platforms'
            },
            {
                'value': 'education',
                'label': 'Education',
                'description': 'Educational institutions and learning platforms'
            },
            {
                'value': 'general',
                'label': 'General',
                'description': 'Other types of websites'
            }
        ]
    
    def generate_template(self) -> str:
        """Generate CSV template with headers and sample data."""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.template_headers)
        
        # Write header
        writer.writeheader()
        
        # Write sample data
        for sample in self.sample_data:
            writer.writerow(sample)
        
        return output.getvalue()
    
    def get_template_filename(self) -> str:
        """Get template filename with timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"website_template_{timestamp}.csv"
    
    def get_template_info(self) -> Dict[str, Any]:
        """Get comprehensive template information."""
        
        return {
            'template_name': 'Website Bulk Upload Template',
            'description': 'CSV template for uploading multiple websites for scraping configuration',
            'version': '1.0',
            'headers': self.template_headers,
            'required_fields': [field for field, info in self.field_descriptions.items() if info['required']],
            'optional_fields': [field for field, info in self.field_descriptions.items() if not info['required']],
            'field_descriptions': self.field_descriptions,
            'categories': self.categories,
            'sample_data': self.sample_data,
            'validation_rules': {
                'url_format': 'Must start with http:// or https://',
                'rate_limit_range': '1-60 seconds',
                'max_pages_range': '1-10000 pages',
                'json_fields': ['custom_headers', 'selectors'],
                'boolean_fields': ['scraping_enabled']
            },
            'tips': [
                'Use descriptive names for easy identification',
                'Ensure URLs are complete and accessible',
                'Choose appropriate categories for better organization',
                'Set reasonable rate limits to avoid being blocked',
                'Custom headers can help with authentication or user agent spoofing',
                'Selectors should be CSS selectors for data extraction',
                'Leave JSON fields empty ({}) if not needed'
            ],
            'common_errors': [
                'Invalid URL format (missing http:// or https://)',
                'Invalid JSON format in custom_headers or selectors',
                'Rate limit outside acceptable range (1-60)',
                'Max pages outside acceptable range (1-10000)',
                'Missing required fields (name, url, category)'
            ]
        }
    
    def get_field_info(self, field_name: str) -> Dict[str, Any]:
        """Get information about a specific field."""
        return self.field_descriptions.get(field_name, {})
    
    def get_available_categories(self) -> List[Dict[str, str]]:
        """Get list of available website categories."""
        return self.categories
    
    def validate_template_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate template data against field requirements."""
        
        errors = []
        
        # Check required fields
        for field, info in self.field_descriptions.items():
            if info['required'] and (field not in data or not data[field]):
                errors.append(f"Missing required field: {field}")
        
        # Validate URL format
        if 'url' in data and data['url']:
            url = data['url'].strip()
            if not url.startswith(('http://', 'https://')):
                errors.append("URL must start with http:// or https://")
        
        # Validate category
        if 'category' in data and data['category']:
            valid_categories = [cat['value'] for cat in self.categories]
            if data['category'] not in valid_categories:
                errors.append(f"Invalid category. Must be one of: {', '.join(valid_categories)}")
        
        # Validate numeric fields
        if 'rate_limit' in data and data['rate_limit']:
            try:
                rate_limit = int(data['rate_limit'])
                if rate_limit < 1 or rate_limit > 60:
                    errors.append("Rate limit must be between 1 and 60 seconds")
            except ValueError:
                errors.append("Rate limit must be a valid integer")
        
        if 'max_pages' in data and data['max_pages']:
            try:
                max_pages = int(data['max_pages'])
                if max_pages < 1 or max_pages > 10000:
                    errors.append("Max pages must be between 1 and 10000")
            except ValueError:
                errors.append("Max pages must be a valid integer")
        
        # Validate JSON fields
        for json_field in ['custom_headers', 'selectors']:
            if json_field in data and data[json_field]:
                try:
                    import json
                    json.loads(data[json_field])
                except json.JSONDecodeError:
                    errors.append(f"{json_field} must be valid JSON format")
        
        # Validate boolean fields
        if 'scraping_enabled' in data and data['scraping_enabled']:
            valid_boolean_values = ['true', 'false', '1', '0', 'yes', 'no']
            if str(data['scraping_enabled']).lower() not in valid_boolean_values:
                errors.append(f"scraping_enabled must be one of: {', '.join(valid_boolean_values)}")
        
        return errors
    
    def get_template_statistics(self) -> Dict[str, Any]:
        """Get statistics about the template."""
        
        return {
            'total_fields': len(self.template_headers),
            'required_fields': len([f for f, info in self.field_descriptions.items() if info['required']]),
            'optional_fields': len([f for f, info in self.field_descriptions.items() if not info['required']]),
            'available_categories': len(self.categories),
            'sample_records': len(self.sample_data),
            'json_fields': len([f for f, info in self.field_descriptions.items() if info.get('type') == 'json']),
            'boolean_fields': len([f for f, info in self.field_descriptions.items() if info.get('type') == 'boolean']),
            'numeric_fields': len([f for f, info in self.field_descriptions.items() if info.get('type') == 'integer'])
        }