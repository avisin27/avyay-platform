import os
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Redis Connection ---
try:
    r = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.getenv("REDIS_PORT", 6380)),  # Default to 6380 for Azure Redis SSL
        password=os.environ["REDIS_PASS"],
        decode_responses=True,
        ssl=True
    )
except KeyError as e:
    raise RuntimeError(f"Missing required Redis env variable: {e}")
except Exception as e:
    raise RuntimeError(f"Failed to connect to Redis: {e}")

# --- Rate Limiting ---
RATE_LIMIT_MODE = os.environ.get("RATE_LIMIT_MODE", "fixed")  # "fixed" or "sliding"

def hybrid_rate_limiter(user_id: int, feature: str, limit: int) -> bool:
    """
    Hybrid rate limiter supporting both fixed and sliding windows.

    Args:
        user_id: Unique user ID
        feature: Action being rate-limited ("reflection", "feedback", etc.)
        limit: Allowed actions per window

    Returns:
        True if action is allowed, False if rate-limited.
    """
    now = datetime.utcnow()
    date_key = now.date().isoformat()
    redis_key_fixed = f"rate:{feature}:user:{user_id}:{date_key}"
    redis_key_sliding = f"rate:{feature}:user:{user_id}:sliding"

    if RATE_LIMIT_MODE == "fixed":
        count = r.get(redis_key_fixed)
        if count and int(count) >= limit:
            return False
        pipeline = r.pipeline()
        pipeline.incr(redis_key_fixed, 1)
        pipeline.expire(redis_key_fixed, 86400)  # TTL: 1 day
        pipeline.execute()
        return True

    elif RATE_LIMIT_MODE == "sliding":
        window = 86400  # 24-hour window
        now_ts = int(now.timestamp())
        cutoff_ts = now_ts - window

        pipeline = r.pipeline()
        pipeline.zremrangebyscore(redis_key_sliding, 0, cutoff_ts)
        pipeline.zcard(redis_key_sliding)
        results = pipeline.execute()
        current_count = results[-1]

        if current_count >= limit:
            return False

        r.zadd(redis_key_sliding, {str(now_ts): now_ts})
        return True

    else:
        raise ValueError(f"Invalid RATE_LIMIT_MODE: {RATE_LIMIT_MODE}")
