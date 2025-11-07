from sqlalchemy import Column, Integer, String, Boolean, Text, Float, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default="user")  # 'admin' or 'user'
    group_name = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=func.now())

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    data_file_path = Column(Text)  # optional dataset archive
    groundtruth_path = Column(Text)  # CSV id,label
    uploader_id = Column(Integer, ForeignKey("users.id"))
    is_official = Column(Boolean, default=False)
    stats_json = Column(JSON)  # EDA results
    created_at = Column(TIMESTAMP, server_default=func.now())

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    file_path = Column(Text)  # CSV id,label_pred
    evaluated = Column(Boolean, default=False)
    score_json = Column(JSON)  # {"AUC":..., "F1":...,"ROC":{...},"PR":{...}}
    created_at = Column(TIMESTAMP, server_default=func.now())

class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    metric_name = Column(String(20))
    metric_value = Column(Float)
    created_at = Column(TIMESTAMP, server_default=func.now())

class ApiLog(Base):
    __tablename__ = "api_logs"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    request_url = Column(Text)
    status_code = Column(Integer)
    response_time = Column(Float)  # ms
    result_preview = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
