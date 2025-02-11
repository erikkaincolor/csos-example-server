from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
import redis
from fastapi.responses import FileResponse
import os
import requests
from dotenv import load_dotenv
import httpx

load_dotenv()

app = FastAPI()

# Connect to Redis
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

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://github.com/login/oauth/authorize",
    tokenUrl="https://github.com/login/oauth/access_token"
)


@app.get("/")
async def home():
    return {"message": "Welcome to the FastAPI server!"}

@app.get("/lessons/{lesson_name}")
async def serve_lesson(lesson_name: str):
     # Define the path to your lesson file
    lesson_path = f"public/lessons/{lesson_name}.zip"
    # /public/lessons/gd2_1-2           404
    # /public/lessons/gd2_1-2.zip       404
    # csos-example-server.onrender.com/lessons/gd2_1-2              202
    # csos-example-server.onrender.com/lessons/gd2_1-2.zip          404

    print(f"Looking for file at: {lesson_path}")

    # Check if the file exists
    if os.path.exists(lesson_path):
        return FileResponse(lesson_path)
    else:
        raise HTTPException(status_code=404, detail="Lesson not found")

# Function to verify GitHub user
def get_github_user(access_token: str):
    headers = {"Authorization": f"token {access_token}"}
    response = requests.get("https://api.github.com/user", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid GitHub token")
    return response.json()

# # GitHub OAuth callback
# https://www.youtube.com/watch?v=Pm938UxLEwQ

@app.get("/auth/github/callback")
async def github_callback(code: str, request: Request):
    print(f"OAuth Code: {code}")  # Debugging
    print(f"Received request: {request.method}")
    
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, headers=headers, data=payload)
        token_data = token_response.json()
        print(f"GitHub Token Response: {token_data}")  # Debugging
        access_token = token_data["access_token"]
        headers.update({"Authorization": f"bearer {access_token}"})

        user_response = await client.get("https://api.github.com/user", headers=headers)
        return user_response.json()


# Rate-limited lesson download
@app.get("/download/{lesson_name}")
async def download_lesson(lesson_name: str, token: str = Depends(oauth2_scheme)):
    user_data = get_github_user(token)
    user_id = user_data["id"]

    # Rate-limiting: Allow 5 downloads per hour
    download_count = redis_client.get(f"downloads:{user_id}")
    if download_count and int(download_count) >= 5:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    
    redis_client.incr(f"downloads:{user_id}")
    redis_client.expire(f"downloads:{user_id}", 3600)

    return {"message": f"Downloading {lesson_name}.zip", "url": f"https://csos-example-server.onrender.com/lessons/{lesson_name}.zip"}




# since i dont get free shell access for render.com, i will use subprocess to run shell commands
import subprocess

@app.get("/debug/list-lessons")
async def list_lessons():
    try:
        result = subprocess.run(["ls", "-R", "public/lessons/"], capture_output=True, text=True)
        return {"output": result.stdout}
    except Exception as e:
        return {"error": str(e)}
