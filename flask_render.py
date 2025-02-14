import os
import logging
import redis
import httpx
import subprocess
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate required environment variables
required_env_vars = [
    "REDIS_HOST", "REDIS_PORT", "GITHUB_CLIENT_ID", 
    "GITHUB_CLIENT_SECRET", "REDIRECT_URI"
]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Initialize FastAPI app
app = FastAPI()

# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    password=os.getenv("REDIS_PASSWORD", ""),  # Optional password
    decode_responses=True
)

# Test Redis connection
try:
    redis_client.ping()
    logger.info("✅ Connected to Redis!")
except redis.exceptions.ConnectionError as e:
    logger.error(f"❌ Redis connection failed: {e}")
    raise

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://github.com/login/oauth/authorize",
    tokenUrl="https://github.com/login/oauth/access_token"
)

# Root endpoint
@app.get("/")
async def home():
    return {"message": "Welcome to the FastAPI server!"}

# Serve lesson files
@app.get("/lessons/{lesson_name}")
async def serve_lesson(lesson_name: str):
    # Define the path to the lesson file
    lesson_path = os.path.join("public", "lessons", f"{lesson_name}.zip")
    logger.info(f"Looking for file at: {lesson_path}")

    # Check if the file exists
    if os.path.exists(lesson_path):
        return FileResponse(lesson_path, filename=f"{lesson_name}.zip")
    else:
        raise HTTPException(status_code=404, detail="Lesson not found")

# GitHub OAuth callback
@app.get("/auth/github/callback")
async def github_callback(code: str, request: Request):
    logger.info("Received GitHub OAuth callback")
    
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, headers=headers, data=payload)
        
        if token_response.status_code != 200:
            logger.error(f"Failed to fetch access token: {token_response.text}")
            raise HTTPException(status_code=token_response.status_code, detail="Failed to fetch access token")

        token_data = token_response.json()
        
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="Invalid response from GitHub")

        # Store the token in Redis
        redis_client.set("github_token", token_data["access_token"], ex=3600)  # Store for 1 hour
        
        return {"access_token": token_data["access_token"]}

# Endpoint to retrieve the GitHub OAuth token
@app.get("/get-token")
async def get_token():
    """Endpoint to return the GitHub OAuth token."""
    token = redis_client.get("github_token")
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"access_token": token}

# Rate-limited lesson download
@app.get("/download/{lesson_name}")
async def download_lesson(lesson_name: str, token: str = Depends(oauth2_scheme)):
    # Fetch user data from GitHub
    user_data = await get_github_user(token)
    user_id = user_data["id"]

    # Rate-limiting: Allow 5 downloads per hour
    download_count = redis_client.get(f"downloads:{user_id}")
    if download_count and int(download_count) >= 5:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    
    redis_client.incr(f"downloads:{user_id}")
    redis_client.expire(f"downloads:{user_id}", 3600)

    return {"message": f"Downloading {lesson_name}.zip", "url": f"/lessons/{lesson_name}.zip"}

# Helper function to fetch GitHub user data
async def get_github_user(token: str):
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}"}
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to fetch user data")
        return user_response.json()

# Debug endpoint to list lesson files
@app.get("/debug/list-lessons")
async def list_lessons():
    try:
        result = subprocess.run(
            ["ls", "-R", "public/lessons/"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return JSONResponse(status_code=500, content={"error": result.stderr})
        return {"output": result.stdout}
    except Exception as e:
        logger.error(f"Error listing lessons: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})