from .models import CanFrame

class MockCanGateway:
    def make_frame(self, channel: str, can_id: int, data: list[int]) -> CanFrame:
        return CanFrame(channel=channel, can_id=can_id, dlc=8, data=(data + [0] * 8)[:8], source="mock")
