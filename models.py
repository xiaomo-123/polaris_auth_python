from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import uuid

Base = declarative_base()

# 数据库连接配置
DATABASE_URL = "sqlite:///./polaris_auth.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建所有表
Base.metadata.create_all(bind=engine)

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class StateMapping(Base):
    """存储 state -> code_verifier 映射"""
    __tablename__ = "state_mappings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String, unique=True, index=True, nullable=False)
    code_verifier = Column(String, nullable=False)
    idp = Column(String, nullable=False)  # 身份提供商
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=10))

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

class OAuthCredential(Base):
    """存储已交换的 OAuth 凭证"""
    __tablename__ = "oauth_credentials"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String, index=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    id_token = Column(Text)
    token_type = Column(String, default="Bearer")
    expires_in = Column(Integer)
    profile_arn = Column(String)
    received_at = Column(DateTime, default=datetime.utcnow)
    idp = Column(String, nullable=False)  # 身份提供商
