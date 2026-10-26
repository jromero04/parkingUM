import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class SensorState:
    def __init__(self, path: str, sensor_id: str, spot_id: str) -> None:
        self.path, self.sensor_id, self.spot_id = path, sensor_id, spot_id
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS sensor_state (
                sensor_id TEXT PRIMARY KEY, spot_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                physical_occupied INTEGER NOT NULL, pending_event TEXT, updated_at TEXT NOT NULL,
                failed INTEGER NOT NULL DEFAULT 0
            )""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(sensor_state)")}
            if "failed" not in columns:
                db.execute("ALTER TABLE sensor_state ADD COLUMN failed INTEGER NOT NULL DEFAULT 0")
            db.execute("""INSERT OR IGNORE INTO sensor_state
                (sensor_id, spot_id, sequence, physical_occupied, pending_event, updated_at, failed)
                VALUES (?, ?, 0, 0, NULL, ?, 0)""", (sensor_id, spot_id, self.now()))

    def connect(self):
        return sqlite3.connect(self.path, timeout=10, isolation_level=None)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def prepare_event(self) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT sequence, physical_occupied, pending_event FROM sensor_state WHERE sensor_id=?",
                             (self.sensor_id,)).fetchone()
            if row[2]:
                db.commit()
                return json.loads(row[2])
            sequence = row[0] + 1
            observed_at = self.now()
            envelope = {
                "event_id": str(uuid.uuid4()), "event_type": "sensor.reported.v1", "schema_version": 1,
                "occurred_at": observed_at, "producer": "sensor-simulator", "correlation_id": str(uuid.uuid4()),
                "data": {"sensor_id": self.sensor_id, "spot_id": self.spot_id, "sequence": sequence,
                         "observed_at": observed_at, "physical_occupied": bool(row[1])},
            }
            encoded = json.dumps(envelope, separators=(",", ":"))
            db.execute("UPDATE sensor_state SET sequence=?, pending_event=?, updated_at=? WHERE sensor_id=?",
                       (sequence, encoded, observed_at, self.sensor_id))
            db.commit()
            return envelope

    def confirm(self, event_id: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT pending_event FROM sensor_state WHERE sensor_id=?", (self.sensor_id,)).fetchone()
            if not row or not row[0] or json.loads(row[0])["event_id"] != event_id:
                return False
            db.execute("UPDATE sensor_state SET pending_event=NULL, updated_at=? WHERE sensor_id=?",
                       (self.now(), self.sensor_id))
            return True

    def set_occupied(self, occupied: bool) -> None:
        with self.connect() as db:
            db.execute("UPDATE sensor_state SET physical_occupied=?, updated_at=? WHERE sensor_id=?",
                       (int(occupied), self.now(), self.sensor_id))

    def set_failed(self, failed: bool) -> None:
        with self.connect() as db:
            db.execute("UPDATE sensor_state SET failed=?, updated_at=? WHERE sensor_id=?",
                       (int(failed), self.now(), self.sensor_id))

    def is_failed(self) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT failed FROM sensor_state WHERE sensor_id=?", (self.sensor_id,)).fetchone()
        return bool(row[0])

    def inspect(self) -> dict:
        with self.connect() as db:
            row = db.execute("""SELECT sequence, physical_occupied, pending_event, failed, updated_at
                FROM sensor_state WHERE sensor_id=?""",
                             (self.sensor_id,)).fetchone()
        return {"sensor_id": self.sensor_id, "spot_id": self.spot_id, "sequence": row[0],
                "physical_occupied": bool(row[1]), "pending_event": json.loads(row[2]) if row[2] else None,
                "failed": bool(row[3]), "updated_at": row[4]}
