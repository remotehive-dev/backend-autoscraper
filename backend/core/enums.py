from enum import Enum

# User related enums
class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYER = "employer"
    JOB_SEEKER = "job_seeker"
    MODERATOR = "moderator"

# Job Post related enums
class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"

class WorkLocation(str, Enum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"

class JobStatus(str, Enum):
    # Initial states
    DRAFT = "draft"                    # Job created but not submitted for approval
    PENDING_APPROVAL = "pending_approval"  # Submitted for admin approval
    
    # Approval states
    APPROVED = "approved"              # Approved by admin but not published
    REJECTED = "rejected"              # Rejected by admin
    
    # Published states
    ACTIVE = "active"                  # Live on website, accepting applications
    PAUSED = "paused"                 # Temporarily hidden from website
    
    # End states
    CLOSED = "closed"                 # No longer accepting applications
    EXPIRED = "expired"               # Past application deadline
    CANCELLED = "cancelled"           # Cancelled by employer/admin
    
    # Special states
    FLAGGED = "flagged"               # Flagged for review
    UNDER_REVIEW = "under_review"     # Being reviewed by admin

class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"

# Job Application related enums
class ApplicationStatus(str, Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    SHORTLISTED = "shortlisted"
    INTERVIEWED = "interviewed"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

# Job Management Workflow enums
class JobAction(str, Enum):
    SUBMIT_FOR_APPROVAL = "submit_for_approval"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    PAUSE = "pause"
    RESUME = "resume"
    CLOSE = "close"
    REOPEN = "reopen"
    CANCEL = "cancel"
    FLAG = "flag"
    UNFLAG = "unflag"
    REVIEW = "review"
    EXPIRE = "expire"

class JobPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    FEATURED = "featured"

class RejectionReason(str, Enum):
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    INCOMPLETE_INFORMATION = "incomplete_information"
    DUPLICATE_POSTING = "duplicate_posting"
    INVALID_SALARY_RANGE = "invalid_salary_range"
    MISLEADING_TITLE = "misleading_title"
    COMPANY_NOT_VERIFIED = "company_not_verified"
    POLICY_VIOLATION = "policy_violation"
    SPAM_CONTENT = "spam_content"
    OTHER = "other"

# Job Seeker related enums
class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    CONSULTING = "consulting"

# Employer related enums
class CompanySize(str, Enum):
    STARTUP = "startup"  # 1-10 employees
    SMALL = "small"      # 11-50 employees
    MEDIUM = "medium"    # 51-200 employees
    LARGE = "large"      # 201-1000 employees
    ENTERPRISE = "enterprise"  # 1000+ employees

class Industry(str, Enum):
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    CONSULTING = "consulting"
    MEDIA = "media"
    NONPROFIT = "nonprofit"
    GOVERNMENT = "government"
    REAL_ESTATE = "real_estate"
    TRANSPORTATION = "transportation"
    ENERGY = "energy"
    AGRICULTURE = "agriculture"
    HOSPITALITY = "hospitality"
    CONSTRUCTION = "construction"
    AUTOMOTIVE = "automotive"
    AEROSPACE = "aerospace"
    TELECOMMUNICATIONS = "telecommunications"
    ENTERTAINMENT = "entertainment"
    LEGAL = "legal"
    INSURANCE = "insurance"
    BANKING = "banking"
    BIOTECHNOLOGY = "biotechnology"
    PHARMACEUTICALS = "pharmaceuticals"
    OTHER = "other"

# Scraper related enums
class ScraperStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScraperSource(str, Enum):
    LINKEDIN = "LINKEDIN"
    INDEED = "INDEED"
    GLASSDOOR = "GLASSDOOR"
    MONSTER = "MONSTER"
    ZIPRECRUITER = "ZIPRECRUITER"
    DICE = "DICE"
    STACKOVERFLOW = "STACKOVERFLOW"
    GITHUB_JOBS = "GITHUB_JOBS"
    ANGELLIST = "ANGELLIST"
    REMOTE_OK = "REMOTE_OK"
    WE_WORK_REMOTELY = "WE_WORK_REMOTELY"
    FLEXJOBS = "FLEXJOBS"
    UPWORK = "UPWORK"
    FREELANCER = "FREELANCER"
    TOPTAL = "TOPTAL"
    OTHER = "OTHER"

# CSV Import related enums
class CSVImportStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Upload related enums
class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MemoryUploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UPLOADED = "uploaded"  # Added for backward compatibility