from can_frame_simulator import PROFILES, Simulator, build_usr_can115_frame, parse_121

def test_builder_and_parse_121():
    p = build_usr_can115_frame(0x121, [0x41,0,0,0x1E,0,0,0,0])
    assert len(p) == 13
    assert parse_121(p)["target_speed"] == 3.0


def test_parse_signed_steering_golden_vectors():
    for angle, encoded in [(-120, 0x88), (-60, 0xC4), (0, 0x00), (60, 0x3C), (120, 0x78)]:
        packet = build_usr_can115_frame(0x121, [0x81, encoded, encoded, 0, 0, 0, 0, 0])
        decoded = parse_121(packet)
        assert decoded["front"] == angle
        assert decoded["rear"] == angle


def test_brake_fail_profile_does_not_report_brake_feedback():
    simulator = Simulator(
        "brake_fail",
        ("127.0.0.1", 8234),
        ("127.0.0.1", 8235),
        ("127.0.0.1", 12341),
        ("127.0.0.1", 12342),
    )
    assert PROFILES["brake_fail"]["brake_response"] is False
    assert simulator.channel_socks == {}
