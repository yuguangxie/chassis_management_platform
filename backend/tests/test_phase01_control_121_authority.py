from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.control.control_121 import Control121Command, decode_control_121, encode_control_121, preview
from app.control.tx_scheduler import TxScheduler
from app.main import app
from simulator.can_frame_simulator import build_usr_can115_frame, parse_121


@pytest.mark.parametrize(
    ("angle", "encoded"),
    [(-120, 0x88), (-60, 0xC4), (0, 0x00), (60, 0x3C), (120, 0x78)],
)
def test_golden_steering_vectors(angle: int, encoded: int):
    command = Control121Command(front_steering_cmd=angle, rear_steering_cmd=angle)
    data = encode_control_121(command)
    assert data[1] == encoded
    assert data[2] == encoded
    assert decode_control_121(data)["front_steering_cmd"] == angle
    assert parse_121(build_usr_can115_frame(0x121, list(data)))["front"] == angle


def test_api_preview_uses_authoritative_encoder(auth_headers):
    payload = {
        "gear": "D",
        "drive_mode": "Remote",
        "target_speed": 2.0,
        "front_steer": -60,
        "rear_steer": 60,
        "brake_enable": True,
        "position_light": True,
        "low_beam": True,
        "control_mode": "speed",
    }
    command = Control121Command(
        shift="D",
        drive_mode="Remote",
        target_speed_kmh=2.0,
        front_steering_cmd=-60,
        rear_steering_cmd=60,
        brake_enable=True,
        position_light=True,
        low_beam=True,
        speed_mode=True,
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/control/121/preview", json=payload, headers=auth_headers("engineer"))
        assert response.status_code == 200
        body = response.json()
    assert body["bytes_dec"] == list(encode_control_121(command))
    assert body["data"] == body["bytes_dec"]
    assert body["bytes_hex"] == preview(command)["bytes_hex"]


@pytest.mark.asyncio
async def test_scheduler_transmits_exact_preview_bytes():
    captured = []

    class Can:
        async def send_frame(self, _channel, frame):
            captured.append(frame)

    safety = SimpleNamespace(require_allowed=lambda *args, **kwargs: {"allowed": True})
    state = SimpleNamespace(
        config=SimpleNamespace(control_channel="CAN2"),
        can=Can(),
        safety=safety,
    )
    command = Control121Command(
        shift="D", drive_mode="Remote", target_speed_kmh=2.0, front_steering_cmd=-60, rear_steering_cmd=60, brake_enable=True
    )
    scheduler = TxScheduler(state)
    await scheduler.send_once(command)
    assert captured[0].data == preview(command)["bytes_dec"]
    simulator_rx = parse_121(build_usr_can115_frame(0x121, captured[0].data))
    assert simulator_rx["front"] == -60
    assert simulator_rx["rear"] == 60
    assert simulator_rx["target_speed"] == 2.0
