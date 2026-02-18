"""
错误响应 Schema

Anthropic 兼容的错误格式 + Admin API 错误格式
"""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """错误详情"""
    type: str
    message: str


class ErrorResponse(BaseModel):
    """Anthropic 兼容错误响应

    格式：{"type": "error", "error": {"type": "...", "message": "..."}}
    """
    type: str = "error"
    error: ErrorDetail

    @classmethod
    def create(cls, error_type: str, message: str) -> "ErrorResponse":
        """快捷创建错误响应"""
        return cls(error=ErrorDetail(type=error_type, message=message))

    @classmethod
    def authentication_error(cls, message: str = "Invalid API key") -> "ErrorResponse":
        """认证错误"""
        return cls.create("authentication_error", message)

    @classmethod
    def permission_error(cls, message: str = "Permission denied") -> "ErrorResponse":
        """权限错误"""
        return cls.create("permission_error", message)

    @classmethod
    def rate_limit_error(cls, message: str = "Token quota exceeded") -> "ErrorResponse":
        """额度超限错误"""
        return cls.create("rate_limit_error", message)

    @classmethod
    def invalid_request_error(cls, message: str) -> "ErrorResponse":
        """请求参数错误"""
        return cls.create("invalid_request_error", message)

    @classmethod
    def api_error(cls, message: str) -> "ErrorResponse":
        """API 内部错误"""
        return cls.create("api_error", message)

    @classmethod
    def overloaded_error(cls, message: str = "Service overloaded") -> "ErrorResponse":
        """服务过载错误"""
        return cls.create("overloaded_error", message)


class AdminErrorResponse(BaseModel):
    """Admin API 错误响应

    格式：{"error": "...", "detail": "..."}
    """
    error: str
    detail: str

    @classmethod
    def create(cls, error: str, detail: str) -> "AdminErrorResponse":
        """快捷创建 Admin 错误响应"""
        return cls(error=error, detail=detail)

    @classmethod
    def not_found(cls, detail: str = "Resource not found") -> "AdminErrorResponse":
        """资源未找到"""
        return cls.create("not_found", detail)

    @classmethod
    def conflict(cls, detail: str) -> "AdminErrorResponse":
        """资源冲突"""
        return cls.create("conflict", detail)

    @classmethod
    def bad_request(cls, detail: str) -> "AdminErrorResponse":
        """请求参数错误"""
        return cls.create("bad_request", detail)
