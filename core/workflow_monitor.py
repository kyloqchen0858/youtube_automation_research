from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def _format_ts(value: float) -> str:
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


class WorkflowMonitor:
    def __init__(self, phase: str, keyword: str = "", metadata: dict | None = None):
        self.phase = phase
        self.keyword = keyword
        self.metadata = metadata or {}
        self.summary = {}
        self.started_at = time.time()
        self.stages: list[dict] = []

    @contextmanager
    def stage(self, name: str, details: dict | None = None):
        started_at = time.time()
        record = {
            "name": name,
            "status": "running",
            "started_at": _format_ts(started_at),
            "duration_sec": 0.0,
            "details": details or {},
            "error": None,
        }
        self.stages.append(record)
        try:
            yield record["details"]
            record["status"] = "ok"
        except BaseException as exc:  # noqa: BLE001
            record["status"] = "failed"
            record["error"] = str(exc)
            raise
        finally:
            record["duration_sec"] = round(time.time() - started_at, 2)

    def add_metadata(self, **kwargs) -> None:
        self.metadata.update(kwargs)

    def set_summary(self, **kwargs) -> None:
        self.summary.update(kwargs)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "keyword": self.keyword,
            "started_at": _format_ts(self.started_at),
            "duration_sec": round(time.time() - self.started_at, 2),
            "metadata": self.metadata,
            "summary": self.summary,
            "stages": self.stages,
        }

    def write_json(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path