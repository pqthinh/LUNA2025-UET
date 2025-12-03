from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Generic, TypeVar

T = TypeVar('T')

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
    created_at: datetime
    class Config:
        from_attributes = True

class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DatasetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    uploader_id: Optional[int]
    is_official: bool
    data_file_path: Optional[str] = None
    groundtruth_path: Optional[str] = None
    uploader_username: Optional[str] = None
    uploader_full_name: Optional[str] = None
    stats_json: Optional[Dict[str, Any]]
    created_at: datetime
    class Config:
        from_attributes = True

class SubmissionOut(BaseModel):
    id: int
    dataset_id: int
    user_id: int
    evaluated: bool
    score_json: Optional[Dict[str, Any]]
    created_at: datetime
    class Config:
        from_attributes = True

class MetricOut(BaseModel):
    id: int
    submission_id: int
    metric_name: str
    metric_value: float
    created_at: datetime
    class Config:
        from_attributes = True

class ApiLogOut(BaseModel):
    id: int
    submission_id: Optional[int]
    request_url: str
    status_code: int
    response_time: float
    result_preview: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class LeaderboardItem(BaseModel):
    group_name: str
    dataset_id: int
    submission_id: int
    auc: float
    f1: float
    created_at: datetime

# Generic paginated response
class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")
    
    class Config:
        from_attributes = True

    @property
    def pages(self) -> int:
        """Calculate total number of pages"""
        return -(-self.total // self.page_size)  # ceiling division

# Common query parameters
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number, 1-based")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")

class DatasetFilterParams(PaginationParams):
    is_official: Optional[bool] = None
    uploader_id: Optional[int] = None

class SubmissionFilterParams(PaginationParams):
    dataset_id: Optional[int] = None
    user_id: Optional[int] = None
    evaluated: Optional[bool] = None
