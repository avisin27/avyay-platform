import redis
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Get Redis connection parameters from environment variables
r = redis.Redis(
    host=os.getenv("REDIS_HOST"),  # No default, must be set in Docker Compose or the environment
    port=int(os.getenv("REDIS_PORT", 6380)),  # Default to 6380 for Azure Redis SSL
    password=os.getenv("REDIS_PASS"),  # Redis password from environment (must be set)
    decode_responses=True,
    ssl=True  # Enable SSL for secure connection to Azure Redis Cache
)

RATE_LIMIT_MODE = os.getenv("RATE_LIMIT_MODE", "fixed")

def hybrid_rate_limiter(user_id: int, feature: str, limit: int):
    """
    General-purpose rate limiter for hybrid (fixed/sliding) modes.
    - feature: "reflection" or "feedback"
    - limit: number of allowed actions (e.g. 3 reflections, 20 feedback)
    """
    now = datetime.utcnow()
    date_key = now.date().isoformat()
    redis_key_fixed = f"rate:{feature}:user:{user_id}:{date_key}"
    redis_key_sliding = f"rate:{feature}:user:{user_id}:sliding"

    if RATE_LIMIT_MODE == "fixed":
        count = r.get(redis_key_fixed)
        if count and int(count) >= limit:
            return False
        r.incr(redis_key_fixed, 1)
        r.expire(redis_key_fixed, 86400)
        return True

    elif RATE_LIMIT_MODE == "sliding":
        window = 86400  # 24h window
        cutoff = int((now - timedelta(seconds=window)).timestamp())
        current_ts = int(now.timestamp())

        # Clean up old timestamps
        r.zremrangebyscore(redis_key_sliding, 0, cutoff)
        count = r.zcard(redis_key_sliding)
        if count >= limit:
            return False

        # Add current timestamp
        r.zadd(redis_key_sliding, {str(current_ts): current_ts})
        return True

    else:
        raise ValueError("Invalid RATE_LIMIT_MODE")
