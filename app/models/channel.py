from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class Channel(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    mode: Literal["proxy", "direct"] = Field(default="proxy")
    group: str = Field(default="Default")
    logo: str = Field(default="")
    enabled: int = Field(default=1)
    sort_order: int = Field(default=0)