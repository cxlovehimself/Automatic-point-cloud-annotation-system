import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

# 你的 MySQL 连接 URL
load_dotenv()

# 从环境变量中读取，如果没有则报错提醒
SQLALCHEMY_DATABASE_URL = os.getenv("DB_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DB_URL 未在 .env 文件中配置！")

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
# 初始化数据库建表函数 (需要在 main.py 启动时调一下)
def init_db():
    SQLModel.metadata.create_all(engine)

# 依赖注入：获取数据库 Session
def get_db():
    with Session(engine) as session:
        yield session