from app.can_gateway.models import CanFrame
from app.can_gateway.usr_can115 import UsrCan115Codec
import pytest

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


@pytest.mark.parametrize("can_id", [0, 0x7FF])
def test_standard_can_id_boundaries_are_accepted(can_id):
    codec = UsrCan115Codec()
    packet = codec.encode_frame(CanFrame(channel="CAN1", can_id=can_id, data=[]))
    assert codec.decode_packet(packet, "CAN1").parse_status == "ok"


@pytest.mark.parametrize("can_id", [0, 0x1FFFFFFF])
def test_extended_can_id_boundaries_are_accepted(can_id):
    codec = UsrCan115Codec()
    packet = codec.encode_frame(
        CanFrame(channel="CAN1", can_id=can_id, is_extended=True, data=[])
    )
    assert codec.decode_packet(packet, "CAN1").parse_status == "ok"


@pytest.mark.parametrize(
    ("can_id", "is_extended"),
    [(-1, False), (0x800, False), (-1, True), (0x20000000, True)],
)
def test_encode_rejects_out_of_range_can_ids(can_id, is_extended):
    codec = UsrCan115Codec()
    with pytest.raises(ValueError, match="CAN ID"):
        codec.encode_frame(
            CanFrame(
                channel="CAN1",
                can_id=can_id,
                is_extended=is_extended,
                data=[],
            )
        )


@pytest.mark.parametrize(
    ("frame_info", "can_id"),
    [(0x08, 0x800), (0x88, 0x20000000)],
)
def test_decode_marks_out_of_range_can_ids(frame_info, can_id):
    codec = UsrCan115Codec()
    packet = bytes([frame_info]) + can_id.to_bytes(4, "big") + bytes(8)
    frame = codec.decode_packet(packet, "CAN1")
    assert frame.parse_status == "can_id_range_error"
    assert codec.stats.can_id_range_errors == 1


def test_rtr_dlc_and_payload_constraints_remain_strict():
    codec = UsrCan115Codec()
    remote = CanFrame(
        channel="CAN1",
        can_id=0x321,
        is_remote=True,
        dlc=4,
        data=[],
    )
    decoded = codec.decode_packet(codec.encode_frame(remote), "CAN1")
    assert decoded.is_remote is True
    assert decoded.dlc == 4
    assert decoded.data_hex == "00 00 00 00"

    with pytest.raises(ValueError, match="DLC"):
        codec.encode_frame(CanFrame(channel="CAN1", can_id=0x321, dlc=9, data=[]))
    with pytest.raises(ValueError, match="data area"):
        codec.encode_frame(CanFrame(channel="CAN1", can_id=0x321, data=[0] * 9))
    with pytest.raises(ValueError, match="data bytes"):
        codec.encode_frame(CanFrame(channel="CAN1", can_id=0x321, data=[256]))
