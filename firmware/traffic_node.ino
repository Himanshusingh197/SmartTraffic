#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- EDIT THESE ----
const char* WIFI_SSID = "YOUR_WIFI_SSID";                             // ← EDIT
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";                         // ← EDIT
const char* SERVER = "http://172.26.16.215:5000/api/esp32/signals"; // ← EDIT (your laptop LAN IP)
// --------------------

// Pin mapping
#define N_G 25
#define N_Y 26
#define N_R 27
#define S_G 14
#define S_Y 12
#define S_R 13
#define E_G 32
#define E_Y 33
#define E_R 4
#define W_G 16
#define W_Y 17
#define W_R 5

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

void setup() {
  Serial.begin(115200);
  pinMode(N_G, OUTPUT); pinMode(N_Y, OUTPUT); pinMode(N_R, OUTPUT);
  pinMode(S_G, OUTPUT); pinMode(S_Y, OUTPUT); pinMode(S_R, OUTPUT);
  pinMode(E_G, OUTPUT); pinMode(E_Y, OUTPUT); pinMode(E_R, OUTPUT);
  pinMode(W_G, OUTPUT); pinMode(W_Y, OUTPUT); pinMode(W_R, OUTPUT);
  allRed();

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

  HTTPClient http;
  http.begin(SERVER);
  http.setTimeout(60000);
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
    }
  } else {
    Serial.print("HTTP error: ");
    Serial.println(code);
    allRed();
  }

  http.end();
  delay(1000);
}