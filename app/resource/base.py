from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseResource(ABC, BaseModel):
    """Base class for all read-only resources in OpenManus."""
    
    name: str
    description: str
    parameters: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        """Access the resource with given parameters."""
        return await self.access(**kwargs)

    @abstractmethod
    async def access(self, **kwargs) -> Any:
        """Access the resource with given parameters."""

    def to_param(self) -> Dict:
        """Convert resource to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ResourceResult(BaseModel):
    """Represents the result of a resource access."""

    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    
    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)
