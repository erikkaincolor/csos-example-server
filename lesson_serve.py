import os
import redis
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

lesson_router = APIRouter()
# redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"), 
    port=os.getenv("REDIS_PORT"), 
    # password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True
)
LESSON_PATH = "public/lessons/"
RATE_LIMIT = 5  # Max 5 downloads per hour

@lesson_router.get("/{lesson_name}")
async def get_lesson(lesson_name: str, authorization: str = Header(None)):
    """Serves a lesson ZIP file after authentication and rate-limit check."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization token")

    token = authorization.split(" ")[1]

    # Validate token with GitHub API
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid GitHub token")

        user_data = response.json()
        github_username = user_data.get("login")

    # Check rate limit
    rate_key = f"rate_limit:{github_username}"
    download_count = redis_client.get(rate_key) or 0
    if int(download_count) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (5 downloads per hour)")

    # Serve lesson file
    lesson_file = os.path.join(LESSON_PATH, f"{lesson_name}.zip")
    if not os.path.exists(lesson_file):
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Increment rate limit count
    redis_client.incr(rate_key)
    redis_client.expire(rate_key, 3600)  # Reset count after 1 hour

    return FileResponse(lesson_file, filename=f"{lesson_name}.zip", media_type="application/zip")


@lesson_router.get("/debug/list-lessons")
async def list_lessons():
    """Lists all available lessons in the public/lessons directory."""
    if not os.path.exists(LESSON_PATH):
        raise HTTPException(status_code=500, detail="Lessons directory missing")

    lessons = [f.replace(".zip", "") for f in os.listdir(LESSON_PATH) if f.endswith(".zip")]
    return {"lessons": lessons}
