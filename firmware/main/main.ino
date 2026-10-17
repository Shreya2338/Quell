#include <Arduino.h>
#include <Wire.h>
#include <math.h>

#include "MPU6050Driver.h"
#include "TremorHaptic.h"
#include "LaptopLink.h"

// ============================ CONFIG ============================

constexpr int MPU_SDA_PIN = 8;
constexpr int MPU_SCL_PIN = 7;
constexpr int HAPTIC_SDA_PIN = 12;
constexpr int HAPTIC_SCL_PIN = 13;

constexpr int8_t HAPTIC_EN_PIN = -1; // DRV2605L EN pin, -1 if not wired

// WIFI/Laptop
const char* WIFI_SSID = "quell";
const char* WIFI_PASS = "a1234567";
const uint16_t LAPTOP_PORT = 5000;
const char* LAPTOP_HOST = nullptr; // nullptr = use WiFi gateway IP (laptop hotspot). Or e.g. "192.168.1.50"

// Sensor/haptics 
constexpr uint16_t SAMPLE_RATE_HZ = 200;
constexpr uint8_t  VIBRATION_PCT = 60; // DEFAULT intensity (0-100 %), used when a command has no "intensity"

// Motor (ZYAMY 10 mm x 2.7 mm coin ERM, 3 V, 12000 RPM)
constexpr float MOTOR_RATED_RPM = 12000.0f;
constexpr float MOTOR_MAX_HZ = MOTOR_RATED_RPM / 60.0f; // 200 Hz at 100 %
constexpr uint16_t VIBRATION_RAMP_MS = 20; // fade in/out within the burst
constexpr uint32_t MAX_VIBRATION_MS = 10000;  // safety clamp
constexpr uint16_t CALIBRATION_SAMPLES = 500; // ~2.5 s at 200 Hz
constexpr bool CALIBRATE_ON_BOOT = true;

// ==========================================================================

constexpr bool SHARED_BUS = (MPU_SDA_PIN == HAPTIC_SDA_PIN) && (MPU_SCL_PIN == HAPTIC_SCL_PIN);
constexpr float DEG2RAD_F = 0.01745329252f;

MPU6050Driver imu;
TremorHaptic haptic(SHARED_BUS ? Wire : Wire1, HAPTIC_EN_PIN);
LaptopLink laptoplink;

bool calibrated = false;
bool calibrateRequested = false;
bool prevLinkConnected = false;
bool prevHapticRunning = false;
uint8_t activeIntensity = 0; 
uint8_t vibrationPct = VIBRATION_PCT;  

// ---------------------------------------------------------------- helpers

void sendCalibrationStatus() {
  laptoplink.printf("{\"caliberation_status\":%d}\n", calibrated ? 1 : 0);
}

int estimateHz(uint8_t pct) {
  if (pct > 100) pct = 100;
  return (int)lroundf(MOTOR_MAX_HZ * pct / 100.0f);
}

void sendVibrationState(bool on, uint8_t pct) {
  laptoplink.printf("{\"actuation_state\":%d,\"actuation_intensity\":%d}\n", on ? 1 : 0, on ? estimateHz(pct) : 0);
}

void runCalibration() {
  Serial.println("[main] calibrating - keep the board still, Z up");
  calibrated = false;
  sendCalibrationStatus(); // 0 = in progress

  bool ok = imu.calibrate(CALIBRATION_SAMPLES);
  calibrated = ok;
  Serial.println(ok ? "[main] calibration OK" : "[main] calibration FAILED (motion or I2C error)");
  sendCalibrationStatus(); // 1 = done, 0 = failed
}

void startVibration(uint32_t lengthMs, uint8_t pct) {
  if (lengthMs == 0) {
    haptic.stop();
    return;
  }
  if (lengthMs > MAX_VIBRATION_MS) lengthMs = MAX_VIBRATION_MS;
  if (pct > 100) pct = 100;

  TremorHaptic::Pattern p;
  p.intensity = pct;
  p.onMs = (uint16_t)lengthMs;
  p.offMs = 0; // continuous burst
  p.rampMs = VIBRATION_RAMP_MS;
  p.totalMs = lengthMs; // stop automatically afterwards
  haptic.start(p);

  activeIntensity = pct;
  prevHapticRunning = true;
  sendVibrationState(true, activeIntensity);
}

void handleCommand(const char* line) {
  if (strstr(line, "calibrate_now")) {
    calibrateRequested = true;
    return;
  }
  const char* k = strstr(line, "\"length\"");
  if (k) {
    const char* colon = strchr(k, ':');
    if (colon) {
      long len = atol(colon + 1);
      if (len < 0) len = 0;

      // optional: {"length":500,"intensity":80}  (percent, 0-100)
      long pct = vibrationPct;
      const char* ik = strstr(line, "\"intensity\"");
      if (ik) {
        const char* ic = strchr(ik, ':');
        if (ic) pct = constrain(atol(ic + 1), 0L, 100L);
      }
      startVibration((uint32_t)len, (uint8_t)pct);
    }
    return;
  }
  Serial.printf("[main] unknown command: %s\n", line);
}

void linearAccel(float &lx, float &ly, float &lz) {
  const auto &a = imu.accel();
  const auto &o = imu.orientation();
  float r = o.roll  * DEG2RAD_F;
  float p = o.pitch * DEG2RAD_F;

  // gravity direction in sensor frame; matches the driver's roll/pitch convention
  float gx = -sinf(p);
  float gy =  sinf(r) * cosf(p);
  float gz =  cosf(r) * cosf(p);

  lx = a.x - gx;
  ly = a.y - gy;
  lz = a.z - gz;
}

void halt(const char* msg) {
  while (true) {
    Serial.println(msg);
    delay(1000);
  }
}

// ---------------------------------------------------------------- setup / loop

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[main] starting");

  // I2C buses
  Wire.begin(MPU_SDA_PIN, MPU_SCL_PIN);
  if (!SHARED_BUS) Wire1.begin(HAPTIC_SDA_PIN, HAPTIC_SCL_PIN);

  if (!imu.begin(Wire, SAMPLE_RATE_HZ)) halt("[main] MPU6050 init FAILED - check wiring/pins");
  Serial.printf("[main] MPU6050 OK, WHO_AM_I=0x%02X\n", imu.whoAmI());

  if (!haptic.begin(3.0f)) Serial.println("[main] DRV2605L init FAILED - vibration disabled");
  else Serial.println("[main] DRV2605L OK");

  laptoplink.setDebug(&Serial);
  laptoplink.begin(WIFI_SSID, WIFI_PASS, LAPTOP_PORT, LAPTOP_HOST);

  if (CALIBRATE_ON_BOOT) {
    calibrated = imu.calibrate(CALIBRATION_SAMPLES);
    Serial.println(calibrated ? "[main] boot calibration OK" : "[main] boot calibration FAILED");
  }
}

void loop() {
  laptoplink.update();
  haptic.update();

  bool nowConnected = laptoplink.connected();
  if (nowConnected && !prevLinkConnected) {
    sendCalibrationStatus();
    sendVibrationState(haptic.running(), haptic.running() ? activeIntensity : 0);
  }
  prevLinkConnected = nowConnected;

  // Incoming commands
  char line[LaptopLink::MAX_LINE_LEN];
  if (laptoplink.readLine(line, sizeof(line))) handleCommand(line);

  // Vibration finished by itself (or stopped)
  bool hapRunning = haptic.running();
  if (prevHapticRunning && !hapRunning) sendVibrationState(false, 0);
  prevHapticRunning = hapRunning;

  // Calibration on request
  if (calibrateRequested) {
    calibrateRequested = false;
    runCalibration();
    return;
  }

  // 200 Hz sensor stream
  if (imu.poll()) {
    const auto &o = imu.orientation(); // degrees: yaw (drifts), pitch, roll
    float lx, ly, lz;
    linearAccel(lx, ly, lz);
    laptoplink.printf("{\"gyroscope\":[%.2f,%.2f,%.2f],\"accelerometer\":[%.4f,%.4f,%.4f]}\n", o.yaw, o.pitch, o.roll, lx, ly, lz);
  }
}
