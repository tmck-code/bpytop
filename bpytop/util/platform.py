import sys
from functools import lru_cache

@lru_cache
def detect() -> str:
    if "linux" in sys.platform:
        return "Linux"
    elif "bsd" in sys.platform:
        return "BSD"
    elif "darwin" in sys.platform:
        return "MacOS"
    else:
        return "Other"
    