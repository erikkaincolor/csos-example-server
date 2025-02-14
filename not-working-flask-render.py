from fastapi import FastAPI
from auth import auth_router
from lesson_serve import lesson_router

app = FastAPI()

# Include authentication and lesson-serving routes
app.include_router(auth_router, prefix="/auth")
app.include_router(lesson_router, prefix="/lessons")

@app.get("/")
def root():
    return {"message": "Welcome to the CSOS Lesson Server"}
