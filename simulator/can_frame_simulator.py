from __future__ import annotations
import argparse
import asyncio
import logging
import socket
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("simulator")

PROFILES = {
    "normal_pass": {"warning_level": 0, "soc": 86, "steering_response": True, "brake_response": True},
    "bms_low_soc": {"warning_level": 0, "soc": 18, "steering_response": True, "brake_response": True},
    "warning_fault": {"warning_level": 3, "soc": 86, "steering_response": True, "brake_response": True},
    "steering_no_response": {"warning_level": 0, "soc": 86, "steering_response": False, "brake_response": True},
    "brake_fail": {"warning_level": 0, "soc": 86, "steering_response": True, "brake_response": False},
}

def build_usr_can115_frame(can_id: int, data: list[int], is_extended: bool = False, is_remote: bool = False, dlc: int = 8) -> bytes:
    frame_info = (0x80 if is_extended else 0) | (0x40 if is_remote else 0) | (dlc & 0x0F)
    return bytes([frame_info]) + int(can_id).to_bytes(4, "big") + bytes((data + [0] * 8)[:8])

def parse_121(packet: bytes) -> dict | None:
    if len(packet) < 13 or int.from_bytes(packet[1:5], "big") != 0x121:
        return None
    d = packet[5:13]
    front = int.from_bytes(bytes([d[1]]), "big", signed=True)
    rear = int.from_bytes(bytes([d[2]]), "big", signed=True)
    speed_raw = d[3] | ((d[4] & 0x01) << 8)
    return {
        "gear": d[0] & 3,
        "drive_mode": (d[0] >> 6) & 3,
        "front": front,
        "rear": rear,
        "target_speed": speed_raw / 10,
        "brake": bool(d[4] & 0x02),
        "left_light": bool(d[5] & 0x03),
        "right_light": bool((d[5] >> 2) & 0x03),
        "position_light": bool((d[5] >> 6) & 0x03),
        "low_beam": bool(d[6] & 0x03),
    }

@dataclass
class VehicleState:
    target_speed: float = 0.0
    actual_speed: float = 0.0
    gear: int = 0
    drive_mode: int = 2
    front_cmd: int = 0
    rear_cmd: int = 0
    front_fb: float = 0.0
    rear_fb: float = 0.0
    brake_enabled: bool = False
    left_light: bool = False
    right_light: bool = False
    position_light: bool = False
    low_beam: bool = False

class Simulator:
    def __init__(self, profile: str, can1_target: tuple[str, int], can2_target: tuple[str, int], can1_listen: tuple[str, int], can2_listen: tuple[str, int], rate_hz: float = 20) -> None:
        self.profile = PROFILES[profile]
        self.state = VehicleState()
        self.targets = {"CAN1": can1_target, "CAN2": can2_target}
        self.listens = {"CAN1": can1_listen, "CAN2": can2_listen}
        self.rate_hz = rate_hz
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_socks: list[socket.socket] = []
        self.running = True

    async def start(self) -> None:
        for channel, addr in self.listens.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.bind(addr)
            self.rx_socks.append(sock)
            asyncio.create_task(self.listen(sock, channel))
        LOGGER.info("simulator profile=%s targets=%s listens=%s", self.profile, self.targets, self.listens)
        while self.running:
            self.update_vehicle()
            self.send_cycle("CAN2")
            self.send_cycle("CAN1")
            await asyncio.sleep(1 / self.rate_hz)

    async def listen(self, sock: socket.socket, channel: str) -> None:
        loop = asyncio.get_running_loop()
        while self.running:
            data, _ = await loop.sock_recvfrom(sock, 4096)
            for i in range(0, len(data) - len(data) % 13, 13):
                cmd = parse_121(data[i:i+13])
                if cmd:
                    self.state.target_speed = cmd["target_speed"]
                    self.state.gear = cmd["gear"]
                    self.state.drive_mode = cmd["drive_mode"]
                    self.state.front_cmd = cmd["front"]
                    self.state.rear_cmd = cmd["rear"]
                    self.state.brake_enabled = cmd["brake"]
                    self.state.left_light = cmd["left_light"]
                    self.state.right_light = cmd["right_light"]
                    self.state.position_light = cmd["position_light"]
                    self.state.low_beam = cmd["low_beam"]
                    LOGGER.info("rx 0x121 %s", cmd)

    def update_vehicle(self) -> None:
        if self.state.brake_enabled and self.profile["brake_response"]:
            self.state.actual_speed *= 0.45
            if self.state.actual_speed < 0.1:
                self.state.actual_speed = 0.0
        else:
            delta = self.state.target_speed - self.state.actual_speed
            self.state.actual_speed += max(-0.15, min(0.15, delta))
        if self.profile["steering_response"]:
            self.state.front_fb += (self.state.front_cmd - self.state.front_fb) * 0.3
            self.state.rear_fb += (self.state.rear_cmd - self.state.rear_fb) * 0.3

    def send(self, channel: str, can_id: int, data: list[int]) -> None:
        self.tx_sock.sendto(build_usr_can115_frame(can_id, data), self.targets[channel])

    def send_cycle(self, channel: str) -> None:
        soc = self.profile["soc"]
        voltage = int(520)
        current = int(12)
        warning = self.profile["warning_level"]
        speed_raw = int(self.state.actual_speed * 10)
        front = int(self.state.front_fb * 10)
        rear = int(self.state.rear_fb * 10)
        frames = [
            (
                0x51,
                [
                    self.state.gear | (self.state.drive_mode << 6),
                    speed_raw & 0xFF,
                    int(self.state.brake_enabled and self.profile["brake_response"]),
                    1,
                    int(self.state.left_light)
                    | (int(self.state.right_light) << 1)
                    | (int(self.state.position_light) << 2)
                    | (int(self.state.low_beam) << 3),
                    0,
                    0,
                    0,
                ],
            ),
            (0x77, [warning, 0, 0, 0, 0, 0, 0, 0]),
            (0x168, [(speed_raw >> 8) & 0xFF, speed_raw & 0xFF, 20, 20, 20, 20, 0, 0]),
            (0xE1, list(front.to_bytes(2, "big", signed=True) + rear.to_bytes(2, "big", signed=True)) + [0,0,0,0]),
            (0x703, [1,0,0,0,0,0,0,0]),
            (0x704, [1,0,0,0,0,0,0,0]),
        ]
        if channel == "CAN2":
            frames += [
                (0x100, [(voltage >> 8) & 0xFF, voltage & 0xFF, (current >> 8) & 0xFF, current & 0xFF, soc, 0, 0, 0]),
                (0x101, [2, soc, 0, 0, 0, 0, 0, 0]),
                (0x102, [0, 0, 0, 0, 0, 0, 0, 0]),
                (0x103, [65, 66, 64, 0, 0, 0, 0, 0]),
                (0x104, [33, 34, 33, 34, 33, 34, 0, 0]),
                (0x105, [33, 34, 33, 34, 33, 34, 0, 0]),
                (0x7F1, [(int(self.state.target_speed * 10) >> 8) & 0xFF, int(self.state.target_speed * 10) & 0xFF, 0,0,0,0,0,0]),
            ]
        for can_id, data in frames:
            self.send(channel, can_id, data)

def parse_addr(text: str) -> tuple[str, int]:
    host, port = text.rsplit(":", 1)
    return host, int(port)

async def amain() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES.keys(), default="normal_pass")
    parser.add_argument("--can1-target", default="127.0.0.1:8234")
    parser.add_argument("--can2-target", default="127.0.0.1:8235")
    parser.add_argument("--can1-listen", default="127.0.0.1:12341")
    parser.add_argument("--can2-listen", default="127.0.0.1:12342")
    parser.add_argument("--rate-hz", type=float, default=20)
    args = parser.parse_args()
    sim = Simulator(args.profile, parse_addr(args.can1_target), parse_addr(args.can2_target), parse_addr(args.can1_listen), parse_addr(args.can2_listen), args.rate_hz)
    await sim.start()

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        LOGGER.info("stopped")
