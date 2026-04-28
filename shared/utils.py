import json
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Any

def generate_referral_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def json_serialize(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)

def json_deserialize(s: str) -> Any:
    return json.loads(s) if s else None

def parse_list_field(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        return json.loads(value)
    except:
        return []

def format_list_field(items: List[str]) -> str:
    return json.dumps(items, ensure_ascii=False)

def calculate_days_left(expires_at: Optional[datetime]) -> int:
    if not expires_at:
        return 0
    delta = expires_at - datetime.utcnow()
    return max(0, delta.days)

def reset_daily_if_needed(last_reset: datetime) -> bool:
    now = datetime.utcnow()
    return (now - last_reset) >= timedelta(days=1)
