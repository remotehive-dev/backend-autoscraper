import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import yaml
from pathlib import Path
from loguru import logger
import aiohttp
from urllib.parse import urlparse, urljoin
import re

from ..models.mongodb_models import JobBoard, JobBoardStatus
from ..ai.decision_engine import get_ai_decision_engine, JobBoardAnalysis
from ..scrapers.types import ScrapingEngine
from ..database.mongodb_client import get_mongodb_client

class JobBoardCategory(str, Enum):
    """Job board categories"""
    GENERAL = "general"
    TECH = "tech"
    REMOTE = "remote"
    FREELANCE = "freelance"
    STARTUP = "startup"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"
    NONPROFIT = "nonprofit"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    CONSULTING = "consulting"
    MEDIA = "media"
    LEGAL = "legal"
    REAL_ESTATE = "real_estate"
    HOSPITALITY = "hospitality"
    TRANSPORTATION = "transportation"
    ENERGY = "energy"

class JobBoardRegion(str, Enum):
    """Job board regions"""
    GLOBAL = "global"
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    LATIN_AMERICA = "latin_america"
    MIDDLE_EAST = "middle_east"
    AFRICA = "africa"
    USA = "usa"
    CANADA = "canada"
    UK = "uk"
    GERMANY = "germany"
    FRANCE = "france"
    INDIA = "india"
    CHINA = "china"
    JAPAN = "japan"
    AUSTRALIA = "australia"
    BRAZIL = "brazil"

@dataclass
class JobBoardConfig:
    """Configuration for a job board"""
    name: str
    base_url: str
    category: JobBoardCategory
    region: JobBoardRegion
    description: str
    is_active: bool = True
    priority: int = 1  # 1-10, higher is more important
    rate_limit_delay: float = 2.0
    max_concurrent_requests: int = 4
    preferred_engine: Optional[ScrapingEngine] = None
    custom_headers: Dict[str, str] = None
    requires_js: bool = False
    has_anti_bot: bool = False
    selectors: Dict[str, str] = None
    search_params: Dict[str, str] = None
    pagination_type: str = "page"  # page, offset, cursor
    max_pages: int = 10
    jobs_per_page: int = 20
    last_analyzed: Optional[datetime] = None
    analysis_score: float = 0.0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    notes: str = ""
    
    def __post_init__(self):
        if self.custom_headers is None:
            self.custom_headers = {}
        if self.selectors is None:
            self.selectors = {}
        if self.search_params is None:
            self.search_params = {}

class JobBoardManager:
    """Manages job board configurations and operations"""
    
    def __init__(self):
        self.ai_decision_engine = get_ai_decision_engine()
        self.mongodb_client = get_mongodb_client()
        self.job_boards: Dict[str, JobBoardConfig] = {}
        self.config_file = Path(__file__).parent / "job_boards_config.yaml"
        self.builtin_job_boards = self._get_builtin_job_boards()
    
    async def initialize(self):
        """Initialize job board manager"""
        try:
            # Load job board configurations
            await self._load_job_board_configs()
            
            # Sync with database
            await self._sync_with_database()
            
            logger.info(f"Initialized JobBoardManager with {len(self.job_boards)} job boards")
            
        except Exception as e:
            logger.error(f"Failed to initialize JobBoardManager: {e}")
            raise
    
    async def _load_job_board_configs(self):
        """Load job board configurations from file and builtin list"""
        try:
            # Load from config file if exists
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    
                for board_data in config_data.get('job_boards', []):
                    try:
                        config = JobBoardConfig(**board_data)
                        self.job_boards[config.name] = config
                    except Exception as e:
                        logger.error(f"Failed to load job board config {board_data.get('name', 'unknown')}: {e}")
            
            # Add builtin job boards if not already loaded
            for name, config in self.builtin_job_boards.items():
                if name not in self.job_boards:
                    self.job_boards[name] = config
            
            logger.info(f"Loaded {len(self.job_boards)} job board configurations")
            
        except Exception as e:
            logger.error(f"Failed to load job board configs: {e}")
            # Fall back to builtin job boards
            self.job_boards = self.builtin_job_boards.copy()
    
    async def _sync_with_database(self):
        """Sync job board configurations with database"""
        try:
            db = await self.mongodb_client.get_database()
            collection = db.job_boards
            
            # Get existing job boards from database
            existing_boards = {}
            async for board_doc in collection.find():
                existing_boards[board_doc['name']] = JobBoard(**board_doc)
            
            # Update or create job boards
            for name, config in self.job_boards.items():
                try:
                    if name in existing_boards:
                        # Update existing board
                        existing_board = existing_boards[name]
                        update_data = {
                            'base_url': config.base_url,
                            'category': config.category.value,
                            'region': config.region.value,
                            'description': config.description,
                            'is_active': config.is_active,
                            'priority': config.priority,
                            'rate_limit_delay': config.rate_limit_delay,
                            'max_concurrent_requests': config.max_concurrent_requests,
                            'preferred_engine': config.preferred_engine.value if config.preferred_engine else None,
                            'custom_headers': config.custom_headers,
                            'requires_js': config.requires_js,
                            'has_anti_bot': config.has_anti_bot,
                            'selectors': config.selectors,
                            'search_params': config.search_params,
                            'pagination_type': config.pagination_type,
                            'max_pages': config.max_pages,
                            'jobs_per_page': config.jobs_per_page,
                            'updated_at': datetime.now()
                        }
                        
                        await collection.update_one(
                            {'_id': existing_board.id},
                            {'$set': update_data}
                        )
                    else:
                        # Create new board
                        board_data = {
                            'name': config.name,
                            'base_url': config.base_url,
                            'category': config.category.value,
                            'region': config.region.value,
                            'description': config.description,
                            'is_active': config.is_active,
                            'priority': config.priority,
                            'rate_limit_delay': config.rate_limit_delay,
                            'max_concurrent_requests': config.max_concurrent_requests,
                            'preferred_engine': config.preferred_engine.value if config.preferred_engine else None,
                            'custom_headers': config.custom_headers,
                            'requires_js': config.requires_js,
                            'has_anti_bot': config.has_anti_bot,
                            'selectors': config.selectors,
                            'search_params': config.search_params,
                            'pagination_type': config.pagination_type,
                            'max_pages': config.max_pages,
                            'jobs_per_page': config.jobs_per_page,
                            'status': JobBoardStatus.ACTIVE.value,
                            'created_at': datetime.now(),
                            'updated_at': datetime.now()
                        }
                        
                        await collection.insert_one(board_data)
                        
                except Exception as e:
                    logger.error(f"Failed to sync job board {name}: {e}")
            
            logger.info("Synced job board configurations with database")
            
        except Exception as e:
            logger.error(f"Failed to sync with database: {e}")
    
    def _get_builtin_job_boards(self) -> Dict[str, JobBoardConfig]:
        """Get builtin job board configurations"""
        builtin_boards = {
            # Major General Job Boards
            "Indeed": JobBoardConfig(
                name="Indeed",
                base_url="https://www.indeed.com",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.GLOBAL,
                description="World's largest job site",
                priority=10,
                requires_js=True,
                has_anti_bot=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "LinkedIn Jobs": JobBoardConfig(
                name="LinkedIn Jobs",
                base_url="https://www.linkedin.com/jobs",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.GLOBAL,
                description="Professional network job board",
                priority=10,
                requires_js=True,
                has_anti_bot=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Glassdoor": JobBoardConfig(
                name="Glassdoor",
                base_url="https://www.glassdoor.com",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.GLOBAL,
                description="Jobs with company reviews and salaries",
                priority=9,
                requires_js=True,
                has_anti_bot=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Monster": JobBoardConfig(
                name="Monster",
                base_url="https://www.monster.com",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.GLOBAL,
                description="Global job search platform",
                priority=8,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            "ZipRecruiter": JobBoardConfig(
                name="ZipRecruiter",
                base_url="https://www.ziprecruiter.com",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.USA,
                description="AI-powered job matching",
                priority=8,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            
            # Tech-Specific Job Boards
            "Stack Overflow Jobs": JobBoardConfig(
                name="Stack Overflow Jobs",
                base_url="https://stackoverflow.com/jobs",
                category=JobBoardCategory.TECH,
                region=JobBoardRegion.GLOBAL,
                description="Developer-focused job board",
                priority=9,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "AngelList": JobBoardConfig(
                name="AngelList",
                base_url="https://angel.co/jobs",
                category=JobBoardCategory.STARTUP,
                region=JobBoardRegion.GLOBAL,
                description="Startup jobs and equity",
                priority=8,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Dice": JobBoardConfig(
                name="Dice",
                base_url="https://www.dice.com",
                category=JobBoardCategory.TECH,
                region=JobBoardRegion.USA,
                description="Technology professionals job board",
                priority=7,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            "GitHub Jobs": JobBoardConfig(
                name="GitHub Jobs",
                base_url="https://jobs.github.com",
                category=JobBoardCategory.TECH,
                region=JobBoardRegion.GLOBAL,
                description="Developer jobs from GitHub",
                priority=7,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            
            # Remote Work Job Boards
            "Remote.co": JobBoardConfig(
                name="Remote.co",
                base_url="https://remote.co",
                category=JobBoardCategory.REMOTE,
                region=JobBoardRegion.GLOBAL,
                description="Remote work opportunities",
                priority=8,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            "We Work Remotely": JobBoardConfig(
                name="We Work Remotely",
                base_url="https://weworkremotely.com",
                category=JobBoardCategory.REMOTE,
                region=JobBoardRegion.GLOBAL,
                description="Largest remote work community",
                priority=8,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            "FlexJobs": JobBoardConfig(
                name="FlexJobs",
                base_url="https://www.flexjobs.com",
                category=JobBoardCategory.REMOTE,
                region=JobBoardRegion.GLOBAL,
                description="Flexible and remote jobs",
                priority=7,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            
            # Freelance Job Boards
            "Upwork": JobBoardConfig(
                name="Upwork",
                base_url="https://www.upwork.com",
                category=JobBoardCategory.FREELANCE,
                region=JobBoardRegion.GLOBAL,
                description="Freelance marketplace",
                priority=9,
                requires_js=True,
                has_anti_bot=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Freelancer": JobBoardConfig(
                name="Freelancer",
                base_url="https://www.freelancer.com",
                category=JobBoardCategory.FREELANCE,
                region=JobBoardRegion.GLOBAL,
                description="Global freelancing platform",
                priority=8,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Fiverr": JobBoardConfig(
                name="Fiverr",
                base_url="https://www.fiverr.com",
                category=JobBoardCategory.FREELANCE,
                region=JobBoardRegion.GLOBAL,
                description="Gig-based freelance services",
                priority=7,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            
            # Regional Job Boards
            "Reed (UK)": JobBoardConfig(
                name="Reed (UK)",
                base_url="https://www.reed.co.uk",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.UK,
                description="UK's leading job board",
                priority=8,
                requires_js=False,
                preferred_engine=ScrapingEngine.BEAUTIFULSOUP
            ),
            "Xing Jobs (Germany)": JobBoardConfig(
                name="Xing Jobs (Germany)",
                base_url="https://www.xing.com/jobs",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.GERMANY,
                description="German professional network jobs",
                priority=7,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Naukri (India)": JobBoardConfig(
                name="Naukri (India)",
                base_url="https://www.naukri.com",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.INDIA,
                description="India's leading job portal",
                priority=8,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
            "Seek (Australia)": JobBoardConfig(
                name="Seek (Australia)",
                base_url="https://www.seek.com.au",
                category=JobBoardCategory.GENERAL,
                region=JobBoardRegion.AUSTRALIA,
                description="Australia's top job board",
                priority=8,
                requires_js=True,
                preferred_engine=ScrapingEngine.SELENIUM
            ),
        }
        
        return builtin_boards
    
    async def get_active_job_boards(self, 
                                   category: Optional[JobBoardCategory] = None,
                                   region: Optional[JobBoardRegion] = None,
                                   min_priority: int = 1) -> List[JobBoardConfig]:
        """Get active job boards with optional filtering"""
        try:
            active_boards = []
            
            for config in self.job_boards.values():
                if not config.is_active:
                    continue
                    
                if config.priority < min_priority:
                    continue
                    
                if category and config.category != category:
                    continue
                    
                if region and config.region != region:
                    continue
                
                active_boards.append(config)
            
            # Sort by priority (highest first)
            active_boards.sort(key=lambda x: x.priority, reverse=True)
            
            return active_boards
            
        except Exception as e:
            logger.error(f"Failed to get active job boards: {e}")
            return []
    
    async def analyze_job_board(self, config: JobBoardConfig) -> JobBoardAnalysis:
        """Analyze a job board using AI"""
        try:
            logger.info(f"Analyzing job board: {config.name}")
            
            # Test connection first
            is_accessible = await self._test_job_board_connection(config)
            
            if not is_accessible:
                return JobBoardAnalysis(
                    is_scrapable=False,
                    requires_js=True,
                    has_anti_bot_measures=True,
                    recommended_engine=ScrapingEngine.SELENIUM,
                    confidence_score=0.0,
                    selectors={},
                    rate_limit_recommendation=5.0,
                    notes="Site not accessible or blocked"
                )
            
            # Get sample HTML for analysis
            sample_html = await self._get_sample_html(config)
            
            if not sample_html:
                return JobBoardAnalysis(
                    is_scrapable=False,
                    requires_js=True,
                    has_anti_bot_measures=True,
                    recommended_engine=ScrapingEngine.SELENIUM,
                    confidence_score=0.0,
                    selectors={},
                    rate_limit_recommendation=5.0,
                    notes="Could not retrieve sample HTML"
                )
            
            # Use AI to analyze the job board
            analysis = await self.ai_decision_engine.analyze_job_board(config.base_url, sample_html)
            
            # Update config with analysis results
            config.last_analyzed = datetime.now()
            config.analysis_score = analysis.confidence_score
            config.requires_js = analysis.requires_js
            config.has_anti_bot = analysis.has_anti_bot_measures
            config.preferred_engine = analysis.recommended_engine
            config.rate_limit_delay = analysis.rate_limit_recommendation
            config.selectors.update(analysis.selectors)
            config.notes = analysis.notes
            
            logger.info(f"Analysis complete for {config.name}: score={analysis.confidence_score:.2f}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze job board {config.name}: {e}")
            return JobBoardAnalysis(
                is_scrapable=False,
                requires_js=True,
                has_anti_bot_measures=True,
                recommended_engine=ScrapingEngine.SELENIUM,
                confidence_score=0.0,
                selectors={},
                rate_limit_recommendation=5.0,
                notes=f"Analysis failed: {str(e)}"
            )
    
    async def _test_job_board_connection(self, config: JobBoardConfig) -> bool:
        """Test if we can connect to a job board"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            headers.update(config.custom_headers)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(config.base_url) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Connection test failed for {config.name}: {e}")
            return False
    
    async def _get_sample_html(self, config: JobBoardConfig) -> Optional[str]:
        """Get sample HTML from job board for analysis"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            headers.update(config.custom_headers)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(config.base_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Return first 10KB for analysis
                        return html[:10000]
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get sample HTML for {config.name}: {e}")
            return None
    
    async def bulk_analyze_job_boards(self, max_concurrent: int = 5) -> Dict[str, JobBoardAnalysis]:
        """Analyze multiple job boards concurrently"""
        try:
            results = {}
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def analyze_single(name: str, config: JobBoardConfig):
                async with semaphore:
                    try:
                        analysis = await self.analyze_job_board(config)
                        results[name] = analysis
                        await asyncio.sleep(1)  # Small delay between analyses
                    except Exception as e:
                        logger.error(f"Failed to analyze {name}: {e}")
            
            # Create tasks for all active job boards
            tasks = []
            for name, config in self.job_boards.items():
                if config.is_active:
                    tasks.append(analyze_single(name, config))
            
            # Run analyses concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"Bulk analysis complete: {len(results)} job boards analyzed")
            return results
            
        except Exception as e:
            logger.error(f"Bulk analysis failed: {e}")
            return {}
    
    async def save_configurations(self):
        """Save job board configurations to file"""
        try:
            config_data = {
                'job_boards': []
            }
            
            for config in self.job_boards.values():
                board_dict = asdict(config)
                # Convert enums to strings
                board_dict['category'] = config.category.value
                board_dict['region'] = config.region.value
                if config.preferred_engine:
                    board_dict['preferred_engine'] = config.preferred_engine.value
                # Convert datetime to ISO string
                if config.last_analyzed:
                    board_dict['last_analyzed'] = config.last_analyzed.isoformat()
                
                config_data['job_boards'].append(board_dict)
            
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to YAML file
            with open(self.config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Saved {len(self.job_boards)} job board configurations")
            
        except Exception as e:
            logger.error(f"Failed to save configurations: {e}")
    
    async def add_job_board(self, config: JobBoardConfig) -> bool:
        """Add a new job board configuration"""
        try:
            if config.name in self.job_boards:
                logger.warning(f"Job board {config.name} already exists")
                return False
            
            # Analyze the new job board
            analysis = await self.analyze_job_board(config)
            
            # Add to memory
            self.job_boards[config.name] = config
            
            # Save to file
            await self.save_configurations()
            
            # Sync with database
            await self._sync_with_database()
            
            logger.info(f"Added new job board: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job board {config.name}: {e}")
            return False
    
    async def update_job_board_metrics(self, name: str, success_rate: float, avg_response_time: float):
        """Update job board performance metrics"""
        try:
            if name in self.job_boards:
                config = self.job_boards[name]
                config.success_rate = success_rate
                config.avg_response_time = avg_response_time
                
                # Update in database
                db = await self.mongodb_client.get_database()
                collection = db.job_boards
                
                await collection.update_one(
                    {'name': name},
                    {'$set': {
                        'success_rate': success_rate,
                        'avg_response_time': avg_response_time,
                        'updated_at': datetime.now()
                    }}
                )
                
                logger.debug(f"Updated metrics for {name}: success_rate={success_rate:.2f}, avg_time={avg_response_time:.2f}s")
                
        except Exception as e:
            logger.error(f"Failed to update metrics for {name}: {e}")
    
    def get_job_board_config(self, name: str) -> Optional[JobBoardConfig]:
        """Get job board configuration by name"""
        return self.job_boards.get(name)
    
    def get_all_job_boards(self) -> Dict[str, JobBoardConfig]:
        """Get all job board configurations"""
        return self.job_boards.copy()
    
    async def get_recommended_job_boards(self, 
                                       category: Optional[JobBoardCategory] = None,
                                       region: Optional[JobBoardRegion] = None,
                                       max_boards: int = 20) -> List[JobBoardConfig]:
        """Get recommended job boards based on performance and criteria"""
        try:
            # Get active boards with filtering
            active_boards = await self.get_active_job_boards(category, region)
            
            # Sort by combined score (priority + success_rate + analysis_score)
            def calculate_score(config: JobBoardConfig) -> float:
                priority_score = config.priority / 10.0  # Normalize to 0-1
                success_score = config.success_rate  # Already 0-1
                analysis_score = config.analysis_score  # Already 0-1
                
                # Weighted combination
                return (priority_score * 0.4) + (success_score * 0.3) + (analysis_score * 0.3)
            
            active_boards.sort(key=calculate_score, reverse=True)
            
            return active_boards[:max_boards]
            
        except Exception as e:
            logger.error(f"Failed to get recommended job boards: {e}")
            return []

# Global instance
_job_board_manager = None

async def get_job_board_manager() -> JobBoardManager:
    """Get global job board manager instance"""
    global _job_board_manager
    if _job_board_manager is None:
        _job_board_manager = JobBoardManager()
        await _job_board_manager.initialize()
    return _job_board_manager