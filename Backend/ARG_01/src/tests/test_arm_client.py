import asyncio
from unittest.mock import AsyncMock

import pytest
from arm_client import ArmClient


async def test_multi_servo_lerp():
    client = ArmClient(ws_url="ws://test:82")

    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.recv.return_value = "OK"
    client._ws = mock_ws

    await client.move_smooth([100, 85, 90, 90], step_deg=2, delay=0.001)

    sent_packets = [call.args[0] for call in mock_ws.send.call_args_list]
    assert sent_packets == [
        "92,89,90,90",
        "94,88,90,90",
        "96,87,90,90",
        "98,86,90,90",
        "100,85,90,90",
    ]
    assert client.current_angles == [100, 85, 90, 90]


async def test_single_servo_helper():
    client = ArmClient(ws_url="ws://test:82")

    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.recv.return_value = "OK"
    client._ws = mock_ws

    await client.send_single_servo(servo_idx=2, angle=135)

    mock_ws.send.assert_called_once_with("90,90,135,90")
    assert client.current_angles == [90, 90, 135, 90]


async def test_validation_errors():
    client = ArmClient(ws_url="ws://test:82")

    with pytest.raises(ValueError):
        await client.send_angles([90, 90])

    with pytest.raises(ValueError):
        await client.send_angles([90, 200, 90, 90])


# --- 2. ЖИВОЙ ТЕСТ ВСЕЙ РУКИ НА ЖЕЛЕЗЕ (ESP32) ---

@pytest.mark.live
async def test_live_full_arm_kinematics():
    async with ArmClient() as arm:
        target_left = [40, 110, 70, 30]
        await arm.move_smooth(target_left, step_deg=2, delay=0.02)
        assert arm.current_angles == target_left
        await asyncio.sleep(0.5)

        target_right = [140, 60, 120, 160]
        await arm.move_smooth(target_right, step_deg=2, delay=0.02)
        assert arm.current_angles == target_right
        await asyncio.sleep(0.5)

        home = [90, 90, 90, 90]
        await arm.move_smooth(home, step_deg=2, delay=0.02)
        assert arm.current_angles == home