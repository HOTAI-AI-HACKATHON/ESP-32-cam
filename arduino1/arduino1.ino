#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "Charlessss";           // 填入你的熱點名稱
const char* password = "charles0000";   // 填入你的熱點密碼
String serverUrl = "http://172.20.10.5:5000/upload"; // 你的Python接收端網址

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

void take_picture_and_upload();

void setup() {
  Serial.begin(115200);
  Serial.println("\n啟動中...");

  WiFi.begin(ssid, password);
  Serial.print("連接 WiFi 中");
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retry++;
    if (retry > 40) {  // 約 20 秒還連不上就報告一次
      Serial.println("\nWiFi 連接逾時,持續嘗試中...");
      retry = 0;
    }
  }
  Serial.println("\nWiFi 已連接!");
  Serial.print("IP 位址: ");
  Serial.println(WiFi.localIP());

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_HD;
    config.jpeg_quality = 10;
    config.fb_count = 2;
    Serial.println("偵測到 PSRAM,使用 HD 畫質");
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    Serial.println("未偵測到 PSRAM,使用 SVGA 畫質");
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("相機初始化失敗,錯誤代碼: 0x%x\n", err);
    return;
  }
  Serial.println("相機初始化成功!");
  Serial.println("======== 初始化完成,開始拍照循環 ========\n");
}

void loop() {
  delay(10000);
  take_picture_and_upload();
}

void take_picture_and_upload() {
  Serial.println("--- 開始拍照 ---");
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("拍照失敗 (fb 為空)");
    return;
  }
  Serial.printf("拍照成功,大小: %d bytes\n", fb->len);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "image/jpeg");

    int httpCode = http.POST(fb->buf, fb->len);

    if (httpCode > 0) {
      Serial.printf("上傳結果 HTTP code: %d\n", httpCode);
      String response = http.getString();
      Serial.println("伺服器回應: " + response);
    } else {
      Serial.printf("上傳失敗,錯誤: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("WiFi 未連接,無法上傳");
  }

  esp_camera_fb_return(fb);
  Serial.println("--- 本輪結束 ---\n");
}