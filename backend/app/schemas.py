from pydantic import BaseModel
from typing import Optional, Dict, List

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    group_name: Optional[str] = None
    role: str = "user"

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    group_name: Optional[str] = None
    role: str = "user"

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True

class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DatasetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_official: bool
    class Config:
        orm_mode = True

class SubmissionOut(BaseModel):
    id: int
    dataset_id: int
    user_id: int
    evaluated: bool
    score_json: Optional[Dict]
    class Config:
        orm_mode = True

class LeaderboardItem(BaseModel):
    group_name: str
    dataset_id: int
    auc: float
    f1: float
    submission_id: int

class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
