from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from statistics import stdev
from typing import Protocol

HostId = str
MAX_HISTORY = 64
TREND_BLOCKS = "▁▂▃▄▅▆▇█"
TIMEOUT_MARKER = "╳"


class HostState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DELETED = "deleted"


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


class SortKey(str, Enum):
    HOST = "target"
    IP = "resolved_ip"
    SEQ = "seq"
    RTT = "last_rtt_ms"
    MIN = "min_rtt_ms"
    AVG = "avg_rtt_ms"
    MAX = "max_rtt_ms"
    STDDEV = "stddev_ms"
    LOSS = "lost"
    LOSS_PERCENT = "loss_percent"
    STATE = "state"
    TREND = "trend"


@dataclass(slots=True)
class SessionConfig:
    interval: float = 1.0
    timeout: float = 1.0
    packet_size: int = 56
    summary: bool = True
    export_path: str | None = None
    export_format: ExportFormat | None = None
    log_file: str | None = None
    log_level: str = "info"


@dataclass(slots=True)
class HostConfig:
    id: HostId
    target: str
    enabled: bool = True


@dataclass(slots=True)
class PingResult:
    success: bool
    rtt_ms: float | None = None
    resolved_ip: str | None = None
    error_message: str | None = None


class PingEngine(Protocol):
    async def ping_once(
        self, target: str, timeout: float, packet_size: int, flag: int
    ) -> PingResult:
        ...


@dataclass(slots=True)
class HostStats:
    resolved_ip: str | None = None
    seq: int = 0
    last_rtt_ms: float | None = None
    min_rtt_ms: float | None = None
    avg_rtt_ms: float | None = None
    max_rtt_ms: float | None = None
    stddev_ms: float | None = None
    lost: int = 0
    loss_percent: float = 0.0
    history_ms: list[float | None] = field(default_factory=list)
    trend: str = ""
    last_error: str | None = None
    state: HostState = HostState.PENDING
    last_updated_at: datetime | None = None

    def register_timeout(self, when: datetime) -> None:
        self.seq += 1
        self.lost += 1
        self.loss_percent = (self.lost / self.seq) * 100 if self.seq else 0.0
        self.last_error = "timeout"
        self.state = HostState.RUNNING
        self.last_updated_at = when
        self._append_history(None)

    def register_error(self, message: str, when: datetime) -> None:
        self.last_error = message
        self.state = HostState.ERROR
        self.last_updated_at = when

    def register_success(self, rtt_ms: float, resolved_ip: str | None, when: datetime) -> None:
        self.seq += 1
        if resolved_ip:
            self.resolved_ip = resolved_ip
        self.last_rtt_ms = rtt_ms
        self.last_error = None
        self.state = HostState.RUNNING
        self.last_updated_at = when
        self._append_history(rtt_ms)
        samples = [sample for sample in self.history_ms if sample is not None]
        if not samples:
            return
        self.min_rtt_ms = min(samples)
        self.max_rtt_ms = max(samples)
        self.avg_rtt_ms = sum(samples) / len(samples)
        self.stddev_ms = stdev(samples) if len(samples) > 1 else 0.0
        self.loss_percent = (self.lost / self.seq) * 100 if self.seq else 0.0

    def mark_paused(self) -> None:
        self.state = HostState.PAUSED

    def mark_pending(self) -> None:
        self.state = HostState.PENDING

    def mark_deleted(self) -> None:
        self.state = HostState.DELETED

    def reset(self) -> None:
        current_ip = self.resolved_ip
        self.resolved_ip = current_ip
        self.seq = 0
        self.last_rtt_ms = None
        self.min_rtt_ms = None
        self.avg_rtt_ms = None
        self.max_rtt_ms = None
        self.stddev_ms = None
        self.lost = 0
        self.loss_percent = 0.0
        self.history_ms = []
        self.trend = ""
        self.last_error = None
        self.last_updated_at = None
        self.state = HostState.PENDING

    def snapshot(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["last_updated_at"] = (
            self.last_updated_at.astimezone(timezone.utc).isoformat()
            if self.last_updated_at
            else None
        )
        return payload

    def _append_history(self, value: float | None) -> None:
        self.history_ms.append(value)
        self.history_ms = self.history_ms[-MAX_HISTORY:]
        self.trend = build_trend(self.history_ms)


@dataclass(slots=True)
class HostRecord:
    config: HostConfig
    stats: HostStats = field(default_factory=HostStats)
    paused: bool = False

    def snapshot(self) -> dict[str, object]:
        return {
            "id": self.config.id,
            "target": self.config.target,
            "enabled": self.config.enabled,
            **self.stats.snapshot(),
        }


@dataclass(slots=True)
class SessionSnapshot:
    generated_at: datetime
    config: SessionConfig
    hosts: list[dict[str, object]]
    aggregates: dict[str, object]


def normalize_target(target: str) -> str:
    return target.strip().lower()


def trend_cells(history: list[float | None]) -> list[tuple[str, int | None]]:
    if not history:
        return []
    visible_history = history[-MAX_HISTORY:]
    samples = [sample for sample in visible_history if sample is not None]
    if not samples:
        return [(TIMEOUT_MARKER, None)] * len(visible_history)
    low = min(samples)
    high = max(samples)
    span = max(high - low, 1.0)
    cells: list[tuple[str, int | None]] = []
    for sample in visible_history:
        if sample is None:
            cells.append((TIMEOUT_MARKER, None))
            continue
        bucket = int(((sample - low) / span) * (len(TREND_BLOCKS) - 1))
        cells.append((TREND_BLOCKS[bucket], bucket))
    return cells


def build_trend(history: list[float | None]) -> str:
    return "".join(cell for cell, _ in trend_cells(history))
