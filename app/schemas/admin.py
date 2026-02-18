"""
通用 Admin 响应 Schema
"""

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    """通用成功响应"""
    success: bool = True
    message: str = Field(default="操作成功", description="操作结果描述")

    @classmethod
    def create(cls, message: str = "操作成功") -> "SuccessResponse":
        """快捷创建成功响应"""
        return cls(message=message)


class LoadBalancingModeResponse(BaseModel):
    """负载均衡模式响应"""
    mode: str = Field(description="当前负载均衡模式: priority / balanced")
