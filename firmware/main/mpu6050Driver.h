#pragma once
#include <Arduino.h>
#include <Wire.h>

class MPU6050Driver {
public:
  enum class AccelRange : uint8_t { G2 = 0, G4 = 1, G8 = 2, G16 = 3 };
  enum class GyroRange  : uint8_t { DPS250 = 0, DPS500 = 1, DPS1000 = 2, DPS2000 = 3 };

  struct Vec3 { float x = 0, y = 0, z = 0; };
  struct Orientation { float yaw = 0, pitch = 0, roll = 0; };

  explicit MPU6050Driver(uint8_t addr = 0x68) : _addr(addr) {}

  // Call Wire.begin(SDA, SCL) before this.
  bool begin(TwoWire &wire = Wire,
             uint16_t rateHz = 200,
             AccelRange ar = AccelRange::G4,
             GyroRange gr = GyroRange::DPS500,
             uint32_t i2cClock = 400000) {
    _wire = &wire;
    _wire->setClock(i2cClock);

    if (!writeReg(REG_PWR_MGMT_1, 0x80)) return false;   // device reset
    delay(100);
    if (!writeReg(REG_PWR_MGMT_1, 0x01)) return false;
    delay(10);

    // DLPF ~44 Hz accel / 42 Hz gyro, gyro output rate becomes 1 kHz
    if (!writeReg(REG_CONFIG, 0x03)) return false;

    // Sample rate = 1000 / (1 + div)
    if (rateHz < 4) rateHz = 4;
    if (rateHz > 1000) rateHz = 1000;
    uint8_t div = (uint8_t)constrain(1000 / rateHz - 1, 0, 255);
    if (!writeReg(REG_SMPLRT_DIV, div)) return false;
    _periodUs = 1000000UL / rateHz;

    setAccelRange(ar);
    setGyroRange(gr);

    uint8_t id = 0;
    if (!readRegs(REG_WHO_AM_I, &id, 1)) return false;
    _whoAmI = id;

    _initialized = true;
    _nextTickUs = micros() + _periodUs;
    _lastUpdateUs = 0;
    return true;
  }

  uint8_t whoAmI() const { return _whoAmI; }

  bool setAccelRange(AccelRange r) {
    static const float lsb[] = {16384.0f, 8192.0f, 4096.0f, 2048.0f};
    _accelLsb = lsb[(uint8_t)r];
    return writeReg(REG_ACCEL_CONFIG, (uint8_t)r << 3);
  }

  bool setGyroRange(GyroRange r) {
    static const float lsb[] = {131.0f, 65.5f, 32.8f, 16.4f};
    _gyroLsb = lsb[(uint8_t)r];
    return writeReg(REG_GYRO_CONFIG, (uint8_t)r << 3);
  }

  /**
   * Non-blocking poll. Returns true (and updates data) when a new sample
   * period has elapsed. Call it from loop(); it costs almost nothing when it's not time yet.
   */
  bool poll() {
    if (!_initialized) return false;
    uint32_t now = micros();
    if ((int32_t)(now - _nextTickUs) < 0) return false;

    _nextTickUs += _periodUs;
    // If fell far behind (e.g. long blocking call), resync instead of bursting
    if ((int32_t)(now - _nextTickUs) > (int32_t)(_periodUs * 4)) _nextTickUs = now + _periodUs;

    return update();
  }

  // Force a read + filter update right now (ignores the 200 Hz pacing).
  bool update() {
    Vec3 a, g;
    if (!readScaled(a, g, _temperature)) return false;

    _accel = {a.x - _accelOffset.x, a.y - _accelOffset.y, a.z - _accelOffset.z};
    _gyro  = {g.x - _gyroOffset.x,  g.y - _gyroOffset.y,  g.z - _gyroOffset.z};

    uint32_t now = micros();
    float dt = _lastUpdateUs == 0 ? _periodUs * 1e-6f : (now - _lastUpdateUs) * 1e-6f;
    _lastUpdateUs = now;
    if (dt <= 0 || dt > 0.1f) dt = _periodUs * 1e-6f;

    // Accel-derived angles
    float accRoll  = atan2f(_accel.y, _accel.z) * RAD2DEG;
    float accPitch = atan2f(-_accel.x, sqrtf(_accel.y * _accel.y + _accel.z * _accel.z)) * RAD2DEG;

    if (!_orientSeeded) {
      _orient.roll = accRoll;
      _orient.pitch = accPitch;
      _orient.yaw = 0;
      _orientSeeded = true;
    } else {
      _orient.roll  = _alpha * (_orient.roll  + _gyro.x * dt) + (1.0f - _alpha) * accRoll;
      _orient.pitch = _alpha * (_orient.pitch + _gyro.y * dt) + (1.0f - _alpha) * accPitch;
      _orient.yaw  += _gyro.z * dt;               // no magnetometer -> drifts over time
      _orient.yaw = wrap180(_orient.yaw);
    }
    return true;
  }

  /**
   * Blocking calibration (~samples / rate seconds; 500 samples ~ 2.5 s at 200 Hz).
   * Keep the board still and flat (Z axis pointing up).
   */
  bool calibrate(uint16_t samples = 500, float motionThresholdDps = 3.0f) {
    if (!_initialized || samples == 0) return false;

    double sa[3] = {0, 0, 0}, sg[3] = {0, 0, 0};
    float gmin[3] = { 1e9f,  1e9f,  1e9f};
    float gmax[3] = {-1e9f, -1e9f, -1e9f};

    uint32_t next = micros();
    for (uint16_t i = 0; i < samples; i++) {
      while ((int32_t)(micros() - next) < 0) { /* wait for next tick */ }
      next += _periodUs;

      Vec3 a, g; float t;
      if (!readScaled(a, g, t)) return false;

      sa[0] += a.x; sa[1] += a.y; sa[2] += a.z;
      sg[0] += g.x; sg[1] += g.y; sg[2] += g.z;
      float gv[3] = {g.x, g.y, g.z};
      for (int k = 0; k < 3; k++) {
        if (gv[k] < gmin[k]) gmin[k] = gv[k];
        if (gv[k] > gmax[k]) gmax[k] = gv[k];
      }
    }

    for (int k = 0; k < 3; k++) {
      if ((gmax[k] - gmin[k]) > motionThresholdDps) return false;  // moved during calibration
    }

    float n = (float)samples;
    _gyroOffset  = {(float)(sg[0] / n), (float)(sg[1] / n), (float)(sg[2] / n)};
    _accelOffset = {(float)(sa[0] / n), (float)(sa[1] / n), (float)(sa[2] / n) - 1.0f};

    // Restart orientation estimate from the now-clean readings
    _orientSeeded = false;
    _lastUpdateUs = 0;
    return true;
  }

  // Offsets can be saved (e.g. in NVS/Preferences) and restored at boot to skip calibration.
  void setOffsets(const Vec3 &accel, const Vec3 &gyro) { _accelOffset = accel; _gyroOffset = gyro; }
  Vec3 accelOffset() const { return _accelOffset; }
  Vec3 gyroOffset()  const { return _gyroOffset; }

  // Complementary filter weight on gyro (0..1). Higher = trust gyro more.
  void setFilterAlpha(float a) { _alpha = constrain(a, 0.0f, 1.0f); }
  void resetYaw() { _orient.yaw = 0; }

  const Vec3 &accel() const { return _accel; }            
  const Vec3 &gyro() const { return _gyro; }              
  const Orientation &orientation() const { return _orient; }
  float temperatureC() const { return _temperature; }

private:
  static constexpr uint8_t REG_SMPLRT_DIV = 0x19;
  static constexpr uint8_t REG_CONFIG = 0x1A;
  static constexpr uint8_t REG_GYRO_CONFIG = 0x1B;
  static constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
  static constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
  static constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
  static constexpr uint8_t REG_WHO_AM_I = 0x75;
  static constexpr float RAD2DEG = 57.29577951f;

  bool writeReg(uint8_t reg, uint8_t val) {
    _wire->beginTransmission(_addr);
    _wire->write(reg);
    _wire->write(val);
    return _wire->endTransmission() == 0;
  }

  bool readRegs(uint8_t reg, uint8_t *buf, size_t len) {
    _wire->beginTransmission(_addr);
    _wire->write(reg);
    if (_wire->endTransmission(false) != 0) return false;   // repeated start
    if (_wire->requestFrom(_addr, (uint8_t)len) != len) return false;
    for (size_t i = 0; i < len; i++) buf[i] = _wire->read();
    return true;
  }

  // One 14-byte burst: accel(6) temp(2) gyro(6). Offsets NOT applied.
  bool readScaled(Vec3 &a, Vec3 &g, float &tempC) {
    uint8_t b[14];
    if (!readRegs(REG_ACCEL_XOUT_H, b, 14)) return false;
    auto s16 = [&](int i) { return (int16_t)((b[i] << 8) | b[i + 1]); };

    a = {s16(0) / _accelLsb, s16(2) / _accelLsb, s16(4) / _accelLsb};
    tempC = s16(6) / 340.0f + 36.53f;
    g = {s16(8) / _gyroLsb, s16(10) / _gyroLsb, s16(12) / _gyroLsb};
    return true;
  }

  static float wrap180(float a) {
    while (a > 180.0f) a -= 360.0f;
    while (a < -180.0f) a += 360.0f;
    return a;
  }

  TwoWire *_wire = &Wire;
  uint8_t _addr;
  uint8_t _whoAmI = 0;
  bool _initialized = false;

  float _accelLsb = 8192.0f, _gyroLsb = 65.5f;
  uint32_t _periodUs = 5000, _nextTickUs = 0, _lastUpdateUs = 0;

  Vec3 _accel, _gyro, _accelOffset, _gyroOffset;
  Orientation _orient;
  float _temperature = 0;
  float _alpha = 0.98f;
  bool _orientSeeded = false;
};
