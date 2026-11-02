import asyncio
import logging

from arm_client import ArmClient
from vision import VideoStreamHandler
from y_calculate import calculate_vertical_angles

logger = logging.getLogger(__name__)

HOME_ANGLES = [90, 90, 90, 30]
GRIP_OPEN = 30
GRIP_CLOSE = 115

HANDOVER_S1 = 70
HANDOVER_S2 = 75


class ArmActions:
    def __init__(self, arm: ArmClient, vision: VideoStreamHandler):
        self.arm = arm
        self.vision = vision

    async def aim_at_target(
        self,
        target_class: int = 0,
        deadzone: int = 20,
        timeout: float = 8.0,
    ) -> bool:

        logger.info(f"Наведение башни на класс ID={target_class}")
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        stable_frames = 0

        while loop.time() - start_time < timeout:
            _, offset_x, detected = self.vision.process_latest_frame(target_class=target_class)

            if not detected:
                stable_frames = 0
                await asyncio.sleep(0.05)
                continue

            if abs(offset_x) <= deadzone:
                stable_frames += 1
                if stable_frames >= 3:
                    logger.info(
                        f"Цель залочена по центру (y_bottom={self.vision.target_y_bottom})"
                    )
                    return True
                await asyncio.sleep(0.04)
                continue

            stable_frames = 0
            current_s0 = self.arm.current_angles[0]

            step = 3 if abs(offset_x) > 60 else 1
            direction = -1 if offset_x > 0 else 1
            new_s0 = max(0, min(180, current_s0 + direction * step))

            if new_s0 != current_s0:
                await self.arm.send_single_servo(servo_idx=0, angle=new_s0)

            await asyncio.sleep(0.04)

        logger.warning(f"Таймаут наведения на класс ID={target_class}")
        return False

    async def approach_object(self, y_bottom: int | None = None) -> None:
        target_y = y_bottom if y_bottom is not None else self.vision.target_y_bottom
        s1, s2 = calculate_vertical_angles(target_y)

        logger.info(f"Опускание к предмету: y_bottom={target_y} -> s1={s1}°, s2={s2}°")
        target_angles = [
            self.arm.current_angles[0],
            s1,
            s2,
            self.arm.current_angles[3],
        ]
        await self.arm.move_smooth(target_angles, step_deg=2, delay=0.03)

    async def grip(self, close: bool = True) -> None:
        angle = GRIP_CLOSE if close else GRIP_OPEN
        await self.arm.send_single_servo(servo_idx=3, angle=angle)
        await asyncio.sleep(0.25)

    async def lift_up(self) -> None:
        target_angles = [
            self.arm.current_angles[0],
            HOME_ANGLES[1],
            HOME_ANGLES[2],
            self.arm.current_angles[3],
        ]
        await self.arm.move_smooth(target_angles, step_deg=2, delay=0.03)

    async def extend_to_human(self) -> None:
        target_angles = [
            self.arm.current_angles[0],
            HANDOVER_S1,
            HANDOVER_S2,
            self.arm.current_angles[3],
        ]
        await self.arm.move_smooth(target_angles, step_deg=2, delay=0.03)

    async def go_home(self) -> None:
        await self.arm.move_smooth(HOME_ANGLES, step_deg=2, delay=0.02)


async def execute_fetch_and_deliver(actions: ArmActions, item_class: int = 41) -> bool:
    try:
        await actions.go_home()
        await actions.grip(close=False)

        if not await actions.aim_at_target(target_class=item_class):
            await actions.go_home()
            return False

        await actions.approach_object()

        await actions.grip(close=True)
        await actions.lift_up()

        if await actions.aim_at_target(target_class=0):
            await actions.extend_to_human()
            await asyncio.sleep(3.0)
            await actions.grip(close=False)

        await actions.lift_up()
        await actions.go_home()
        return True

    except Exception as err:
        logger.exception(f"Ошибка при выполнении сценария: {err}")
        await actions.go_home()
        return False