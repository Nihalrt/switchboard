# This is the main entry point of the file
# uvicorn, starts the actual web server and makes every endpoint defined in the 
# routers/flags.py reachable over the network. 

from fastapi import FastAPI
from .routers import flags

app = FastAPI(title="Switchboard Manager")
app.include_router(flags.router)