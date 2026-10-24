import os
for entry in os.listdir("/proc"):
    if entry.isdigit() and entry != str(os.getpid()):
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as source: command=source.read().replace(b"\0", b" ").decode()
        except (OSError, UnicodeError): continue
        if "app.worker" in command: raise SystemExit(0)
raise SystemExit(1)
