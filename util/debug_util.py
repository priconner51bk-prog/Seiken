from datetime import datetime
from pathlib import Path

can_debug = False
LOG_FILE = Path(__file__).with_name("debug.log")


def debug_write(msg: str):
    print(msg)
    if can_debug:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
