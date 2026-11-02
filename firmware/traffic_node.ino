#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- EDIT THESE ----
const char* WIFI_SSID = "YOUR_WIFI_SSID";       // ← EDIT
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";   // ← EDIT
const char* SERVER_HOST = "172.26.16.215";      // ← EDIT (your laptop LAN IP, no http://)
const int   SERVER_PORT = 5000;
// --------------------

String SIGNALS_URL;   // ESP32 <- App  (GET)
String STATUS_URL;    // ESP32 -> App  (POST)

// Pin mapping
#define N_G 25
#define N_Y 26
#define N_R 27
#define S_G 14
#define S_Y 12   // GPIO12 is a strapping pin; move to 18/19/21/22/23 if boot problems occur
#define S_R 13
#define E_G 32
#define E_Y 33
#define E_R 4
#define W_G 16
#define W_Y 17
#define W_R 5

String lastSignals = "";
unsigned long lastPost = 0;

void setLane(int g, int y, int r, String state) {
  digitalWrite(g, state == "GREEN"  ? HIGH : LOW);
  digitalWrite(y, state == "YELLOW" ? HIGH : LOW);
  digitalWrite(r, state == "RED"    ? HIGH : LOW);
}

void allRed() {
  setLane(N_G, N_Y, N_R, "RED");
  setLane(S_G, S_Y, S_R, "RED");
  setLane(E_G, E_Y, E_R, "RED");
  setLane(W_G, W_Y, W_R, "RED");
}

// ESP32 -> App: send status, read the server's response
void sendStatus() {
  HTTPClient http;
  http.begin(STATUS_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  StaticJsonDocument<256> doc;
  doc["device"] = "esp32-1";
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["uptime"] = millis() / 1000;
  doc["signals"] = lastSignals;

  String body;
  serializeJson(doc, body);

  int code = http.POST(body);              // send request
  if (code == 200) {
    String resp = http.getString();        // read response
    Serial.println("Server replied: " + resp);
  } else {
    Serial.println("POST failed: " + String(code));
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(N_G, OUTPUT); pinMode(N_Y, OUTPUT); pinMode(N_R, OUTPUT);
  pinMode(S_G, OUTPUT); pinMode(S_Y, OUTPUT); pinMode(S_R, OUTPUT);
  pinMode(E_G, OUTPUT); pinMode(E_Y, OUTPUT); pinMode(E_R, OUTPUT);
  pinMode(W_G, OUTPUT); pinMode(W_Y, OUTPUT); pinMode(W_R, OUTPUT);
  allRed();

  SIGNALS_URL = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/esp32/signals";
  STATUS_URL  = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/esp32/status";

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println();
  Serial.print("Connected. IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    allRed();
    delay(1000);
    return;
  }

  // App -> ESP32: get signal states
  HTTPClient http;
  http.begin(SIGNALS_URL);
  http.setTimeout(3000);
  int code = http.GET();

  if (code == 200) {
    String payload = http.getString();
    StaticJsonDocument<512> doc;
    if (!deserializeJson(doc, payload)) {
      JsonObject sig = doc["signals"];
      setLane(N_G, N_Y, N_R, String((const char*)(sig["north"] | "RED")));
      setLane(S_G, S_Y, S_R, String((const char*)(sig["south"] | "RED")));
      setLane(E_G, E_Y, E_R, String((const char*)(sig["east"]  | "RED")));
      setLane(W_G, W_Y, W_R, String((const char*)(sig["west"]  | "RED")));

      lastSignals = String((const char*)(sig["north"] | "RED")) + "," +
                    String((const char*)(sig["south"] | "RED")) + "," +
                    String((const char*)(sig["east"]  | "RED")) + "," +
                    String((const char*)(sig["west"]  | "RED"));
    }
  } else {
    Serial.print("HTTP error: ");
    Serial.println(code);
    allRed();
  }

  http.end();

  // ESP32 -> App: send status every 5 seconds
  if (millis() - lastPost > 5000) {
    lastPost = millis();
    sendStatus();
  }

  delay(1000);
}