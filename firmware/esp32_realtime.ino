/*
 * ESP32 realtime irrigation node.
 *
 * Every 60 s: read the moisture probe, POST it to /ingest, then poll /command.
 * Commands are one-shot: each id is executed once and acknowledged on the next
 * ingest. All pump safety is enforced here, never in Python.
 *
 * Wiring
 *   probe VCC -> GPIO25 (powered only while reading)
 *   probe AOUT -> GPIO34 (ADC1)
 *   probe GND -> GND
 *   pump + -> 5 V adapter +, pump - -> MOSFET drain, gate -> GPIO26
 *   1N4007 across the pump, cathode to +5 V; all grounds common
 */

#include <WiFi.h>
#include <HTTPClient.h>

const char *WIFI_SSID = "YOUR_WIFI";
const char *WIFI_PASS = "YOUR_PASSWORD";
const char *API_BASE = "http://192.168.1.10:8000";  // laptop LAN IP

const int PIN_SM = 34;
const int PIN_SM_PWR = 25;
const int PIN_PUMP = 26;

const float ADC_DRY = 2900;  // raw in dry air - calibrate for your probe
const float ADC_WET = 1200;  // raw in a cup of water - calibrate

const unsigned long SAMPLE_MS = 60000;
const unsigned long MAX_BURST_MS = 60000;
const unsigned long MIN_GAP_MS = 45UL * 60000UL;

bool pumpOn = false;
bool everIrrigated = false;
unsigned long pumpStart = 0;
unsigned long pumpStopAt = 0;
unsigned long lastIrrigation = 0;
int fails = 0;
String lastCommandId = "";

float readMoisture() {
  digitalWrite(PIN_SM_PWR, HIGH);
  delay(2000);
  long sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogRead(PIN_SM);
    delay(10);
  }
  digitalWrite(PIN_SM_PWR, LOW);
  float raw = sum / 16.0;
  return constrain((ADC_DRY - raw) * 100.0 / (ADC_DRY - ADC_WET), 0.0, 100.0);
}

void setPump(bool on) {
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  pumpOn = on;
  if (on) {
    pumpStart = millis();
    lastIrrigation = millis();
    everIrrigated = true;
  } else {
    pumpStopAt = 0;
  }
}

bool gapElapsed() {
  return !everIrrigated || (millis() - lastIrrigation > MIN_GAP_MS);
}

bool postReading(float sm) {
  HTTPClient http;
  if (!http.begin(String(API_BASE) + "/ingest")) return false;
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(4000);
  char body[128];
  snprintf(body, sizeof(body),
           "{\"moisture\":%.1f,\"pump_state\":%d,\"last_command_id\":\"%s\"}",
           sm, pumpOn ? 1 : 0, lastCommandId.c_str());
  int code = http.POST(body);
  http.end();
  return code == 200;
}

int jsonInt(const String &s, const char *key) {
  int i = s.indexOf(key);
  if (i < 0) return 0;
  i = s.indexOf(':', i) + 1;
  return s.substring(i, s.indexOf(',', i) > 0 ? s.indexOf(',', i) : s.indexOf('}', i)).toInt();
}

void pollCommand(float sm) {
  HTTPClient http;
  if (!http.begin(String(API_BASE) + "/command")) return;
  http.setTimeout(4000);
  int code = http.GET();
  String resp = code == 200 ? http.getString() : "";
  http.end();
  if (!resp.length()) return;

  int i = resp.indexOf("\"id\": \"");
  if (i < 0) return;
  i += 7;
  String id = resp.substring(i, resp.indexOf('"', i));
  if (id.length() == 0 || id == lastCommandId) return;

  int duration_s = jsonInt(resp, "\"duration_s\"");
  if (duration_s > 60 || duration_s <= 0) return;  // never trust a long burst
  if (pumpOn || !gapElapsed() || sm < 5.0 || sm > 95.0) return;

  lastCommandId = id;  // acknowledged by the next ingest
  setPump(true);
  pumpStopAt = millis() + (unsigned long)duration_s * 1000UL;
  Serial.printf("command %s -> %d s burst\n", id.c_str(), duration_s);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SM_PWR, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);
  digitalWrite(PIN_SM_PWR, LOW);
  digitalWrite(PIN_PUMP, LOW);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) delay(200);
  Serial.println(WiFi.status() == WL_CONNECTED ? "wifi ok" : "wifi FAILED - fallback active");
}

void loop() {
  // safety runs every loop, outside the sampling branch
  if (pumpOn && millis() - pumpStart > MAX_BURST_MS) setPump(false);
  if (pumpOn && pumpStopAt && millis() >= pumpStopAt) setPump(false);

  if (Serial.available()) {  // demo override: o = ON, f = OFF
    char c = Serial.read();
    if (c == 'o') setPump(true);
    if (c == 'f') setPump(false);
  }

  static unsigned long nextSample = 0;
  if (millis() < nextSample) {
    delay(50);
    return;
  }
  nextSample = millis() + SAMPLE_MS;

  float sm = readMoisture();
  bool ok = WiFi.status() == WL_CONNECTED && postReading(sm);
  if (ok) {
    fails = 0;
    pollCommand(sm);
  } else if (++fails >= 3) {
    fails = 0;
    if (!pumpOn && sm < 20.0 && gapElapsed()) {
      setPump(true);
      pumpStopAt = millis() + 30000;
    }
  }
  Serial.printf("sm=%.1f%% pump=%d acks=%s\n", sm, pumpOn, lastCommandId.c_str());
}
