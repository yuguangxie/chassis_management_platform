from app.can_gateway.models import CanFrame
from app.can_gateway.usr_can115 import UsrCan115Codec

def test_usr_can115_encode_decode():
    codec = UsrCan115Codec()
    frame = CanFrame(channel="CAN2", can_id=0x121, dlc=8, data=[0x40,0,0,0,2,0,0,0])
    packet = codec.encode_frame(frame)
    assert len(packet) == 13
    decoded = codec.decode_packet(packet, "CAN2")
    assert decoded.can_id == 0x121
    assert decoded.data_hex == "40 00 00 00 02 00 00 00"

def test_decode_stream_sticky_and_half_packet():
    codec = UsrCan115Codec()
    p1 = codec.encode_frame(CanFrame(channel="CAN1", can_id=0x51, data=[1]*8))
    p2 = codec.encode_frame(CanFrame(channel="CAN1", can_id=0x77, data=[0]*8))
    frames, rest = codec.decode_stream(bytearray(p1 + p2 + p1[:5]), "CAN1")
    assert [f.can_id for f in frames] == [0x51, 0x77]
    assert len(rest) == 5

def test_dlc_and_reserved_validation():
    codec = UsrCan115Codec()
    bad = bytes([0x39]) + (0x51).to_bytes(4, "big") + bytes(8)
    frame = codec.decode_packet(bad, "CAN1")
    assert frame.parse_status == "reserved_bits_error"
    assert codec.stats.reserved_bit_errors == 1
