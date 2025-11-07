from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine, SessionLocal
from .models import User
from .utils import hash_password
from .routers import auth, users, datasets, submissions, leaderboard, apitest
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LUNA25 Evaluation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def seed_admin():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    group = os.getenv("ADMIN_GROUP", "group1")
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == username).first():
            user = User(username=username, password_hash=hash_password(password), role="admin", group_name=group)
            db.add(user); db.commit()
    finally:
        db.close()

seed_admin()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(datasets.router)
app.include_router(submissions.router)
app.include_router(leaderboard.router)
app.include_router(apitest.router)

@app.get("/")
def root():
    return {"message": "LUNA25 Evaluation API is running"}
