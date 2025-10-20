import uuid
import time


def generate_message_id() -> str:
    """Generate a unique message identifier (UUID4 as string)."""
    return str(uuid.uuid4())


def current_timestamp() -> float:
    """Return current timestamp as float seconds since epoch, for consistency."""
    return time.time()
