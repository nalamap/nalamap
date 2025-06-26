from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
# General config in a central place


# File & Data Management

## Optional Azure Blob storage
USE_AZURE = os.getenv("USE_AZURE_STORAGE", "false").lower() == "true"
AZ_CONN = os.getenv("AZURE_CONN_STRING", "")
AZ_CONTAINER = os.getenv("AZURE_CONTAINER", "")

## Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

## File size limit (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


# Database

# Database connection URL
DATABASE_URL = os.getenv("DATABASE_AZURE_URL")
