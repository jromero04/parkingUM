import os
import sys


def main() -> None:
    target = os.getenv("WORKER_MODULE", "")
    if not target:
        raise SystemExit(1)
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or entry == str(os.getpid()):
            continue
        try:
            command = open(f"/proc/{entry}/cmdline", "rb").read().replace(b"\x00", b" ").decode()
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            continue
        if target in command:
            return
    raise SystemExit(1)


if __name__ == "__main__":
    sys.exit(main())
