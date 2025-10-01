#!/usr/bin/env python3
"""
Data Deduplication System for Scraped Jobs
Prevents duplicate job entries and ensures data quality
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class JobFingerprint:
    """Represents a unique fingerprint for a job posting"""
    content_hash: str
    title_normalized: str
    company_normalized: str
    location_normalized: str
    url_normalized: str
    description_hash: str
    similarity_tokens: Set[str]
    
    def __post_init__(self):
        if isinstance(self.similarity_tokens, list):
            self.similarity_tokens = set(self.similarity_tokens)

class JobDeduplicator:
    """Advanced job deduplication system"""
    
    def __init__(self, similarity_threshold: float = 0.85,
                 title_weight: float = 0.3,
                 company_weight: float = 0.2,
                 location_weight: float = 0.1,
                 description_weight: float = 0.4):
        
        self.similarity_threshold = similarity_threshold
        self.title_weight = title_weight
        self.company_weight = company_weight
        self.location_weight = location_weight
        self.description_weight = description_weight
        
        # Storage for job fingerprints
        self.job_fingerprints: Dict[str, JobFingerprint] = {}
        self.url_to_hash: Dict[str, str] = {}
        self.content_hashes: Set[str] = set()
        
        # Duplicate tracking
        self.duplicate_groups: Dict[str, List[str]] = defaultdict(list)
        self.stats = {
            'total_processed': 0,
            'duplicates_found': 0,
            'unique_jobs': 0
        }
        
        logger.info(f"JobDeduplicator initialized with threshold {similarity_threshold}")
    
    def process_jobs(self, jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Process a list of jobs and return unique jobs and duplicates"""
        unique_jobs = []
        duplicates = []
        
        for job in jobs:
            self.stats['total_processed'] += 1
            
            if self.is_duplicate(job):
                duplicates.append(job)
                self.stats['duplicates_found'] += 1
            else:
                unique_jobs.append(job)
                self.add_job_fingerprint(job)
                self.stats['unique_jobs'] += 1
        
        logger.info(f"Processed {len(jobs)} jobs: {len(unique_jobs)} unique, {len(duplicates)} duplicates")
        return unique_jobs, duplicates
    
    def is_duplicate(self, job: Dict[str, Any]) -> bool:
        """Check if a job is a duplicate of existing jobs"""
        fingerprint = self.create_fingerprint(job)
        
        # Quick check: exact content hash match
        if fingerprint.content_hash in self.content_hashes:
            return True
        
        # Quick check: exact URL match
        url_normalized = fingerprint.url_normalized
        if url_normalized and url_normalized in self.url_to_hash:
            return True
        
        # Similarity-based duplicate detection
        for existing_hash, existing_fingerprint in self.job_fingerprints.items():
            similarity = self.calculate_similarity(fingerprint, existing_fingerprint)
            if similarity >= self.similarity_threshold:
                # Add to duplicate group
                self.duplicate_groups[existing_hash].append(fingerprint.content_hash)
                return True
        
        return False
    
    def add_job_fingerprint(self, job: Dict[str, Any]) -> str:
        """Add a job fingerprint to the deduplication system"""
        fingerprint = self.create_fingerprint(job)
        
        self.job_fingerprints[fingerprint.content_hash] = fingerprint
        self.content_hashes.add(fingerprint.content_hash)
        
        if fingerprint.url_normalized:
            self.url_to_hash[fingerprint.url_normalized] = fingerprint.content_hash
        
        return fingerprint.content_hash
    
    def create_fingerprint(self, job: Dict[str, Any]) -> JobFingerprint:
        """Create a unique fingerprint for a job"""
        # Normalize job fields
        title = self.normalize_text(job.get('title', ''))
        company = self.normalize_text(job.get('company', ''))
        location = self.normalize_location(job.get('location', ''))
        description = self.normalize_text(job.get('description', ''))
        url = self.normalize_url(job.get('url', ''))
        
        # Create content for hashing
        content_parts = [title, company, location]
        content_string = '|'.join(filter(None, content_parts))
        content_hash = hashlib.md5(content_string.encode()).hexdigest()
        
        # Create description hash
        description_hash = hashlib.md5(description.encode()).hexdigest() if description else ''
        
        # Create similarity tokens for fuzzy matching
        similarity_tokens = self.create_similarity_tokens(job)
        
        return JobFingerprint(
            content_hash=content_hash,
            title_normalized=title,
            company_normalized=company,
            location_normalized=location,
            url_normalized=url,
            description_hash=description_hash,
            similarity_tokens=similarity_tokens
        )
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ''
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common punctuation
        text = re.sub(r'[^\w\s-]', '', text)
        
        # Remove common job title prefixes/suffixes
        prefixes = ['senior', 'junior', 'lead', 'principal', 'staff', 'entry level']
        suffixes = ['remote', 'full time', 'part time', 'contract', 'freelance']
        
        words = text.split()
        filtered_words = []
        
        for word in words:
            if word not in prefixes and word not in suffixes:
                filtered_words.append(word)
        
        return ' '.join(filtered_words)
    
    def normalize_location(self, location: str) -> str:
        """Normalize location for comparison"""
        if not location:
            return ''
        
        location = location.lower().strip()
        
        # Common location normalizations
        location_mappings = {
            'remote': 'remote',
            'anywhere': 'remote',
            'work from home': 'remote',
            'wfh': 'remote',
            'usa': 'united states',
            'us': 'united states',
            'uk': 'united kingdom',
            'ny': 'new york',
            'nyc': 'new york',
            'sf': 'san francisco',
            'la': 'los angeles'
        }
        
        for pattern, replacement in location_mappings.items():
            if pattern in location:
                location = location.replace(pattern, replacement)
        
        # Remove common location suffixes
        suffixes = [', usa', ', us', ', united states']
        for suffix in suffixes:
            if location.endswith(suffix):
                location = location[:-len(suffix)]
        
        return location.strip()
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        if not url:
            return ''
        
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        
        # Remove trailing slash
        url = url.rstrip('/')
        
        # Convert to lowercase
        url = url.lower()
        
        return url
    
    def create_similarity_tokens(self, job: Dict[str, Any]) -> Set[str]:
        """Create tokens for similarity matching"""
        tokens = set()
        
        # Add title words
        title_words = self.normalize_text(job.get('title', '')).split()
        tokens.update(title_words)
        
        # Add company words
        company_words = self.normalize_text(job.get('company', '')).split()
        tokens.update(company_words)
        
        # Add key description words (first 100 words)
        description = job.get('description', '')
        if description:
            desc_words = self.normalize_text(description).split()[:100]
            tokens.update(desc_words)
        
        # Add location tokens
        location_words = self.normalize_location(job.get('location', '')).split()
        tokens.update(location_words)
        
        # Filter out common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        tokens = {token for token in tokens if token not in stop_words and len(token) > 2}
        
        return tokens
    
    def calculate_similarity(self, fp1: JobFingerprint, fp2: JobFingerprint) -> float:
        """Calculate similarity between two job fingerprints"""
        # Title similarity
        title_sim = SequenceMatcher(None, fp1.title_normalized, fp2.title_normalized).ratio()
        
        # Company similarity
        company_sim = SequenceMatcher(None, fp1.company_normalized, fp2.company_normalized).ratio()
        
        # Location similarity
        location_sim = SequenceMatcher(None, fp1.location_normalized, fp2.location_normalized).ratio()
        
        # Token-based similarity (Jaccard similarity)
        if fp1.similarity_tokens and fp2.similarity_tokens:
            intersection = len(fp1.similarity_tokens & fp2.similarity_tokens)
            union = len(fp1.similarity_tokens | fp2.similarity_tokens)
            token_sim = intersection / union if union > 0 else 0
        else:
            token_sim = 0
        
        # Weighted similarity score
        similarity = (
            title_sim * self.title_weight +
            company_sim * self.company_weight +
            location_sim * self.location_weight +
            token_sim * self.description_weight
        )
        
        return similarity
    
    def get_duplicate_groups(self) -> Dict[str, List[str]]:
        """Get groups of duplicate jobs"""
        return dict(self.duplicate_groups)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics"""
        return {
            **self.stats,
            'fingerprints_stored': len(self.job_fingerprints),
            'duplicate_groups': len(self.duplicate_groups),
            'deduplication_rate': self.stats['duplicates_found'] / max(self.stats['total_processed'], 1)
        }
    
    def clear_old_fingerprints(self, days: int = 30) -> int:
        """Clear old fingerprints to prevent memory bloat"""
        # This is a simplified implementation
        # In a real system, you'd track creation timestamps
        
        if len(self.job_fingerprints) > 10000:  # Arbitrary limit
            # Keep only the most recent 5000 fingerprints
            fingerprints_to_keep = 5000
            hashes_to_remove = list(self.job_fingerprints.keys())[:-fingerprints_to_keep]
            
            for hash_to_remove in hashes_to_remove:
                fingerprint = self.job_fingerprints.pop(hash_to_remove, None)
                if fingerprint:
                    self.content_hashes.discard(hash_to_remove)
                    # Remove from URL mapping
                    url_to_remove = None
                    for url, hash_val in self.url_to_hash.items():
                        if hash_val == hash_to_remove:
                            url_to_remove = url
                            break
                    if url_to_remove:
                        del self.url_to_hash[url_to_remove]
            
            logger.info(f"Cleared {len(hashes_to_remove)} old fingerprints")
            return len(hashes_to_remove)
        
        return 0

class AdvancedDeduplicator:
    """Advanced deduplication with machine learning-like features"""
    
    def __init__(self):
        self.basic_deduplicator = JobDeduplicator()
        self.company_aliases = self._load_company_aliases()
        self.location_aliases = self._load_location_aliases()
    
    def _load_company_aliases(self) -> Dict[str, str]:
        """Load known company aliases and variations"""
        return {
            'google inc': 'google',
            'alphabet inc': 'google',
            'facebook inc': 'meta',
            'meta platforms': 'meta',
            'amazon.com': 'amazon',
            'amazon web services': 'amazon',
            'aws': 'amazon',
            'microsoft corporation': 'microsoft',
            'apple inc': 'apple',
            'netflix inc': 'netflix',
            'uber technologies': 'uber',
            'airbnb inc': 'airbnb'
        }
    
    def _load_location_aliases(self) -> Dict[str, str]:
        """Load known location aliases and variations"""
        return {
            'san francisco bay area': 'san francisco',
            'sf bay area': 'san francisco',
            'silicon valley': 'san francisco',
            'new york city': 'new york',
            'manhattan': 'new york',
            'brooklyn': 'new york',
            'greater london': 'london',
            'london area': 'london',
            'los angeles area': 'los angeles',
            'la area': 'los angeles'
        }
    
    def normalize_company(self, company: str) -> str:
        """Normalize company name using aliases"""
        normalized = self.basic_deduplicator.normalize_text(company)
        return self.company_aliases.get(normalized, normalized)
    
    def normalize_location_advanced(self, location: str) -> str:
        """Advanced location normalization using aliases"""
        normalized = self.basic_deduplicator.normalize_location(location)
        return self.location_aliases.get(normalized, normalized)
    
    def detect_job_reposts(self, jobs: List[Dict[str, Any]], 
                          time_window_days: int = 7) -> List[Dict[str, Any]]:
        """Detect job reposts within a time window"""
        # Group jobs by normalized title and company
        job_groups = defaultdict(list)
        
        for job in jobs:
            key = (
                self.basic_deduplicator.normalize_text(job.get('title', '')),
                self.normalize_company(job.get('company', ''))
            )
            job_groups[key].append(job)
        
        reposts = []
        for group_jobs in job_groups.values():
            if len(group_jobs) > 1:
                # Sort by posted date if available
                try:
                    group_jobs.sort(key=lambda x: x.get('posted_date', ''), reverse=True)
                    # Keep the most recent, mark others as reposts
                    reposts.extend(group_jobs[1:])
                except:
                    # If sorting fails, mark all but first as reposts
                    reposts.extend(group_jobs[1:])
        
        return reposts

# Global deduplicator instance
_global_deduplicator: Optional[JobDeduplicator] = None

def get_deduplicator() -> JobDeduplicator:
    """Get or create the global deduplicator instance"""
    global _global_deduplicator
    if _global_deduplicator is None:
        _global_deduplicator = JobDeduplicator()
    return _global_deduplicator

# Convenience functions
def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Deduplicate a list of jobs"""
    deduplicator = get_deduplicator()
    return deduplicator.process_jobs(jobs)

def is_duplicate_job(job: Dict[str, Any]) -> bool:
    """Check if a single job is a duplicate"""
    deduplicator = get_deduplicator()
    return deduplicator.is_duplicate(job)

def add_job_to_deduplicator(job: Dict[str, Any]) -> str:
    """Add a job to the deduplication system"""
    deduplicator = get_deduplicator()
    return deduplicator.add_job_fingerprint(job)

def get_deduplication_stats() -> Dict[str, Any]:
    """Get deduplication statistics"""
    deduplicator = get_deduplicator()
    return deduplicator.get_stats()

def clear_old_duplicates(days: int = 30) -> int:
    """Clear old duplicate fingerprints"""
    deduplicator = get_deduplicator()
    return deduplicator.clear_old_fingerprints(days)