from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

class CarouselType(str, Enum):
    HERO = "hero"
    TESTIMONIAL = "testimonial"
    PRODUCT = "product"
    GALLERY = "gallery"

class PageStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# CMS Page Models
class CMSPageBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    content: Optional[str] = None
    meta_title: Optional[str] = Field(None, max_length=60)
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[str] = Field(None, max_length=255)
    featured_image: Optional[str] = None
    status: PageStatus = PageStatus.DRAFT
    publish_date: Optional[datetime] = None
    is_homepage: bool = False
    template: Optional[str] = "default"
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None

class CMSPageCreate(CMSPageBase):
    pass

class CMSPageUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = None
    meta_title: Optional[str] = Field(None, max_length=60)
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[str] = Field(None, max_length=255)
    featured_image: Optional[str] = None
    status: Optional[PageStatus] = None
    publish_date: Optional[datetime] = None
    is_homepage: Optional[bool] = None
    template: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None

class CMSPage(CMSPageBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    views: int = 0

    class Config:
        from_attributes = True

class CMSPageResponse(BaseModel):
    data: CMSPage

# SEO Settings Models
class SEOSettingsBase(BaseModel):
    site_title: Optional[str] = Field(None, max_length=60)
    site_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[str] = Field(None, max_length=255)
    og_title: Optional[str] = Field(None, max_length=60)
    og_description: Optional[str] = Field(None, max_length=160)
    og_image: Optional[str] = None
    og_type: Optional[str] = "website"
    twitter_card: Optional[str] = "summary_large_image"
    twitter_site: Optional[str] = None
    twitter_creator: Optional[str] = None
    canonical_url: Optional[str] = None
    robots_txt: Optional[str] = None
    sitemap_url: Optional[str] = None
    google_analytics_id: Optional[str] = None
    google_tag_manager_id: Optional[str] = None
    facebook_pixel_id: Optional[str] = None
    google_site_verification: Optional[str] = None
    bing_site_verification: Optional[str] = None

class SEOSettingsUpdate(SEOSettingsBase):
    pass

class SEOSettings(SEOSettingsBase):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Review Models
class ReviewBase(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1)
    company: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    status: ReviewStatus = ReviewStatus.PENDING
    featured: bool = False
    helpful_count: int = 0
    verified: bool = False

class ReviewCreate(ReviewBase):
    pass

class ReviewUpdate(BaseModel):
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    company: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    status: Optional[ReviewStatus] = None
    featured: Optional[bool] = None
    verified: Optional[bool] = None

class Review(ReviewBase):
    id: str
    created_at: datetime
    updated_at: datetime
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True

class ReviewResponse(BaseModel):
    data: Review

# Theme Settings Models
class ThemeSettingsBase(BaseModel):
    primary_color: Optional[str] = "#3B82F6"
    secondary_color: Optional[str] = "#10B981"
    accent_color: Optional[str] = "#F59E0B"
    background_color: Optional[str] = "#FFFFFF"
    text_color: Optional[str] = "#1F2937"
    link_color: Optional[str] = "#3B82F6"
    font_family: Optional[str] = "Inter"
    font_size_base: Optional[str] = "16px"
    line_height: Optional[str] = "1.6"
    border_radius: Optional[str] = "8px"
    shadow: Optional[str] = "0 1px 3px rgba(0, 0, 0, 0.1)"
    logo_url: Optional[str] = None
    logo_alt: Optional[str] = None
    favicon_url: Optional[str] = None
    header_height: Optional[str] = "64px"
    footer_text: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None

class ThemeSettingsUpdate(ThemeSettingsBase):
    pass

class ThemeSettings(ThemeSettingsBase):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Analytics Models
class AnalyticsData(BaseModel):
    page_views: int
    unique_visitors: int
    bounce_rate: float
    avg_session_duration: str
    top_pages: List[Dict[str, Any]]
    traffic_sources: List[Dict[str, Any]]
    conversion_rate: Optional[float] = None
    goal_completions: Optional[int] = None

# Ad Campaign Models
class AdCampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(..., min_length=1, max_length=50)  # Google Ads, Meta, etc.
    campaign_type: Optional[str] = None  # Search, Display, Video, etc.
    status: str = "active"  # active, paused, ended
    budget: Optional[str] = None
    daily_budget: Optional[float] = None
    total_budget: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = None
    ad_copy: Optional[str] = None
    landing_page: Optional[str] = None

class AdCampaignCreate(AdCampaignBase):
    pass

class AdCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    platform: Optional[str] = Field(None, min_length=1, max_length=50)
    campaign_type: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[str] = None
    daily_budget: Optional[float] = None
    total_budget: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = None
    ad_copy: Optional[str] = None
    landing_page: Optional[str] = None

class AdCampaign(AdCampaignBase):
    id: str
    created_at: datetime
    updated_at: datetime
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    cost: float = 0.0
    ctr: float = 0.0  # Click-through rate
    cpc: float = 0.0  # Cost per click
    cpa: float = 0.0  # Cost per acquisition

    class Config:
        from_attributes = True

# Generic Response Models
class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]]
    count: int
    page: int
    limit: int
    pages: int

class MessageResponse(BaseModel):
    message: str
    data: Optional[Dict[str, Any]] = None

# Website Analytics Models
class WebsiteStats(BaseModel):
    total_pages: int
    published_pages: int
    draft_pages: int
    total_reviews: int
    approved_reviews: int
    pending_reviews: int
    featured_reviews: int
    monthly_visitors: int
    monthly_page_views: int
    bounce_rate: float
    avg_session_duration: str

# Content Block Models (for page builder)
class ContentBlock(BaseModel):
    id: str
    type: str  # text, image, video, button, etc.
    content: Dict[str, Any]
    order: int
    styles: Optional[Dict[str, Any]] = None

class PageTemplate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    blocks: List[ContentBlock]
    is_default: bool = False
    category: Optional[str] = None

# Menu/Navigation Models
class NavigationItem(BaseModel):
    id: str
    label: str
    url: str
    target: Optional[str] = "_self"  # _self, _blank
    order: int
    parent_id: Optional[str] = None

# Media Library Models
class MediaFileBase(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    original_filename: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1)
    file_url: str = Field(..., min_length=1)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., min_length=1, max_length=100)
    media_type: MediaType
    alt_text: Optional[str] = Field(None, max_length=255)
    caption: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    folder: Optional[str] = Field(None, max_length=100)
    is_public: bool = True

class MediaFileCreate(MediaFileBase):
    pass

class MediaFileUpdate(BaseModel):
    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    alt_text: Optional[str] = Field(None, max_length=255)
    caption: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    folder: Optional[str] = Field(None, max_length=100)
    is_public: Optional[bool] = None

class MediaFile(MediaFileBase):
    id: str
    created_at: datetime
    updated_at: datetime
    uploaded_by: Optional[str] = None
    download_count: int = 0

    class Config:
        from_attributes = True

# Carousel Management Models
class CarouselItemBase(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=500)
    image_url: str = Field(..., min_length=1)
    link_url: Optional[str] = None
    link_text: Optional[str] = Field(None, max_length=50)
    order: int = Field(default=0)
    is_active: bool = True
    carousel_type: CarouselType

class CarouselItemCreate(CarouselItemBase):
    pass

class CarouselItemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    link_text: Optional[str] = Field(None, max_length=50)
    order: Optional[int] = None
    is_active: Optional[bool] = None
    carousel_type: Optional[CarouselType] = None

class CarouselItem(CarouselItemBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

# Image Gallery Models
class GalleryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    slug: str = Field(..., min_length=1, max_length=100)
    is_public: bool = True
    cover_image: Optional[str] = None

class GalleryCreate(GalleryBase):
    pass

class GalleryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    is_public: Optional[bool] = None
    cover_image: Optional[str] = None

class Gallery(GalleryBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    image_count: int = 0

    class Config:
        from_attributes = True

class GalleryImageBase(BaseModel):
    gallery_id: str
    media_file_id: str
    order: int = Field(default=0)
    caption: Optional[str] = Field(None, max_length=500)
    is_featured: bool = False

class GalleryImageCreate(GalleryImageBase):
    pass

class GalleryImageUpdate(BaseModel):
    order: Optional[int] = None
    caption: Optional[str] = Field(None, max_length=500)
    is_featured: Optional[bool] = None

class GalleryImage(GalleryImageBase):
    id: str
    created_at: datetime
    media_file: Optional[MediaFile] = None

    class Config:
        from_attributes = True
    is_active: bool = True
    icon: Optional[str] = None
    css_class: Optional[str] = None

class NavigationMenu(BaseModel):
    id: str
    name: str
    location: str  # header, footer, sidebar
    items: List[NavigationItem]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime