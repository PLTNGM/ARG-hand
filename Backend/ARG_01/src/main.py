import asyncio
import logging
from contextlib import asynccontextmanager

import cv2
import uvicorn
from action import ArmActions
from arm_client import ArmClient
from config import settings
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from vision import VideoStreamHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class AppState:
    arm: ArmClient
    vision: VideoStreamHandler
    actions: ArmActions
    active_target_class: int = 0


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.arm = ArmClient(url=settings.esp32_ws_url)
    stream_src = 0 if settings.esp32_stream_url == "0" else settings.esp32_stream_url
    state.vision = VideoStreamHandler(source=stream_src).start()
    state.actions = ArmActions(arm=state.arm, vision=state.vision)

    try:
        await state.arm.connect()
        logger.info("Перевод манипулятора в стартовую парковку...")
        await state.actions.go_home()
    except Exception as err:
        logger.warning(f"ESP32 недоступна при старте (пропуск парковки): {err}")

    yield

    logger.info("Остановка сервера: возврат манипулятора в парковку...")
    try:
        if state.arm.ws is not None:
            await state.actions.go_home()
    except Exception as err:
        logger.warning(f"Не удалось запарковать руку при выходе: {err}")
    finally:
        state.vision.stop()
        await state.arm.close()


app = FastAPI(title="ARG Robotic Arm Backend", lifespan=lifespan)


async def mjpeg_generator():
    while True:
        frame, _, _ = state.vision.process_latest_frame(target_class=state.active_target_class)
        if frame is None:
            await asyncio.sleep(0.05)
            continue

        success, encoded_jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            await asyncio.sleep(0.02)
            continue

        frame_bytes = encoded_jpg.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        await asyncio.sleep(0.04)


@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
