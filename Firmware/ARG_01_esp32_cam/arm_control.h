#pragma once

#include <ESP32Servo.h>
#include <ArduinoWebsockets.h>

const int SERVO_PIN = 12;
const uint16_t WS_PORT = 82;

Servo armServo;
websockets::WebsocketsServer wsServer;
websockets::WebsocketsClient wsClient; // Храним активного клиента глобально

void onMessageCallback(websockets::WebsocketsMessage message) {
  String data = message.data();
  Serial.print("[ARM WS] Получена команда: ");
  Serial.println(data);

  int angle = data.toInt();
  if (angle >= 0 && angle <= 180) {
    armServo.write(angle);
    Serial.printf("[ARM] Серва переведена в угол: %d°\n", angle);
    wsClient.send("OK: Angle set to " + String(angle));
  } else {
    wsClient.send("ERR: Out of range (0-180)");
  }
}

void arm_setup() {
  Serial.println("\n--- Инициализация манипулятора АРГ 01 ---");
  
  ESP32PWM::allocateTimer(2);
  armServo.setPeriodHertz(50);
  armServo.attach(SERVO_PIN, 500, 2400);

  armServo.write(90);
  Serial.println("[ARM] Серва запаркована в 90°");

  wsServer.listen(WS_PORT);
  Serial.printf("[ARM WS] Сервер команд запущен на порту: %d\n", WS_PORT);
}

void arm_loop() {
  // Если Python подключился (или переподключился после перезапуска скрипта)
  if (wsServer.poll()) {
    wsClient = wsServer.accept();
    Serial.println("[ARM WS] Бэкенд подключился!");
    wsClient.onMessage(onMessageCallback);
  }
  
  // Опрашиваем активное соединение, чтобы ловить прилетающие углы
  if (wsClient.available()) {
    wsClient.poll();
  }
}
