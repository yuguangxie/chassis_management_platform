from app.control.control_121 import Control121Command, encode_control_121, encode_i8_twos

def hx(cmd):
    return " ".join(f"{b:02X}" for b in encode_control_121(cmd))

def test_examples():
    assert hx(Control121Command(brake_enable=True)) == "40 00 00 00 02 00 00 00"
    assert hx(Control121Command(front_steering_cmd=60, rear_steering_cmd=60)) == "40 3C 3C 00 00 00 00 00"
    assert hx(Control121Command(front_steering_cmd=-60, rear_steering_cmd=-60)) == "40 C4 C4 00 00 00 00 00"
    assert hx(Control121Command(shift="D", target_speed_kmh=3)) == "41 00 00 1E 00 00 00 00"
    assert hx(Control121Command(shift="R", target_speed_kmh=3)) == "43 00 00 1E 00 00 00 00"

def test_i8_boundaries_and_clamp():
    assert encode_i8_twos(-60) == 0xC4
    assert encode_i8_twos(60) == 0x3C
    assert encode_i8_twos(-120) == 0x88
    assert encode_i8_twos(120) == 0x78
    assert encode_i8_twos(-999) == 0x88
    assert encode_i8_twos(999) == 0x78
