#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.100:5000/upload";

const unsigned long CAPTURE_INTERVAL_MS = 15000;

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

unsigned long lastCaptureMs = 0;
void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(500);

  if (!startCamera()) {
    Serial.println("Camera init failed. Check the pin map and power supply.");
    return;
  }
  connectWiFi();
  lastCaptureMs = millis() - CAPTURE_INTERVAL_MS;
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (millis() - lastCaptureMs >= CAPTURE_INTERVAL_MS) {
    lastCaptureMs = millis();
    captureAndUpload();
  }
  delay(50);
}

bool startCamera() {
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
#else
    // Arduino-ESP32 2.x kept the older field names.
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
#endif
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.frame_size = FRAMESIZE_VGA;
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 1;

    if (psramFound()) {
        config.frame_size = FRAMESIZE_SVGA;
        config.jpeg_quality = 10;
        config.fb_count = 2;
    } else {
        config.fb_location = CAMERA_FB_IN_DRAM;
    }

    return esp_camera_init(&config) == ESP_OK;
}

void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) {
        return;
    }
    Serial.printf("Connecting to %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    for (int attempt = 0; attempt < 30 && WiFi.status() != WL_CONNECTED; attempt++) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("Wi-Fi connected. ESP32 address: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("Wi-Fi connection failed.");
    }
}

void captureAndUpload() {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }

    camera_fb_t* frame = esp_camera_fb_get();
    if (!frame) {
        Serial.println("Capture failed.");
        return;
    }

    HTTPClient http;
    http.setTimeout(15000);
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "image/jpeg");
    int statusCode = http.POST(frame->buf, frame->len);
    Serial.printf("Upload %u bytes -> HTTP %d\n", frame->len, statusCode);
    http.end();
    esp_camera_fb_return(frame);
}