from pydantic import BaseModel, Field


class DeployRequest(BaseModel):
    entry: str = Field(min_length=1, max_length=120)
    files: dict[str, str] = Field(default_factory=dict)
    requirements: str = Field(default="", max_length=4000)
    env: dict[str, str] = Field(default_factory=dict)
    owner: str = Field(default="", max_length=120)
