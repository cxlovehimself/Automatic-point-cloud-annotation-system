from typing import Any

def success_response(data: Any = None, message: str = "操作成功", code: int = 200):
    """
    统一的成功返回体
    """
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {}
    }

def error_response(message: str = "操作失败", code: int = 400):
    """
    统一的错误/失败返回体 (注意：这里返回的 HTTP 状态码依然是 200，但是业务 code 是 400)
    如果你希望抛出真实的 HTTP 异常，可以配合 FastAPI 的 HTTPException 使用。
    """
    return {
        "code": code,
        "message": message,
        "data": {}
    }