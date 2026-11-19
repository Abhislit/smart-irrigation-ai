/*
 * ESP32 irrigation node: moisture probe -> /sensor -> pump.
 *
 * Safety lives here, not on the laptop. Max burst 60 s, min gap 45 min,
 * sensor-fault cutoff, and a local fallback if WiFi or the PC disappears.
 *
 * Wiring
 *   sensor VCC  -> GPIO25   (power-gated: probe is only powered while reading)
 *   sensor AOUT -> GPIO34   (must be an ADC1 pin: GPIO32-39)
 *   sensor GND  -> GND
 *   pump +      -> 5V adapter +
 *   pump -      -> MOSFET module drain
 *   MOSFET gate -> GPIO26   (gate pulldown 10k to GND)
 *   1N4007 across the pump, cathode to +5V   <- without this the ESP32 resets
 *   GND: adapter, ESP32 and MOSFET all common
 */

#include <WiFi.h>
#include <HTTPClient.h>

const char *WIFI_SSID = "YOUR_WIFI";
const char *WIFI_PASS = "YOUR_PASSWORD";
const char *ENDPOINT = "http://192.168.1.10:8000/sensor";  // laptop LAN IP

const int PIN_SM = 34;
const int PIN_SM_PWR = 25;
const int PIN_PUMP = 26;

const float ADC_DRY = 2900;  // raw value in dry air      -> calibrate
const float ADC_WET = 1200;  // raw value in a cup of water -> calibrate

const unsigned long SAMPLE_MS = 60000;
const unsigned long BURST_MS = 40000;
const unsigned long MAX_BURST_MS = 60000;
const unsigned long MIN_GAP_MS = 45UL * 60000UL;

bool pumpOn = false;
bool everIrrigated = false;
unsigned long pumpStart = 0;
unsigned long pumpStopAt = 0;
unsigned long lastIrrigation = 0;
int fails = 0;

float readMoisture() {
  digitalWrite(PIN_SM_PWR, HIGH);
  delay(2000);  // probe settling time
  long sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogRead(PIN_SM);
    delay(10);
  }
  digitalWrite(PIN_SM_PWR, LOW);
  float raw = sum / 16.0;
  float pct = (ADC_DRY - raw) * 100.0 / (ADC_DRY - ADC_WET);
  return constrain(pct, 0.0, 100.0);
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

String askServer(float sm) {
  if (WiFi.status() != WL_CONNECTED) return "";
  HTTPClient http;
  http.setTimeout(4000);
  if (!http.begin(ENDPOINT)) return "";
  http.addHeader("Content-Type", "application/json");
  char body[64];
  snprintf(body, sizeof(body), "{\"soil_moisture\": %.1f}", sm);
  int code = http.POST(body);
  String resp = code == 200 ? http.getString() : "";
  http.end();
  if (!resp.length()) return "";
  int i = resp.indexOf("\"need\": \"");
  if (i < 0) return "";
  i += 9;
  return resp.substring(i, resp.indexOf('"', i));
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
  Serial.println(WiFi.status() == WL_CONNECTED ? "wifi ok" : "wifi FAILED - local fallback active");
}

void loop() {
  // safety runs every iteration, never inside the sampling branch
  if (pumpOn && millis() - pumpStart > MAX_BURST_MS) setPump(false);
  if (pumpOn && pumpStopAt && millis() >= pumpStopAt) setPump(false);

  if (Serial.available()) {  // manual override for the demo: o = on, f = off
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
  String need = askServer(sm);
  Serial.printf("sm=%.1f%%  need=%s  pump=%d\n", sm, need.c_str(), pumpOn);

  bool sensorSane = sm > 5.0 && sm < 95.0;
  if (need.length()) {
    fails = 0;
    if (need == "High" && !pumpOn && sensorSane && gapElapsed()) {
      setPump(true);
      pumpStopAt = millis() + BURST_MS;
    } else if (need == "Low") {
      setPump(false);
    }
  } else if (++fails >= 3) {
    fails = 0;
    if (!pumpOn && sm < 20.0 && sensorSane && gapElapsed()) {
      setPump(true);
      pumpStopAt = millis() + 30000;
    }
  }
}
