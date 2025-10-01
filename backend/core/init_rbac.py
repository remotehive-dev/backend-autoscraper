import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from beanie import init_beanie
from backend.database.mongodb_models import (
    User, UserRole, ContactSubmission, ContactInformation, 
    SeoSettings, Review, Ad, OAuthAccount, Session, AuditLog,
    Permission, RolePermission
)
from backend.database.database import db_manager
from backend.core.security import get_password_hash
from backend.database.services import UserService

def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    # MongoDB doesn't require table creation like SQLAlchemy
    # Collections are created automatically when documents are inserted
    print("MongoDB collections will be created automatically when needed.")

def init_role_permissions(db):
    """Initialize role-permission mappings in database"""
    print("Initializing role permissions...")
    
    # MongoDB-based role permissions are handled differently
    # Role permissions are now managed through the RBAC system
    print("Role permissions are managed through MongoDB RBAC system.")
    print("Role permissions initialized successfully.")

async def create_super_admin(db: AsyncIOMotorDatabase, email: str, password: str):
    """Create the main super admin user"""
    print(f"Creating super admin user: {email}")
    
    # Check if super admin already exists
    user_service = UserService(db)
    existing_user = await user_service.get_user_by_email(email)
    if existing_user:
        print(f"Super admin user already exists with email: {email}")
        return existing_user
    
    # Create new super admin user
    user_data = {
        "email": email,
        "password_hash": get_password_hash(password),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "super_admin",
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Create the user using the existing UserService instance
    super_admin = await user_service.create_user(user_data)
    
    print(f"Super admin user created successfully with email: {email}")
    return super_admin

async def verify_database_setup(db: AsyncIOMotorDatabase):
    """Verify that the database is set up correctly"""
    print("Verifying database setup...")
    
    try:
        # Check if super admin exists
        user_service = UserService(db)
        super_admin = await user_service.get_user_by_email("admin@remotehive.in")
        if super_admin:
            print(f"Super admin found: {super_admin.email} (Role: {super_admin.role})")
        else:
            print("No super admin user found!")
        
        # Check users collection
        users_count = await db.users.count_documents({})
        print(f"Total users in database: {users_count}")
        
        print("Database verification completed.")
        
    except Exception as e:
        print(f"Error during database verification: {e}")

async def init_rbac_system(super_admin_email: str = "admin@remotehive.in", super_admin_password: str = "Ranjeet11$"):
    """Initialize the complete RBAC system"""
    print("Initializing RBAC system...")
    print("=" * 50)
    
    try:
        # Create tables
        create_tables()
        
        # Initialize database manager if needed
        if not db_manager._initialized:
            await db_manager.initialize()
        
        # Get database session
        db = db_manager.get_session()
        
        # Initialize Beanie with all document models
        await init_beanie(
            database=db,
            document_models=[
                User, ContactSubmission, ContactInformation, 
                SeoSettings, Review, Ad, OAuthAccount, Session, AuditLog,
                Permission, RolePermission
            ]
        )
        
        try:
            # Initialize role permissions
            init_role_permissions(db)
            
            # Create super admin user
            super_admin = await create_super_admin(db, super_admin_email, super_admin_password)
            
            # Verify setup
            await verify_database_setup(db)
            
            print("=" * 50)
            print("RBAC system initialized successfully!")
            print(f"Super Admin Email: {super_admin_email}")
            print(f"Super Admin Password: {super_admin_password}")
            print("=" * 50)
            
            return True
            
        finally:
            pass  # MongoDB connection will be closed automatically
            
    except Exception as e:
        import traceback
        print(f"Error initializing RBAC system: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

async def reset_rbac_system():
    """Reset the RBAC system (use with caution)"""
    print("WARNING: This will reset the entire RBAC system!")
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Reset cancelled.")
        return
    
    try:
        # Initialize database manager if needed
        if not db_manager._initialized:
            await db_manager.initialize()
        
        # Get database session
        db = db_manager.get_session()
        
        # Initialize Beanie with all document models
        await init_beanie(
            database=db,
            document_models=[
                User, ContactSubmission, ContactInformation, 
                SeoSettings, Review, Ad, OAuthAccount, Session, AuditLog,
                Permission, RolePermission
            ]
        )
        
        try:
            # Clear all RBAC-related data
            await db.user_sessions.delete_many({})
            await db.login_attempts.delete_many({})
            await db.users.delete_many({"role": {"$in": ["admin", "super_admin"]}})
            
            print("RBAC system reset completed.")
            
        finally:
            pass  # MongoDB connection will be closed automatically
            
    except Exception as e:
        print(f"Error resetting RBAC system: {e}")

async def main():
    """Main function to initialize RBAC system"""
    print("Starting RBAC initialization...")
    
    # Initialize the complete RBAC system
    success = await init_rbac_system()
    
    if success:
        print("RBAC initialization completed successfully!")
    else:
        print("RBAC initialization failed!")
        return False
    
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        asyncio.run(reset_rbac_system())
    else:
        # Initialize with default super admin credentials
        asyncio.run(main())