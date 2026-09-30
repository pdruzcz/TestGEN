from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details response."""

    type: str = Field(description="URI identifying the problem type")
    title: str = Field(description="Short human-readable summary")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation")
    instance: str = Field(default="", description="URI of the specific occurrence")
