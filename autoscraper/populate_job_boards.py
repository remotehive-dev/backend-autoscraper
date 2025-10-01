#!/usr/bin/env python3
import asyncio
from datetime import datetime
from app.models.mongodb_models import JobBoard, JobBoardType
from app.database.mongodb_manager import get_autoscraper_mongodb_manager

# Job board configurations using correct MongoDB model format
JOB_BOARD_CONFIGS = [
    {
        "name": "Indeed Jobs",
        "type": JobBoardType.INDEED,
        "base_url": "https://www.indeed.com",
        "search_url_template": "https://www.indeed.com/jobs?q={query}&l={location}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 20,
        "selectors": {
            "job_title": "h2.jobTitle a span",
            "company": "span.companyName",
            "location": "div.companyLocation",
            "salary": "span.salary-snippet",
            "description": "div.job-snippet"
        }
    },
    {
        "name": "LinkedIn Jobs",
        "type": JobBoardType.LINKEDIN,
        "base_url": "https://www.linkedin.com",
        "search_url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 3.0,
        "max_pages_per_search": 15,
        "javascript_required": True,
        "selectors": {
            "job_title": "h3.base-search-card__title",
            "company": "h4.base-search-card__subtitle",
            "location": "span.job-search-card__location",
            "description": "p.job-search-card__snippet"
        }
    },
    {
        "name": "Glassdoor",
        "type": JobBoardType.GLASSDOOR,
        "base_url": "https://www.glassdoor.com",
        "search_url_template": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=C&locId={location}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.5,
        "max_pages_per_search": 10
    },
    {
        "name": "Monster",
        "type": JobBoardType.MONSTER,
        "base_url": "https://www.monster.com",
        "search_url_template": "https://www.monster.com/jobs/search/?q={query}&where={location}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 15
    },
    {
        "name": "ZipRecruiter",
        "type": JobBoardType.ZIPRECRUITER,
        "base_url": "https://www.ziprecruiter.com",
        "search_url_template": "https://www.ziprecruiter.com/jobs/search?search={query}&location={location}",
        "region": "US",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 12
    },
    {
        "name": "CareerBuilder",
        "type": JobBoardType.CAREERBUILDER,
        "base_url": "https://www.careerbuilder.com",
        "search_url_template": "https://www.careerbuilder.com/jobs?keywords={query}&location={location}",
        "region": "US",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 10
    },
    {
        "name": "Dice",
        "type": JobBoardType.DICE,
        "base_url": "https://www.dice.com",
        "search_url_template": "https://www.dice.com/jobs?q={query}&location={location}",
        "region": "US",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 15
    },
    {
        "name": "Remote OK",
        "type": JobBoardType.REMOTE_OK,
        "base_url": "https://remoteok.io",
        "search_url_template": "https://remoteok.io/remote-{query}-jobs",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 1.5,
        "max_pages_per_search": 5
    },
    {
        "name": "We Work Remotely",
        "type": JobBoardType.WE_WORK_REMOTELY,
        "base_url": "https://weworkremotely.com",
        "search_url_template": "https://weworkremotely.com/remote-jobs/search?term={query}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 8
    },
    {
        "name": "AngelList",
        "type": JobBoardType.ANGELLIST,
        "base_url": "https://angel.co",
        "search_url_template": "https://angel.co/jobs?q={query}&location={location}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 3.0,
        "max_pages_per_search": 8
    },
    {
        "name": "FlexJobs",
        "type": JobBoardType.FLEXJOBS,
        "base_url": "https://www.flexjobs.com",
        "search_url_template": "https://www.flexjobs.com/search?search={query}&location={location}",
        "region": "US",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 5
    },
    {
        "name": "Upwork",
        "type": JobBoardType.UPWORK,
        "base_url": "https://www.upwork.com",
        "search_url_template": "https://www.upwork.com/freelance-jobs/{query}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 3.0,
        "max_pages_per_search": 10
    },
    {
        "name": "Freelancer",
        "type": JobBoardType.FREELANCER,
        "base_url": "https://www.freelancer.com",
        "search_url_template": "https://www.freelancer.com/jobs/{query}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 8
    },
    {
        "name": "Toptal",
        "type": JobBoardType.TOPTAL,
        "base_url": "https://www.toptal.com",
        "search_url_template": "https://www.toptal.com/freelance-jobs/{query}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 4.0,
        "max_pages_per_search": 3
    },
    {
        "name": "Guru",
        "type": JobBoardType.GURU,
        "base_url": "https://www.guru.com",
        "search_url_template": "https://www.guru.com/d/jobs/skill/{query}",
        "region": "Global",
        "is_active": True,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 6
    },
    {
        "name": "Stack Overflow Jobs",
        "type": JobBoardType.STACKOVERFLOW,
        "base_url": "https://stackoverflow.com",
        "search_url_template": "https://stackoverflow.com/jobs?q={query}&l={location}",
        "region": "Global",
        "is_active": False,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 10
    },
    {
        "name": "GitHub Jobs",
        "type": JobBoardType.GITHUB_JOBS,
        "base_url": "https://jobs.github.com",
        "search_url_template": "https://jobs.github.com/positions?description={query}&location={location}",
        "region": "Global",
        "is_active": False,
        "rate_limit_delay": 2.0,
        "max_pages_per_search": 8
    }
]

async def populate_job_boards():
    """Populate the database with job board configurations"""
    try:
        manager = await get_autoscraper_mongodb_manager()
        
        # Check existing job boards
        existing_count = await JobBoard.count()
        print(f"Current job boards in database: {existing_count}")
        
        # Clear existing job boards to avoid conflicts
        await JobBoard.delete_all()
        print("Cleared existing job boards")
        
        created_count = 0
        
        for config in JOB_BOARD_CONFIGS:
            # Create new job board
            job_board = JobBoard(**config)
            await job_board.insert()
            created_count += 1
            print(f"Created: {config['name']} ({config['type']})")
        
        # Final count
        final_count = await JobBoard.count()
        active_count = await JobBoard.find({"is_active": True}).count()
        
        print(f"\n=== Summary ===")
        print(f"Job boards created: {created_count}")
        print(f"Total job boards: {final_count}")
        print(f"Active job boards: {active_count}")
        
        return final_count, active_count
        
    except Exception as e:
        print(f"Error populating job boards: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

if __name__ == '__main__':
    asyncio.run(populate_job_boards())