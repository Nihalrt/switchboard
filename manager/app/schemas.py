# This file basically defines the shape of the data during a req and res.
# Previously, we worked on what the request type should be and what it should contain and what should the response contain
# This file is quite different from models.py, which contains the definition for the tables, inheriting the base class.abs

from pydantic import BaseModel, Field

class FlagCreate(BaseModel):
    """
     Desc: This class describes what the request should look like when a flag is created.
    """
    # The req should contain the name
    name: str
    # Should contain a rollout percentage b/w 0-100
    rollout_percentage:int=Field(default=0, ge=0, le=100)

class FlagUpdate(BaseModel):
    """
     Desc: This class describes the req body for updating a flag's rollout percentage
    """
    rollout_percentage:int=Field(ge=0, le=100)

class FlagResponse(BaseModel):
    """
    Desc: This class describes the response body.
    """
    id: int
    name: str
    rollout_percentage: int
    
    class Config:
        from_attributes=True