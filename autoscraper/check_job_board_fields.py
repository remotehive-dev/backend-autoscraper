import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

async def check_job_board_fields():
    # MongoDB Atlas connection string
    mongodb_url = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    
    print("Connecting to MongoDB Atlas...")
    
    # Use synchronous client for easier debugging
    client = MongoClient(mongodb_url)
    
    try:
        db = client['remotehive_autoscraper']
        job_boards_collection = db['job_boards']
        
        # Get a sample job board to see its structure
        sample_board = job_boards_collection.find_one()
        
        if sample_board:
            print("Sample job board document structure:")
            print("Fields in database:")
            for key, value in sample_board.items():
                print(f"  - {key}: {type(value).__name__} = {value if len(str(value)) < 100 else str(value)[:100] + '...'}")
            
            print("\nExpected fields by Beanie model:")
            expected_fields = [
                'name', 'type', 'base_url', 'search_url_template', 'region', 'is_active',
                'rate_limit_delay', 'max_pages_per_search', 'selectors', 'headers', 'cookies',
                'proxy_enabled', 'javascript_required', 'captcha_protection', 'requires_login',
                'login_url', 'login_credentials', 'api_key', 'api_endpoint', 'last_successful_scrape',
                'total_jobs_scraped', 'success_rate', 'average_response_time', 'notes',
                'created_at', 'updated_at'
            ]
            
            print("\nField mapping analysis:")
            for field in expected_fields:
                if field in sample_board:
                    print(f"  ✓ {field}: EXISTS")
                else:
                    print(f"  ✗ {field}: MISSING")
            
            print("\nExtra fields in database (not in model):")
            for key in sample_board.keys():
                if key not in expected_fields and key != '_id':
                    print(f"  + {key}: {type(sample_board[key]).__name__}")
        
        else:
            print("No job board documents found")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()
        print("\nDisconnected from MongoDB Atlas")

if __name__ == "__main__":
    asyncio.run(check_job_board_fields())