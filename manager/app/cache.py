# This file basically handles writing rollout percentages to redis.
# Uses the exact same format as the one give to go-relay for processing. 

import os
import redis

REDIS_ADDR = os.getenv("REDIS_ADDR", "localhost:6379")

# grab the host and port since the redis lib processes host and port separately
_host, _port = REDIS_ADDR.split(":")

# Creating a connection to Redis, This line creates the actual connection. 
# decode_responses = True, basically says that output would be returned in a python string
redis_client = redis.Redis(host=_host, port=int(_port), decode_responses=True)

def set_rollout(flag_name: str, rollout_percentage: int):
    key = f"flag:{flag_name}"
    redis_client.set(key, rollout_percentage)