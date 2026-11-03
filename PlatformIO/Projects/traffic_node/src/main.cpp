// SmartChauraha - ESP8266 node
// Flash the SAME file to both boards; only change BOARD_ID.
//   BOARD_ID 1 -> controls NORTH + SOUTH LEDs
//   BOARD_ID 2 -> controls EAST  + WEST  LEDs
// Each board polls the Flask app (GET /api/esp8266/signals) and mirrors the
// state for its own two lanes. The app is the single source of truth, so the
// boards never need to talk to each other.

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ================= EDIT THESE =================
#define BOARD_ID 1                       // 1 = north+south, 2 = east+west
#define USE_OLED 1                       // 0 if this board has no OLED
const char*    WIFI_SSID   = "YOUR_WIFI_SSID";
const char*    WIFI_PASS   = "YOUR_WIFI_PASSWORD";
const char*    SERVER_HOST = "172.26.16.215";   // laptop LAN IP, no http://
const uint16_t SERVER_PORT = 5000;
// ==============================================

// ---- Pin map (NodeMCU labels). LED: pin -> 220 ohm -> LED anode, cathode -> GND
struct Lane { const char* name; uint8_t g, y, r; };
#if BOARD_ID == 1
const char* DEVICE = "esp8266-1";
const Lane LANES[2] = { {"north", D5, D6, D7}, {"south", D0, D8, D4} };
#else
const char* DEVICE = "esp8266-2";
const Lane LANES[2] = { {"east",  D5, D6, D7}, {"west",  D0, D8, D4} };
#endif
// OLED I2C: SDA = D2, SCL = D1

#if USE_OLED
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;
#endif

WiFiClient client;
String SIGNALS_URL, STATUS_URL;

String laneState[2] = {"RED", "RED"};
int    laneRem[2]   = {0, 0};
String phase = "idle";
String netMsg = "starting";

unsigned long lastPoll = 0, lastPost = 0, lastOk = 0;
uint8_t failCount = 0;

void setLane(const Lane& l, const String& s) {
  digitalWrite(l.g, s == "GREEN"  ? HIGH : LOW);
  digitalWrite(l.y, s == "YELLOW" ? HIGH : LOW);
  digitalWrite(l.r, s == "RED"    ? HIGH : LOW);
}

void allRed() {
  for (int i = 0; i < 2; i++) { laneState[i] = "RED"; laneRem[i] = 0; setLane(LANES[i], "RED"); }
}

void drawOled() {
#if USE_OLED
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("Board "); oled.print(BOARD_ID); oled.print("  "); oled.print(netMsg);
  oled.setCursor(0, 12);
  oled.print("Phase: "); oled.print(phase);
  oled.setTextSize(2);
  for (int i = 0; i < 2; i++) {
    oled.setCursor(0, 28 + i * 18);
    String n = LANES[i].name; n.setCharAt(0, toupper(n.charAt(0)));
    oled.print(n.substring(0, 1)); oled.print(' ');
    oled.print(laneState[i].substring(0, 1)); oled.print(' ');
    if (laneRem[i] > 0) { oled.print(laneRem[i]); oled.print('s'); }
  }
  oled.display();
#endif
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected. IP: "); Serial.println(WiFi.localIP());
    netMsg = "online";
  } else {
    Serial.println("WiFi failed (will keep retrying)");
    netMsg = "no wifi";
  }
}

// App -> ESP: fetch signal states and apply this board's lanes
bool pollSignals() {
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(client, SIGNALS_URL)) return false;
  int code = http.GET();
  bool ok = false;
  if (code == HTTP_CODE_OK) {
    StaticJsonDocument<768> doc;
    if (!deserializeJson(doc, http.getString())) {
      for (int i = 0; i < 2; i++) {
        const char* s = doc["signals"][LANES[i].name] | "RED";
        laneState[i] = s;
        laneRem[i]   = doc["remaining"][LANES[i].name] | 0;
        setLane(LANES[i], laneState[i]);
      }
      phase = (const char*)(doc["phase"] | "idle");
      ok = true;
    }
  } else {
    Serial.print("GET failed: "); Serial.println(code);
  }
  http.end();
  return ok;
}

// ESP -> App: heartbeat/status
void postStatus() {
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(client, STATUS_URL)) return;
  http.addHeader("Content-Type", "application/json");
  StaticJsonDocument<256> doc;
  doc["device"] = DEVICE;
  doc["board"]  = BOARD_ID;
  doc["ip"]     = WiFi.localIP().toString();
  doc["rssi"]   = WiFi.RSSI();
  doc["uptime"] = millis() / 1000;
  doc["signals"] = laneState[0] + "," + laneState[1];
  String body; serializeJson(doc, body);
  int code = http.POST(body);
  if (code != HTTP_CODE_OK) { Serial.print("POST failed: "); Serial.println(code); }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(100);
  for (int i = 0; i < 2; i++) {
    pinMode(LANES[i].g, OUTPUT); pinMode(LANES[i].y, OUTPUT); pinMode(LANES[i].r, OUTPUT);
  }
  allRed();

#if USE_OLED
  Wire.begin(D2, D1);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) Serial.println("OLED not found (check wiring / address 0x3C)");
#endif

  SIGNALS_URL = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/esp8266/signals";
  STATUS_URL  = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/esp8266/status";

  drawOled();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    allRed(); netMsg = "no wifi"; drawOled();
    delay(500);
    return;
  }

  unsigned long now = millis();

  if (now - lastPoll >= 500) {              // poll twice a second
    lastPoll = now;
    if (pollSignals()) { failCount = 0; lastOk = now; netMsg = "online"; }
    else if (++failCount >= 3) { allRed(); netMsg = "app down"; }   // fail-safe
    drawOled();
  }

  if (now - lastPost >= 5000) {
    lastPost = now;
    postStatus();
  }
}