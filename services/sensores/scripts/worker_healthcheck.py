import os, sqlite3
target="app.publisher"; found=False
for entry in os.listdir("/proc"):
    if entry.isdigit() and entry!=str(os.getpid()):
        try:
            with open(f"/proc/{entry}/cmdline","rb") as source: command=source.read().replace(b"\0",b" ").decode()
        except (OSError,UnicodeError): continue
        if target in command: found=True; break
if not found: raise SystemExit(1)
path=os.getenv("STATE_DB_PATH","/data/sensors.db")
if os.path.exists(path):
    with sqlite3.connect(path) as db: db.execute("PRAGMA quick_check").fetchone()
