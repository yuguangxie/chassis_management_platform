from __future__ import annotations

import asyncio
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from app.can_gateway.manager import CanGatewayManager
from app.can_gateway.models import CanFrame
from app.can_gateway.tcp_gateway import TcpCanGateway
from app.control.control_121 import Control121Command, encode_control_121
from app.core.config import ChannelConfig, RuntimeConfig
from app.main import app
from app.services.app_state import state
from app.api.signals import live_dashboard_payload


DASHBOARDS = [
    ("/api/v1/overview/summary", "viewer"),
    ("/api/v1/can/frames/latest", "viewer"),
    ("/api/v1/can/statistics/monitor", "viewer"),
    ("/api/v1/signals/dashboard", "viewer"),
    ("/api/v1/signals/curve-config", "viewer"),
    ("/api/v1/signals/timeseries", "viewer"),
    ("/api/v1/alarms/dashboard", "viewer"),
    ("/api/v1/reports/dashboard", "viewer"),
    ("/api/v1/history/dashboard", "viewer"),
    ("/api/v1/eol/dashboard", "viewer"),
    ("/api/v1/config/system-dashboard", "viewer"),
]


def test_openapi_exposes_phase03_response_contracts():
    spec = app.openapi()
    required = {
        "/api/v1/overview/summary",
        "/api/v1/can/frames/latest",
        "/api/v1/can/frames/latest/{can_id}/decoded",
        "/api/v1/can/statistics/monitor",
        "/api/v1/signals/dashboard",
        "/api/v1/signals/timeseries",
        "/api/v1/alarms/dashboard",
        "/api/v1/reports/dashboard",
        "/api/v1/reports/{rid}/preview",
        "/api/v1/history/dashboard",
        "/api/v1/config/system-dashboard",
    }
    assert required <= set(spec["paths"])
    for path in required:
        operation = next(iter(spec["paths"][path].values()))
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema


def test_dashboard_provenance_is_never_silent(auth_headers):
    with TestClient(app) as client:
        for path, role in DASHBOARDS:
            response = client.get(path, headers=auth_headers(role) if role else None)
            assert response.status_code == 200, (path, response.text)
            payload = response.json()
            assert payload["data_source"]
            assert payload["mock"] is False
            assert payload["quality"] in {"good", "degraded", "unavailable"}
            assert payload["updated_at"]
            assert payload["trace_id"] == response.headers["X-Trace-Id"]


def test_signal_dashboard_rest_and_websocket_share_complete_envelope(auth_headers):
    """The publisher calls this same helper; no partial WS payload may erase quality."""
    with TestClient(app) as client:
        response = client.get("/api/v1/signals/dashboard", headers=auth_headers("viewer"))
        assert response.status_code == 200, response.text
        rest = response.json()
        published = live_dashboard_payload()

    required = {
        "data_source", "mock", "quality", "updated_at", "trace_id", "status",
        "bms", "vehicle", "wheel_speed", "steering", "motor", "lights_brake",
        "alarm", "watchlist",
    }
    assert required <= rest.keys()
    assert required <= published.keys()
    assert rest["quality"] == rest["status"]["quality"] or rest["quality"] == "mock"
    assert published["quality"] == published["status"]["quality"] or published["quality"] == "mock"
    comparable = required - {"trace_id", "updated_at", "status"}
    assert {key: rest[key] for key in comparable} == {key: published[key] for key in comparable}
    assert rest["status"] | {"updated_at": "normalized"} == published["status"] | {"updated_at": "normalized"}


def test_can_frames_list_matches_declared_response_contract(auth_headers):
    with TestClient(app) as client:
        response = client.get("/api/v1/can/frames", headers=auth_headers("viewer"))
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_unified_4xx_validation_and_5xx_errors_have_trace_id(auth_headers, monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        viewer = auth_headers("viewer")
        missing = client.get("/api/v1/reports/REPORT-NOT-FOUND/preview", headers=viewer)
        assert missing.status_code == 404
        assert set(missing.json()) == {"code", "message", "details", "trace_id"}
        assert missing.json()["code"] == "REPORT_NOT_FOUND"
        assert missing.json()["trace_id"] == missing.headers["X-Trace-Id"]

        invalid = client.post(
            "/api/v1/test-sessions/no-session/replay/seek",
            json={"progress_percent": 101}, headers=viewer,
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "VALIDATION_ERROR"
        assert invalid.json()["details"]["errors"]

        original = state.report_service.dashboard
        monkeypatch.setattr(state.report_service, "dashboard", lambda: (_ for _ in ()).throw(RuntimeError("secret")))
        failed = client.get("/api/v1/reports/dashboard", headers=viewer)
        monkeypatch.setattr(state.report_service, "dashboard", original)
        assert failed.status_code == 500
        assert failed.json()["code"] == "INTERNAL_ERROR"
        assert failed.json()["message"] != "secret"
        assert failed.json()["trace_id"] == failed.headers["X-Trace-Id"]


def test_production_rejects_unavailable_live_data_instead_of_using_fallback(auth_headers):
    saved_profile = state.config.profile
    saved_latest = deepcopy(state.can.latest_frames)
    saved_recent = list(state.can.recent_frames)
    try:
        state.config.profile = "production"
        state.can.latest_frames.clear()
        state.can.recent_frames.clear()
        with TestClient(app) as client:
            response = client.get("/api/v1/can/frames/latest", headers=auth_headers("viewer"))
        assert response.status_code == 503
        body = response.json()
        assert body["code"] == "PRODUCTION_DATA_UNAVAILABLE"
        assert body["trace_id"]
    finally:
        state.config.profile = saved_profile
        state.can.latest_frames.clear()
        state.can.latest_frames.update(saved_latest)
        state.can.recent_frames.clear()
        state.can.recent_frames.extend(saved_recent)


def test_latest_can_details_use_actual_frame_and_authoritative_decoders(auth_headers):
    with TestClient(app) as client:
        saved_latest = deepcopy(state.can.latest_frames)
        saved_recent = list(state.can.recent_frames)
        state.can.latest_frames.clear()
        state.can.recent_frames.clear()
        try:
            warning = CanFrame(
                channel="CAN1",
                direction="rx",
                can_id=0x77,
                dlc=8,
                data=[1, 0, 0, 0, 0, 0, 0, 0],
                source="phase03-test",
            )
            asyncio.run(state.dbc.decode(warning))
            state.can.record_recent(warning)
            viewer = auth_headers("viewer")
            overview = client.get("/api/v1/overview/summary", headers=viewer)
            assert overview.status_code == 200, overview.text
            assert overview.json()["signals"]["signals"]
            decoded = client.get("/api/v1/can/frames/latest/0x77/decoded", headers=viewer).json()
            assert decoded["frame"]["data_hex"] == "01 00 00 00 00 00 00 00"
            assert decoded["frame"]["can_id_hex"] == "0x77"
            assert decoded["dbc_status"] == "decoded"
            assert any(row["physical_value"] not in (0, "0", False) for row in decoded["signals"])

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
            data = encode_control_121(command)
            control = CanFrame(channel="CAN2", direction="tx", can_id=0x121, dlc=8, data=list(data), source="phase03-test")
            state.can.record_recent(control)
            decoded_121 = client.get("/api/v1/can/frames/latest/0x121/decoded", headers=viewer).json()
            rows = {row["name"]: row for row in decoded_121["signals"]}
            assert rows["SCU_Steering_Angle_Front"]["raw_value"] == 0xC4
            assert rows["SCU_Steering_Angle_Front"]["physical_value"] == -60
            assert rows["SCU_Steering_Angle_Rear"]["raw_value"] == 0x3C
            assert rows["SCU_Target_Speed"]["physical_value"] == 2.0

            protect = CanFrame(channel="CAN2", direction="rx", can_id=0x102, dlc=8, data=[1, 128, 52, 18, 120, 86, 0, 0], source="phase03-test")
            state.can.record_recent(protect)
            decoded_102 = client.get("/api/v1/can/frames/latest/0x102/decoded", headers=viewer).json()
            rows_102 = {row["name"]: row for row in decoded_102["signals"]}
            assert rows_102["BMS_Protect_Bitmap"]["raw_value"] == 0x8001
            assert rows_102["BMS_Protect_Bit_15"]["raw_value"] == 1
            assert rows_102["Balance_symbol_cell16"]["raw_value"] == 0x1234
            assert rows_102["Balance_symbol_cell33"]["raw_value"] == 0x5678
        finally:
            state.can.latest_frames.clear()
            state.can.latest_frames.update(saved_latest)
            state.can.recent_frames.clear()
            state.can.recent_frames.extend(saved_recent)


@pytest.mark.asyncio
async def test_tcp_channel_uses_real_stream_gateway_and_loopback_frame():
    received_packets: list[bytes] = []
    callback_frames: list[CanFrame] = []

    async def device(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        packet = await reader.readexactly(13)
        received_packets.append(packet)
        writer.write(packet)
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(device, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])

    async def on_frame(frame: CanFrame):
        callback_frames.append(frame.model_copy(deep=True))

    config = RuntimeConfig(
        profile="test",
        control_channel="CAN1",
        channels=[
            ChannelConfig(
                channel="CAN1",
                protocol="tcp",
                local_ip="127.0.0.1",
                local_receive_port=0,
                device_ip="127.0.0.1",
                device_port=port,
                control_enabled=True,
            )
        ],
    )
    manager = CanGatewayManager(config, on_frame)
    assert isinstance(manager.gateways["CAN1"], TcpCanGateway)
    try:
        await manager.start_channel("CAN1")
        await manager.send_frame(
            "CAN1",
            CanFrame(channel="CAN1", direction="tx", can_id=0x121, dlc=8, data=[0] * 8),
        )
        await asyncio.sleep(0.1)
        assert len(received_packets) == 1 and len(received_packets[0]) == 13
        assert any(frame.direction == "rx" and frame.can_id == 0x121 for frame in callback_frames)
    finally:
        await manager.stop_all()
        server.close()
        await server.wait_closed()
