from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ESP32_HOST: str
    ESP32_WS_PORT: int = 82
    ESP32_STREAM_PORT: int = 81

    YOLO_MODEL_PATH: str = "yolov8n.pt"
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    @computed_field
    @property
    def esp32_ws_url(self) -> str:
        return f"ws://{self.ESP32_HOST}:{self.ESP32_WS_PORT}"

    @computed_field
    @property
    def esp32_stream_url(self) -> str:
        return f"http://{self.ESP32_HOST}:{self.ESP32_STREAM_PORT}/stream"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()