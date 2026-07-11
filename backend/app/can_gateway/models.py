from __future__ import annotations
import time
from pydantic import BaseModel, Field
from app.core.time import now_ns

class CanFrame(BaseModel):
    timestamp_ns: int = Field(default_factory=now_ns)
    channel: str
    direction: str = "rx"
    can_id: int
    is_extended: bool = False
    is_remote: bool = False
    dlc: int = 8
    data: list[int] = Field(default_factory=list)
    raw_packet: bytes = b""
    message_name: str | None = None
    parse_status: str = "ok"
    source: str = "unknown"
    received_at_monotonic: float = Field(default_factory=time.monotonic, exclude=True)

    @property
    def can_id_hex(self) -> str:
        return f"0x{self.can_id:X}"

    @property
    def data_hex(self) -> str:
        return " ".join(f"{b & 0xFF:02X}" for b in self.data[: self.dlc])

    @property
    def raw_packet_hex(self) -> str:
        return self.raw_packet.hex(" ").upper()

    def ui_dict(self) -> dict:
        return {
            "timestamp_ns": self.timestamp_ns,
            "channel": self.channel,
            "direction": self.direction,
            "can_id": self.can_id,
            "can_id_hex": self.can_id_hex,
            "is_extended": self.is_extended,
            "is_remote": self.is_remote,
            "dlc": self.dlc,
            "data": self.data[: self.dlc],
            "data_hex": self.data_hex,
            "raw_packet_hex": self.raw_packet_hex,
            "message_name": self.message_name,
            "parse_status": self.parse_status,
            "source": self.source,
        }
