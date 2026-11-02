import threading
import time

import cv2
from config import settings
from ultralytics import YOLO


class VideoStreamHandler:
    def __init__(self, source: str | int | None = None, model_path: str = "yolov8n.pt"):
        self.source = source if source is not None else settings.esp32_stream_url
        self.model = YOLO(model_path)

        self.cap = cv2.VideoCapture(self.source)
        self.latest_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

        self.target_offset_x: int = 0
        self.target_y_bottom: int = 300
        self.target_detected: bool = False

    def start(self) -> "VideoStreamHandler":
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return self

    def _capture_loop(self) -> None:
        while self.running:
            success, frame = self.cap.read()
            if not success:
                time.sleep(0.05)
                continue

            with self.lock:
                self.latest_frame = frame

    def process_latest_frame(self, target_class: int = 0) -> tuple[cv2.Mat | None, int, bool]:

        with self.lock:
            if self.latest_frame is None:
                return None, 0, False
            frame = self.latest_frame.copy()

        height, width, _ = frame.shape
        center_screen_x = width // 2

        results = self.model(frame, verbose=False)
        
        detected = False
        offset_x = 0

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id == target_class:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    self.target_y_bottom = y2
                    obj_center_x = (x1 + x2) // 2

                    offset_x = obj_center_x - center_screen_x
                    detected = True

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.circle(frame, (obj_center_x, (y1 + y2) // 2), 5, (0, 0, 255), -1)
                    cv2.line(frame, (center_screen_x, 0), (center_screen_x, height), (255, 0, 0), 1)
                    
                    break
            if detected:
                break

        self.target_offset_x = offset_x
        self.target_detected = detected

        return frame, offset_x, detected

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()