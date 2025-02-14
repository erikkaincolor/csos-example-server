import os
import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.responses import RedirectResponse
from starlette.requests import Request
from dotenv import load_dotenv

load_dotenv()

auth_router = APIRouter()

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


# GitHub OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# RENDER_URL = os.getenv("RENDER_URL", "https://csos-example-server.onrender.com")  # Ensure this is in .env

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://github.com/login/oauth/authorize",
    tokenUrl="https://github.com/login/oauth/access_token"
)

@auth_router.get("/github/login")
async def github_login():
    """Redirects users to GitHub OAuth login."""
    redirect_url = f"{GITHUB_AUTH_URL}?client_id={GITHUB_CLIENT_ID}&scope=read:user"
    return RedirectResponse(url=redirect_url)

# Function to verify GitHub user
# # GitHub OAuth callback
# https://www.youtube.com/watch?v=Pm938UxLEwQ

@auth_router.get("/github/callback")
async def github_callback(request: Request):
    """Handles GitHub OAuth callback and stores token in Redis."""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing GitHub authorization code")

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="GitHub token request failed")

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        # Fetch GitHub user info
        user_response = await client.get(GITHUB_USER_URL, headers={"Authorization": f"token {access_token}"})
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")
        
        # ----------------------------------------------
        # user_data = user_response.json()
        # github_username = user_data.get("login")

        # # Store token in Redis (expires in 1 hour)
        # redis_client.setex(f"github_token:{github_username}", 3600, access_token)

        # return {"message": "Authentication successful", "username": github_username}
        # ----------------------------------------------
        
        # Store the token in Redis for csos get tool file and /get-token endpoint
        redis_client.set("github_token", access_token, ex=3600)  # Store for 1 hour
        
        return {"access_token": access_token}  # Return only the token, not the full response



@auth_router.get("/get-token")
async def get_token(request: Request):
    """Allows the CLI to poll for an authenticated token."""
    # Get the token directly since we're not using username-specific storage
    token = redis_client.get("github_token")
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    
    return {"access_token": token}
