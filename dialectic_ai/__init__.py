__version__ = "0.1.0"

import sys

# Ensure UTF-8 output encoding across Windows consoles and environments
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
