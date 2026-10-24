import os


target = "app.worker"
for entry in os.listdir("/proc"):
    if not entry.isdigit() or entry == str(os.getpid()):
        continue
    try:
        with open(f"/proc/{entry}/cmdline", "rb") as source:
            command = source.read().replace(b"\x00", b" ").decode()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        continue
    if target in command:
        raise SystemExit(0)
raise SystemExit(1)
