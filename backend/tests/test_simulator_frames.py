import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "simulator"))
from can_frame_simulator import build_usr_can115_frame

def test_simulator_frame_builder():
    packet = build_usr_can115_frame(0x121, [0x40,0,0,0,2,0,0,0])
    assert len(packet) == 13
    assert packet[0] == 8
    assert packet[1:5] == (0x121).to_bytes(4, "big")
