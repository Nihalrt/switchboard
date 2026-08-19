# This file defines the endpoints required for the user to retrieve the necessary data about the flags
# Creating a flag, updating a flag, and reading a flag's current state.abs

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Flag
from ..schemas import FlagCreate, FlagUpdate, FlagResponse
from .. import cache

"""
An APIRouter sets the prefix=/flags for any resp/req made from the engineers. For example
a path return /{name} would become /flags/{name} once connected to the app from the router.

"""

router = APIRouter(prefix="/flags", tags=["flags"])

@router.post("/", response_model=FlagReponse, status_code=201)
def create_flag(flag: FlagCreate, db: Session = Depends(get_db)):
    """
    Insert a flag into the db after a check
    """
    existing_flag = db.query(Flag).filter(Flag.name==flag.name).first()
    if existing_flag:
        raise HTTPException(
            status_code=409, detail=f"flag '{flag.name}' already exists"
        )
    
    new_flag = Flag(name=flag.name, rollout_percentage=flag.rollout_percentage)
    db.add(new_flag)
    db.commit()
    df.refresh(new_flag)

    # Add the new flag to Redis for go relay process
    cache.set_rollout(new_flag.name, new_flag.rollout_percentage)
    return new_flag

@router.put("/{name}", response_model=FlagResponse)
def update_flag(new_name: str, update: FlagUpdate, db: Session = Depends(get_db()):
    """
    Update the flag 

    """