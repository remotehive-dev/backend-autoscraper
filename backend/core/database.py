from loguru import logger
from backend.database.database import init_database, get_database_manager
from backend.models.mongodb_models import User, UserRole

# Database session dependency for FastAPI
def get_db():
    """Get MongoDB database for FastAPI dependency injection"""
    try:
        db_manager = get_database_manager()
        if not db_manager._initialized:
            logger.error("Database manager not initialized")
            raise Exception("Database manager not initialized")
        return db_manager.get_session()
    except Exception as e:
        logger.error(f"Error getting MongoDB database: {e}")
        raise

async def get_database():
    """Get MongoDB database instance asynchronously"""
    try:
        db_manager = get_database_manager()
        if not db_manager._initialized:
            logger.error("Database manager not initialized")
            raise Exception("Database manager not initialized")
        return db_manager.get_session()
    except Exception as e:
        logger.error(f"Error getting MongoDB database: {e}")
        raise

async def init_db():
    """Initialize MongoDB and create default data"""
    try:
        # Initialize MongoDB collections and indexes
        await init_database()
        logger.info("MongoDB collections initialized successfully")
        
        # Create default super admin user
        await create_default_data()
        
    except Exception as e:
        logger.error(f"Error initializing MongoDB: {e}")
        raise

async def create_default_data():
    """Create default data like super admin user"""
    try:
        # Import here to avoid circular import
        from backend.core.password_utils import get_password_hash
        
        # Check if super admin exists
        existing_admin = await User.find_one({"email": "admin@remotehive.in"})
        
        if not existing_admin:
            # Create super admin user
            super_admin = User(
                email="admin@remotehive.in",
                password_hash=get_password_hash("Ranjeet11$"),
                first_name="Super",
                last_name="Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_verified=True
            )
            
            # Save user to MongoDB
            await super_admin.insert()
            logger.info("Super admin user created successfully")
        else:
            logger.info("Super admin user already exists")
        
    except Exception as e:
        logger.error(f"Error creating default data: {e}")
        # Don't raise here as this is not critical for app startup

async def health_check() -> bool:
    """Check MongoDB health"""
    try:
        # Simple MongoDB health check by attempting to find a user
        # This will test the MongoDB connection
        await User.find_one()
        return True
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return False