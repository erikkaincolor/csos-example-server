import os
import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException
import logging
from fastapi.responses import RedirectResponse
from starlette.requests import Request
from dotenv import load_dotenv

load_dotenv()
auth_router = APIRouter()

# Configure logger
logger = logging.getLogger(__name__)

auth_router = APIRouter()

required_env_vars = ["REDIS_HOST", "REDIS_PORT", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "REDIRECT_URI"]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")
    
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"), 
    port=os.getenv("REDIS_PORT"), 
    # password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True
)

# Test Connection
try:
    redis_client.ping()
    print("✅ Connected to Redis!")
except redis.exceptions.ConnectionError:
    print("❌ Redis connection failed.")


# RENDER_URL = os.getenv("RENDER_URL", "https://csos-example-server.onrender.com")  # Ensure this is in .env

# SUNSET
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# SUNSET
# @auth_router.get("/github/login")
# async def github_login():
#     """Redirects users to GitHub OAuth login."""
#     redirect_url = f"{GITHUB_AUTH_URL}?client_id={GITHUB_CLIENT_ID}&scope=read:user"
#     return RedirectResponse(url=redirect_url)


# TEST
# GitHub OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
# TEST

# Function to verify GitHub user
# # GitHub OAuth callback
# https://www.youtube.com/watch?v=Pm938UxLEwQ
# SUNSET
# @auth_router.get("/github/callback")
# async def github_callback(request: Request):
#     """Handles GitHub OAuth callback and stores token in Redis."""
#     code = request.query_params.get("code")
#     if not code:
#         raise HTTPException(status_code=400, detail="Missing GitHub authorization code")

#     async with httpx.AsyncClient() as client:
#         token_response = await client.post(
#             GITHUB_TOKEN_URL,
#             data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
#             headers={"Accept": "application/json"},
#         )
#         if token_response.status_code != 200:
#             raise HTTPException(status_code=400, detail="GitHub token request failed")

#         token_data = token_response.json()
#         access_token = token_data.get("access_token")

#         # Fetch GitHub user info
#         user_response = await client.get(GITHUB_USER_URL, headers={"Authorization": f"token {access_token}"})
#         if user_response.status_code != 200:
#             raise HTTPException(status_code=400, detail="Failed to fetch user info")
        
#         # ----------------------------------------------
#         # user_data = user_response.json()
#         # github_username = user_data.get("login")

#         # # Store token in Redis (expires in 1 hour)
#         # redis_client.setex(f"github_token:{github_username}", 3600, access_token)

#         # return {"message": "Authentication successful", "username": github_username}
#         # ----------------------------------------------
        
#         # Store the token in Redis for csos get tool file and /get-token endpoint
#         redis_client.set("github_token", access_token, ex=3600)  # Store for 1 hour
        
#         return {"access_token": access_token}  # Return only the token, not the full response

# TEST
@auth_router.get("/auth/github/callback")
async def github_callback(code: str, request: Request):
    logger.debug(f"OAuth Code: {code}")  
    logger.debug(f"Received request: {request.method}")
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code, 
        "redirect_uri": REDIRECT_URI }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
                GITHUB_TOKEN_URL,
                data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
                headers={"Accept": "application/json"},
            )
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="GitHub token request failed")

        token_data = token_response.json()
        logger.debug(f"Token_data: {token_data}")
        
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="Invalid response from GitHub")
                # Fetch GitHub user info
        user_response = await client.get(GITHUB_USER_URL, headers={"Authorization": f"token {access_token}"})

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")
        user_data = user_response.json()
        github_username = user_data.get("login")

        # Store token in Redis (expires in 1 hour)
        redis_client.setex(f"github_token:{github_username}", 3600, access_token)

        return {"message": "Authentication successful", "username": github_username}
        
        
        return {"access_token": token_data["access_token"]}  # Return only the token, not the full response



# SUNSET
# @auth_router.get("/get-token")
# async def get_token(request: Request):
#     """Allows the CLI to poll for an authenticated token."""
#     # Get the token directly since we're not using username-specific storage
#     token = redis_client.get("github_token")
    
#     if not token:
#         raise HTTPException(status_code=404, detail="Token not found or expired")
    
#     return {"access_token": token}

# TEST
# to expose github auth token to the csos get tool file
@auth_router.get("/get-token")
async def get_token():
    """Endpoint to return the GitHub OAuth token."""
    # Fetch the token from Redis or generate it dynamically
    token = redis_client.get("github_token")
    logger.debug(f"GitHub Token: {token}")
    # Store the token in Redis after GitHub OAuth flow

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"access_token": token}


