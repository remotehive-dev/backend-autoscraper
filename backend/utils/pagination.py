from typing import Optional, List, Dict, Any, TypeVar, Generic, Union
# from sqlalchemy.orm import Query, Session  # Using MongoDB instead
# from sqlalchemy import desc, asc, func, text  # Using MongoDB instead
from pydantic import BaseModel, Field
from datetime import datetime
import base64
import json
from urllib.parse import urlencode

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Standard pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters for better performance on large datasets"""
    cursor: Optional[str] = Field(default=None, description="Cursor for pagination")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

class CursorPaginationMeta(BaseModel):
    """Cursor pagination metadata"""
    size: int
    has_next: bool
    has_prev: bool
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    sort_by: str
    sort_order: str

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response"""
    items: List[T]
    meta: PaginationMeta
    
class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Cursor-based paginated response"""
    items: List[T]
    meta: CursorPaginationMeta

class PaginationHelper:
    """Helper class for database pagination operations"""
    
    @staticmethod
    def paginate_query(
        query: Query,
        params: PaginationParams,
        count_query: Optional[Query] = None
    ) -> Dict[str, Any]:
        """
        Apply offset-based pagination to a SQLAlchemy query.
        
        Args:
            query: The SQLAlchemy query to paginate
            params: Pagination parameters
            count_query: Optional separate query for counting (for performance)
            
        Returns:
            Dictionary with items and pagination metadata
        """
        # Apply sorting
        if params.sort_by:
            sort_column = getattr(query.column_descriptions[0]['type'], params.sort_by, None)
            if sort_column:
                if params.sort_order == "desc":
                    query = query.order_by(desc(sort_column))
                else:
                    query = query.order_by(asc(sort_column))
        
        # Get total count
        if count_query:
            total = count_query.scalar()
        else:
            total = query.count()
        
        # Calculate pagination
        offset = (params.page - 1) * params.size
        pages = (total + params.size - 1) // params.size  # Ceiling division
        
        # Apply pagination
        items = query.offset(offset).limit(params.size).all()
        
        # Create metadata
        meta = PaginationMeta(
            page=params.page,
            size=params.size,
            total=total,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
            next_page=params.page + 1 if params.page < pages else None,
            prev_page=params.page - 1 if params.page > 1 else None
        )
        
        return {
            "items": items,
            "meta": meta
        }
    
    @staticmethod
    def cursor_paginate_query(
        query: Query,
        params: CursorPaginationParams,
        cursor_column: str = "id"
    ) -> Dict[str, Any]:
        """
        Apply cursor-based pagination to a SQLAlchemy query.
        More efficient for large datasets as it doesn't require counting.
        
        Args:
            query: The SQLAlchemy query to paginate
            params: Cursor pagination parameters
            cursor_column: Column to use for cursor (should be unique and sortable)
            
        Returns:
            Dictionary with items and cursor pagination metadata
        """
        # Get the model class from query
        model_class = query.column_descriptions[0]['type']
        
        # Get sort column
        sort_column = getattr(model_class, params.sort_by, getattr(model_class, cursor_column))
        cursor_col = getattr(model_class, cursor_column)
        
        # Apply sorting
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column), desc(cursor_col))
        else:
            query = query.order_by(asc(sort_column), asc(cursor_col))
        
        # Apply cursor filter if provided
        if params.cursor:
            try:
                cursor_data = PaginationHelper._decode_cursor(params.cursor)
                cursor_value = cursor_data.get('value')
                cursor_id = cursor_data.get('id')
                
                if cursor_value is not None and cursor_id is not None:
                    if params.sort_order == "desc":
                        query = query.filter(
                            (sort_column < cursor_value) |
                            ((sort_column == cursor_value) & (cursor_col < cursor_id))
                        )
                    else:
                        query = query.filter(
                            (sort_column > cursor_value) |
                            ((sort_column == cursor_value) & (cursor_col > cursor_id))
                        )
            except Exception:
                # Invalid cursor, ignore and start from beginning
                pass
        
        # Fetch one extra item to check if there's a next page
        items = query.limit(params.size + 1).all()
        
        # Check if there are more items
        has_next = len(items) > params.size
        if has_next:
            items = items[:-1]  # Remove the extra item
        
        # Generate cursors
        next_cursor = None
        prev_cursor = None
        
        if items:
            if has_next:
                last_item = items[-1]
                next_cursor = PaginationHelper._encode_cursor(
                    getattr(last_item, params.sort_by, getattr(last_item, cursor_column)),
                    getattr(last_item, cursor_column)
                )
            
            if params.cursor:  # If we have a cursor, we can go back
                first_item = items[0]
                prev_cursor = PaginationHelper._encode_cursor(
                    getattr(first_item, params.sort_by, getattr(first_item, cursor_column)),
                    getattr(first_item, cursor_column),
                    reverse=True
                )
        
        # Create metadata
        meta = CursorPaginationMeta(
            size=params.size,
            has_next=has_next,
            has_prev=params.cursor is not None,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            sort_by=params.sort_by,
            sort_order=params.sort_order
        )
        
        return {
            "items": items,
            "meta": meta
        }
    
    @staticmethod
    def _encode_cursor(value: Any, id_value: Any, reverse: bool = False) -> str:
        """Encode cursor data to base64 string"""
        cursor_data = {
            'value': value.isoformat() if isinstance(value, datetime) else value,
            'id': id_value,
            'reverse': reverse
        }
        cursor_json = json.dumps(cursor_data, default=str)
        return base64.b64encode(cursor_json.encode()).decode()
    
    @staticmethod
    def _decode_cursor(cursor: str) -> Dict[str, Any]:
        """Decode cursor from base64 string"""
        cursor_json = base64.b64decode(cursor.encode()).decode()
        return json.loads(cursor_json)
    
    @staticmethod
    def create_search_query(
        session: Session,
        model_class,
        search_term: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        search_fields: Optional[List[str]] = None
    ) -> Query:
        """
        Create a search query with optional full-text search and filters.
        
        Args:
            session: Database session
            model_class: SQLAlchemy model class
            search_term: Text to search for
            filters: Dictionary of field filters
            search_fields: List of fields to search in
            
        Returns:
            SQLAlchemy query object
        """
        query = session.query(model_class)
        
        # Apply text search
        if search_term and search_fields:
            search_conditions = []
            for field in search_fields:
                if hasattr(model_class, field):
                    column = getattr(model_class, field)
                    search_conditions.append(column.ilike(f"%{search_term}%"))
            
            if search_conditions:
                # from sqlalchemy import or_  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
                query = query.filter(or_(*search_conditions))
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(model_class, field) and value is not None:
                    column = getattr(model_class, field)
                    if isinstance(value, list):
                        query = query.filter(column.in_(value))
                    elif isinstance(value, dict):
                        # Range filters
                        if 'gte' in value:
                            query = query.filter(column >= value['gte'])
                        if 'lte' in value:
                            query = query.filter(column <= value['lte'])
                        if 'gt' in value:
                            query = query.filter(column > value['gt'])
                        if 'lt' in value:
                            query = query.filter(column < value['lt'])
                    else:
                        query = query.filter(column == value)
        
        return query
    
    @staticmethod
    def get_optimized_count(session: Session, query: Query) -> int:
        """
        Get optimized count for large tables using PostgreSQL-specific optimizations.
        
        Args:
            session: Database session
            query: Query to count
            
        Returns:
            Approximate or exact count
        """
        try:
            # For PostgreSQL, try to get approximate count for better performance
            if session.bind.dialect.name == 'postgresql':
                # Get table name from query
                table_name = query.column_descriptions[0]['type'].__tablename__
                
                # Use pg_stat_user_tables for approximate count on large tables
                approx_result = session.execute(text(
                    "SELECT n_tup_ins - n_tup_del AS approx_count "
                    "FROM pg_stat_user_tables WHERE relname = :table_name"
                ), {'table_name': table_name}).scalar()
                
                if approx_result and approx_result > 100000:  # Use approximation for large tables
                    return max(0, approx_result)
            
            # Fall back to exact count
            return query.count()
            
        except Exception:
            # If anything fails, use standard count
            return query.count()

class AsyncPaginationHelper:
    """Async version of pagination helper for async database operations"""
    
    @staticmethod
    async def async_paginate_query(
        query,  # AsyncQuery type
        params: PaginationParams,
        session  # AsyncSession type
    ) -> Dict[str, Any]:
        """
        Async version of paginate_query for use with async SQLAlchemy.
        Note: This is a placeholder for async implementation.
        """
        # This would be implemented when async database operations are needed
        raise NotImplementedError("Async pagination not yet implemented")

# Utility functions for common pagination patterns
def paginate_users(session: Session, params: PaginationParams, search: Optional[str] = None) -> Dict[str, Any]:
    """Paginate users with optional search"""
    # TODO: MongoDB Migration - Update imports to use MongoDB models
    # from backend.database.models import User
    from backend.models.mongodb_models import User
    
    query = PaginationHelper.create_search_query(
        session=session,
        model_class=User,
        search_term=search,
        search_fields=['email', 'first_name', 'last_name']
    )
    
    return PaginationHelper.paginate_query(query, params)

def paginate_job_posts(
    session: Session, 
    params: PaginationParams, 
    search: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Paginate job posts with search and filters"""
    # TODO: MongoDB Migration - Update imports to use MongoDB models
    # from backend.database.models import JobPost
    from backend.models.mongodb_models import JobPost
    
    query = PaginationHelper.create_search_query(
        session=session,
        model_class=JobPost,
        search_term=search,
        filters=filters,
        search_fields=['title', 'description', 'location']
    )
    
    return PaginationHelper.paginate_query(query, params)

def cursor_paginate_job_applications(
    session: Session,
    params: CursorPaginationParams,
    job_seeker_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cursor paginate job applications for better performance"""
    # TODO: MongoDB Migration - Update imports to use MongoDB models
    # from backend.database.models import JobApplication
    from backend.models.mongodb_models import JobApplication
    
    query = session.query(JobApplication)
    
    if job_seeker_id:
        query = query.filter(JobApplication.job_seeker_id == job_seeker_id)
    
    return PaginationHelper.cursor_paginate_query(query, params, cursor_column="id")