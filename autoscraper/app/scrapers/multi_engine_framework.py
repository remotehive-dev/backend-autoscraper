import asyncio
from typing import Dict, List, Optional, Any, Union, Type
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from loguru import logger

from .types import ScrapingEngine, JobData
from ..ai.decision_engine import get_ai_decision_engine, AIAnalysisResult
from ..models.mongodb_models import JobBoard

@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    success: bool
    jobs: List[JobData]
    engine_used: ScrapingEngine
    execution_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    ai_analysis: Optional[AIAnalysisResult] = None

@dataclass
class EnginePerformanceMetrics:
    """Performance metrics for a scraping engine"""
    engine: ScrapingEngine
    success_rate: float
    average_execution_time: float
    jobs_per_minute: float
    error_count: int
    last_used: datetime
    total_jobs_scraped: int

class BaseJobScraper(ABC):
    """Base class for all job scrapers"""
    
    def __init__(self, engine_type: ScrapingEngine):
        self.engine_type = engine_type
        self.performance_metrics = EnginePerformanceMetrics(
            engine=engine_type,
            success_rate=0.0,
            average_execution_time=0.0,
            jobs_per_minute=0.0,
            error_count=0,
            last_used=datetime.now(),
            total_jobs_scraped=0
        )
    
    @abstractmethod
    async def scrape_jobs(self, job_board: JobBoard, selectors: Dict[str, str], **kwargs) -> List[JobData]:
        """Scrape jobs from a job board"""
        pass
    
    @abstractmethod
    async def test_connection(self, url: str) -> bool:
        """Test if the scraper can connect to a URL"""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """Cleanup resources"""
        pass

class MultiEngineScrapingFramework:
    """Intelligent multi-engine scraping framework with AI coordination"""
    
    def __init__(self):
        self.engines: Dict[ScrapingEngine, BaseJobScraper] = {}
        self.ai_decision_engine = get_ai_decision_engine()
        self.performance_history: Dict[str, List[EnginePerformanceMetrics]] = {}
        self.fallback_order = [ScrapingEngine.SCRAPY, ScrapingEngine.BEAUTIFULSOUP, ScrapingEngine.SELENIUM]
        self._initialize_engines()
    
    def _initialize_engines(self):
        """Initialize all scraping engines"""
        try:
            from .scrapy_engine import ScrapyJobScraper
            self.engines[ScrapingEngine.SCRAPY] = ScrapyJobScraper()
            logger.info("Scrapy engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Scrapy engine: {e}")
        
        try:
            from .beautifulsoup_engine import BeautifulSoupJobScraper
            self.engines[ScrapingEngine.BEAUTIFULSOUP] = BeautifulSoupJobScraper()
            logger.info("BeautifulSoup engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize BeautifulSoup engine: {e}")
        
        try:
            from .selenium_engine import SeleniumJobScraper
            self.engines[ScrapingEngine.SELENIUM] = SeleniumJobScraper()
            logger.info("Selenium engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Selenium engine: {e}")
    
    async def scrape_job_board(self, job_board: JobBoard, max_jobs: int = 100) -> ScrapingResult:
        """Scrape a job board using AI-selected optimal engine"""
        start_time = datetime.now()
        
        try:
            # Get AI analysis and engine recommendation
            ai_analysis = await self.ai_decision_engine.analyze_job_board(job_board)
            recommended_engine = ai_analysis.recommended_engine
            
            logger.info(f"AI recommends {recommended_engine.value} engine for {job_board.name}")
            
            # Try recommended engine first
            result = await self._scrape_with_engine(
                job_board, recommended_engine, ai_analysis.selectors, max_jobs
            )
            
            if result.success:
                result.ai_analysis = ai_analysis
                await self._update_performance_metrics(recommended_engine, result, start_time)
                return result
            
            # If recommended engine fails, try fallback engines
            logger.warning(f"Recommended engine {recommended_engine.value} failed, trying fallbacks")
            
            for fallback_engine in self.fallback_order:
                if fallback_engine == recommended_engine:
                    continue  # Skip already tried engine
                
                if fallback_engine not in self.engines:
                    continue  # Skip unavailable engines
                
                logger.info(f"Trying fallback engine: {fallback_engine.value}")
                
                result = await self._scrape_with_engine(
                    job_board, fallback_engine, ai_analysis.selectors, max_jobs
                )
                
                if result.success:
                    result.ai_analysis = ai_analysis
                    await self._update_performance_metrics(fallback_engine, result, start_time)
                    return result
            
            # All engines failed
            execution_time = (datetime.now() - start_time).total_seconds()
            return ScrapingResult(
                success=False,
                jobs=[],
                engine_used=recommended_engine,
                execution_time=execution_time,
                error_message="All scraping engines failed",
                ai_analysis=ai_analysis
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Multi-engine scraping failed for {job_board.name}: {e}")
            
            return ScrapingResult(
                success=False,
                jobs=[],
                engine_used=ScrapingEngine.SCRAPY,  # Default
                execution_time=execution_time,
                error_message=str(e)
            )
    
    async def _scrape_with_engine(
        self, 
        job_board: JobBoard, 
        engine: ScrapingEngine, 
        selectors: Dict[str, str], 
        max_jobs: int
    ) -> ScrapingResult:
        """Scrape using a specific engine"""
        start_time = datetime.now()
        
        if engine not in self.engines:
            return ScrapingResult(
                success=False,
                jobs=[],
                engine_used=engine,
                execution_time=0.0,
                error_message=f"Engine {engine.value} not available"
            )
        
        try:
            scraper = self.engines[engine]
            
            # Test connection first
            if not await scraper.test_connection(job_board.base_url):
                return ScrapingResult(
                    success=False,
                    jobs=[],
                    engine_used=engine,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    error_message="Connection test failed"
                )
            
            # Scrape jobs
            jobs = await scraper.scrape_jobs(job_board, selectors, max_jobs=max_jobs)
            
            # Validate jobs using AI
            validated_jobs = []
            for job in jobs:
                validation_result = await self.ai_decision_engine.validate_job_content(
                    job.__dict__, job_board.name
                )
                
                if validation_result.quality_score > 0.5:  # Only keep high-quality jobs
                    validated_jobs.append(job)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ScrapingResult(
                success=True,
                jobs=validated_jobs,
                engine_used=engine,
                execution_time=execution_time,
                metadata={
                    "total_scraped": len(jobs),
                    "validated_count": len(validated_jobs),
                    "validation_rate": len(validated_jobs) / len(jobs) if jobs else 0
                }
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Engine {engine.value} failed for {job_board.name}: {e}")
            
            return ScrapingResult(
                success=False,
                jobs=[],
                engine_used=engine,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    async def _update_performance_metrics(self, engine: ScrapingEngine, result: ScrapingResult, start_time: datetime):
        """Update performance metrics for an engine"""
        if engine not in self.engines:
            return
        
        scraper = self.engines[engine]
        metrics = scraper.performance_metrics
        
        # Update metrics
        if result.success:
            # Update success rate (exponential moving average)
            metrics.success_rate = 0.9 * metrics.success_rate + 0.1 * 1.0
            metrics.total_jobs_scraped += len(result.jobs)
        else:
            metrics.success_rate = 0.9 * metrics.success_rate + 0.1 * 0.0
            metrics.error_count += 1
        
        # Update execution time (exponential moving average)
        metrics.average_execution_time = 0.9 * metrics.average_execution_time + 0.1 * result.execution_time
        
        # Calculate jobs per minute
        if result.execution_time > 0:
            current_jpm = len(result.jobs) / (result.execution_time / 60)
            metrics.jobs_per_minute = 0.9 * metrics.jobs_per_minute + 0.1 * current_jpm
        
        metrics.last_used = datetime.now()
        
        # Store in history
        board_key = f"{engine.value}"
        if board_key not in self.performance_history:
            self.performance_history[board_key] = []
        
        self.performance_history[board_key].append(metrics)
        
        # Keep only last 100 entries
        if len(self.performance_history[board_key]) > 100:
            self.performance_history[board_key] = self.performance_history[board_key][-100:]
    
    async def get_optimal_engine_for_board(self, job_board: JobBoard) -> ScrapingEngine:
        """Get the optimal engine for a specific job board based on AI and performance history"""
        # Get AI recommendation
        ai_analysis = await self.ai_decision_engine.analyze_job_board(job_board)
        ai_recommendation = ai_analysis.recommended_engine
        
        # Check if we have performance history for this board
        board_key = f"{job_board.id}"
        if board_key in self.performance_history:
            # Find the best performing engine
            best_engine = None
            best_score = 0.0
            
            for engine in ScrapingEngine:
                if engine not in self.engines:
                    continue
                
                metrics = self.engines[engine].performance_metrics
                # Score based on success rate and speed
                score = metrics.success_rate * 0.7 + (1.0 / max(metrics.average_execution_time, 0.1)) * 0.3
                
                if score > best_score:
                    best_score = score
                    best_engine = engine
            
            if best_engine and best_score > 0.5:
                logger.info(f"Using performance-based engine {best_engine.value} for {job_board.name}")
                return best_engine
        
        # Fall back to AI recommendation
        logger.info(f"Using AI-recommended engine {ai_recommendation.value} for {job_board.name}")
        return ai_recommendation
    
    async def test_all_engines(self, test_url: str = "https://httpbin.org/get") -> Dict[ScrapingEngine, bool]:
        """Test all engines with a simple URL"""
        results = {}
        
        for engine, scraper in self.engines.items():
            try:
                result = await scraper.test_connection(test_url)
                results[engine] = result
                logger.info(f"Engine {engine.value} test: {'PASS' if result else 'FAIL'}")
            except Exception as e:
                results[engine] = False
                logger.error(f"Engine {engine.value} test failed: {e}")
        
        return results
    
    def get_engine_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get performance summary for all engines"""
        summary = {}
        
        for engine, scraper in self.engines.items():
            metrics = scraper.performance_metrics
            summary[engine.value] = {
                "success_rate": round(metrics.success_rate, 3),
                "average_execution_time": round(metrics.average_execution_time, 2),
                "jobs_per_minute": round(metrics.jobs_per_minute, 2),
                "error_count": metrics.error_count,
                "total_jobs_scraped": metrics.total_jobs_scraped,
                "last_used": metrics.last_used.isoformat()
            }
        
        return summary
    
    async def optimize_engine_parameters(self, job_board: JobBoard) -> Dict[str, Any]:
        """Get AI-powered optimization parameters for engines"""
        # Collect performance data
        performance_data = {
            "job_board_id": str(job_board.id),
            "job_board_name": job_board.name,
            "base_url": job_board.base_url,
            "engine_performance": self.get_engine_performance_summary()
        }
        
        # Get AI optimization recommendations
        optimization = await self.ai_decision_engine.optimize_scraping_parameters(
            job_board, performance_data
        )
        
        return {
            "recommended_delay": optimization.recommended_delay,
            "concurrent_requests": optimization.recommended_concurrent_requests,
            "timeout": optimization.recommended_timeout,
            "user_agent_strategy": optimization.user_agent_strategy,
            "use_proxy": optimization.proxy_recommendation,
            "other_optimizations": optimization.other_optimizations
        }
    
    async def cleanup_all_engines(self):
        """Cleanup all engines"""
        for engine, scraper in self.engines.items():
            try:
                await scraper.cleanup()
                logger.info(f"Cleaned up {engine.value} engine")
            except Exception as e:
                logger.error(f"Failed to cleanup {engine.value} engine: {e}")
    
    def get_available_engines(self) -> List[ScrapingEngine]:
        """Get list of available engines"""
        return list(self.engines.keys())
    
    def is_engine_available(self, engine: ScrapingEngine) -> bool:
        """Check if an engine is available"""
        return engine in self.engines

# Global framework instance
_framework_instance = None

def get_multi_engine_framework() -> MultiEngineScrapingFramework:
    """Get or create multi-engine framework instance"""
    global _framework_instance
    if _framework_instance is None:
        _framework_instance = MultiEngineScrapingFramework()
    return _framework_instance