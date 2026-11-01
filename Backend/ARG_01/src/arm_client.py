import asyncio
import logging

import websockets
from config import settings
from websockets.exceptions import ConnectionClosed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ArmClient:
    def __init__(self, ws_url: str | None = None, num_servos: int = 4):
        self.uri = ws_url or settings.esp32_ws_url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._lock = asyncio.Lock()
        self.num_servos = num_servos
        self.current_angles: list[int] = [90] * num_servos

    async def connect(self) -> None:
        try:
            self._ws = await websockets.connect(self.uri, ping_interval=None)
            logger.info(f"Успешный коннект к манипулятору: {self.uri}")
        except Exception as e:
            logger.error(f"Ошибка подключения к {self.uri}: {e}")
            self._ws = None
            raise

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("Соединение с ESP32 закрыто")

    def _validate_angles(self, angles: list[int]) -> None:
        if len(angles) != self.num_servos:
            raise ValueError(f"Ожидается {self.num_servos} углов, получено {len(angles)}")
        if any(not (0 <= a <= 180) for a in angles):
            raise ValueError(f"Все углы должны быть в диапазоне 0-180: {angles}")

    async def send_angles(self, angles: list[int]) -> str:
        self._validate_angles(angles)

        async with self._lock:
            if self._ws is None or self._ws.closed:
                await self.connect()

            try:
                payload = ",".join(map(str, angles))
                await self._ws.send(payload)
                response = await asyncio.wait_for(self._ws.recv(), timeout=2.0)
                self.current_angles = list(angles)
                return str(response)
            except (ConnectionClosed, asyncio.TimeoutError) as err:
                logger.warning(f"Сбой связи ({err}), сбрасываем сокет")
                self._ws = None
                raise

    async def send_single_servo(self, servo_idx: int, angle: int) -> str:
        if not (0 <= servo_idx < self.num_servos):
            raise IndexError(f"Индекс сервы {servo_idx} вне диапазона 0-{self.num_servos - 1}")

        target = list(self.current_angles)
        target[servo_idx] = angle
        return await self.send_angles(target)

    async def move_smooth(
        self,
        target_angles: list[int],
        step_deg: int = 2,
        delay: float = 0.02,
    ) -> None:
        self._validate_angles(target_angles)

        max_diff = max(abs(t - c) for t, c in zip(target_angles, self.current_angles))
        if max_diff == 0:
            return

        steps_count = max(1, max_diff // step_deg)
        start_angles = list(self.current_angles)

        for step in range(1, steps_count + 1):
            progress = step / steps_count
            intermediate = [
                round(start + (target - start) * progress)
                for start, target in zip(start_angles, target_angles)
            ]
            await self.send_angles(intermediate)
            await asyncio.sleep(delay)

    async def move_single_smooth(
        self,
        servo_idx: int,
        angle: int,
        step_deg: int = 2,
        delay: float = 0.02,
    ) -> None:
        if not (0 <= servo_idx < self.num_servos):
            raise IndexError(f"Индекс сервы {servo_idx} вне диапазона 0-{self.num_servos - 1}")

        target = list(self.current_angles)
        target[servo_idx] = angle
        await self.move_smooth(target, step_deg=step_deg, delay=delay)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()