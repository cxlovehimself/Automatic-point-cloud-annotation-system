from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, DateTime, String, Numeric

# ==========================================
# 1. User (用户模块)
# ==========================================
class UserBase(SQLModel):
    """用户基础字段，供 DB 和 Schema 共享"""
    # 完美继承你原来 Schema 里的 EmailStr 校验，同时在数据库加索引和唯一约束
    email: EmailStr = Field(sa_column=Column(String(120), unique=True, index=True, nullable=False))
    
class User(SQLModel, table=True):
    """真实数据库表：users"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    # 💡 帮你把之前有的 email 补回来了，这个绝对不能丢！
    email: str = Field(sa_column=Column(String(255), nullable=False, unique=True, index=True))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    role: str = Field(default="normal", sa_column=Column(String(20), default="normal"))
    is_subscribed: bool = Field(default=False)
    
    # ==========================================
    # 💡 核心新增：VIP 到期时间 (允许为空)
    # ==========================================
    vip_expire_time: Optional[datetime] = Field(default=None)
    
    register_time: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(default=None)

    # 💡 魔法连表关系：自动反向关联历史记录和订单
    histories: List["ProcessingHistory"] = Relationship(back_populates="user")
    orders: List["Order"] = Relationship(back_populates="user")
# 前端传来的 Schema (注册)
class UserCreate(UserBase):
    password: str

# 前端传来的 Schema (登录)
class UserLogin(UserBase):
    password: str


# ==========================================
# 2. ProcessingHistory (历史记录模块)
# ==========================================
class ProcessingHistoryBase(SQLModel):
    """历史记录基础字段"""
    # sa_column_kwargs={"comment": "..."} 完美还原你原来的原生表注释
    original_filename: str = Field(sa_column=Column(String(255), nullable=False, comment="原始文件名"))
    scene_type: Optional[str] = Field(default=None, sa_column=Column(String(50), comment="识别出的场景类型"))
    result_url: str = Field(sa_column=Column(String(500), nullable=False, comment="模型下载/访问链接"))
    remark: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True, comment="用户自定义备注"))

class ProcessingHistory(ProcessingHistoryBase, table=True):
    """真实数据库表：processing_history"""
    __tablename__ = "processing_history"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True, description="记录唯一ID")
    # 外键：严格保留了你原来的 CASCADE 级联删除特性
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", description="关联的用户ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="任务完成时间")

    # 💡 连表关系：记录属于哪个用户
    user: Optional[User] = Relationship(back_populates="histories")

# 返回给前端的 Schema (历史记录列表)
class HistoryResponse(ProcessingHistoryBase):
    id: int
    created_at: datetime
    # 💡 注: SQLModel 默认自带 from_attributes=True (即以前的 orm_mode=True)
    # 所以你原来的 ConfigDict 在这里可以完全省掉，极其丝滑！


# ==========================================
# 3. Order (订单模块)
# ==========================================
class OrderBase(SQLModel):
    """订单基础字段"""
    out_trade_no: str = Field(sa_column=Column(String(100), unique=True, index=True, nullable=False, comment="系统生成的订单号"))
    alipay_trade_no: Optional[str] = Field(default=None, sa_column=Column(String(100), unique=True, index=True, nullable=True, comment="支付宝流水号"))
    # 严格保留你原来的 Numeric(10, 2) 小数精度设定
    total_amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False, comment="订单金额"))
    status: str = Field(default="pending", sa_column=Column(String(20), default="pending", comment="状态: pending/paid/failed"))

class Order(OrderBase, table=True):
    """真实数据库表：orders"""
    __tablename__ = "orders"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True, description="订单自增ID")
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", description="购买者ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 💡 这里的魔法：完美保留了你原来的 onupdate=datetime.utcnow 自动更新机制！
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, 
        sa_column=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    )

    # 💡 连表关系：订单属于哪个用户
    user: Optional[User] = Relationship(back_populates="orders")
class ChangePasswordRequest(SQLModel):
    old_password: str
    new_password: str
class ResetPasswordRequest(SQLModel):
    email: str
    code: str
    new_password: str
class SendCodeRequest(SQLModel):
    email: str