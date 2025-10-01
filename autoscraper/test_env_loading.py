#!/usr/bin/env python3
"""
Test environment variable loading
"""

import os
from config.settings import get_settings

print("=== ENVIRONMENT VARIABLE LOADING TEST ===")

# Test direct os.getenv
print(f"\n1. Direct os.getenv:")
print(f"   MONGODB_URL: {os.getenv('MONGODB_URL', 'NOT_FOUND')}")
print(f"   MONGODB_DATABASE_NAME: {os.getenv('MONGODB_DATABASE_NAME', 'NOT_FOUND')}")
print(f"   AUTOSCRAPER_MONGODB_URL: {os.getenv('AUTOSCRAPER_MONGODB_URL', 'NOT_FOUND')}")
print(f"   AUTOSCRAPER_MONGODB_DATABASE_NAME: {os.getenv('AUTOSCRAPER_MONGODB_DATABASE_NAME', 'NOT_FOUND')}")

# Test settings loading
print(f"\n2. Settings loading:")
settings = get_settings()
print(f"   settings.MONGODB_URL: {settings.MONGODB_URL}")
print(f"   settings.MONGODB_DATABASE_NAME: {settings.MONGODB_DATABASE_NAME}")

# Test if .env file exists and is readable
print(f"\n3. .env file check:")
env_file_path = ".env"
if os.path.exists(env_file_path):
    print(f"   .env file exists: {os.path.abspath(env_file_path)}")
    with open(env_file_path, 'r') as f:
        lines = f.readlines()[:10]  # First 10 lines
        print(f"   First few lines:")
        for i, line in enumerate(lines, 1):
            if 'MONGODB' in line:
                print(f"     {i}: {line.strip()}")
else:
    print(f"   .env file not found at: {os.path.abspath(env_file_path)}")

print("\n=== TEST COMPLETE ===")