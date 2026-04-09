from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session  # 💡 修改 1：把 sqlalchemy.orm 换成 sqlmodel
from jose import jwt, JWTError

# 💡 修改 2：直接引入 database.py 里写好的 get_db，彻底告别 SessionLocal！
from database import get_db 
from services import crud_user

# 你的密钥配置
from security import SECRET_KEY, ALGORITHM 

# 告诉 FastAPI，我们的 Token 是通过 Bearer 方式传递的
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 🚨 注意：我把你原本写在这里的 def get_db() 删掉了！
# 因为我们在前面的重构中，已经把 get_db() 函数写进 database.py 里了。
# 这里直接 import 过来用，代码更少，不打架！

# ==========================================
# 2. 当前登录用户鉴权依赖
# ==========================================
def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """
    解析前端传来的 JWT Token，并返回当前操作的 User 对象
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，Token 无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码 JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 💡 完美复用 Service 层逻辑！
    user = crud_user.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
        
    return user