#pragma once
#include <Arduino.h>
#include <Wire.h>

class TremorHaptic {
public:
  struct Pattern {
    uint8_t  intensity = 60;   // peak intensity, 0-100 %
    uint16_t onMs      = 1000; // burst length
    uint16_t offMs     = 500;  // pause length (0 = continuous)
    uint16_t rampMs    = 100;  // fade in/out inside each burst (0 = square)
    uint32_t totalMs   = 0;    // total run time, 0 = until stop()
  };

  TremorHaptic(TwoWire &wire = Wire, int8_t enPin = -1, uint8_t addr = 0x5A) : _w(wire), _en(enPin), _addr(addr) {}

  // ratedVolts: motor rated voltage (3.0 for this motor). Call after Wire.begin().
  bool begin(float ratedVolts = 3.0f) {
    if (_en >= 0) {
      pinMode(_en, OUTPUT);
      digitalWrite(_en, HIGH);
      delay(5);
    }
    uint8_t status;
    if (!read(REG_STATUS, status)) return false;
    if ((status >> 5) != 7) return false;           // 7 = DRV2605L

    write(REG_MODE, 0x80);                           // device reset
    uint32_t t0 = millis();
    uint8_t mode = 0x80;
    while ((mode & 0x80) && millis() - t0 < 50) {    // wait for reset to clear
      delay(2);
      read(REG_MODE, mode);
    }
    write(REG_MODE, 0x00);                           // leave standby

    write(REG_FEEDBACK, 0x36);                       // bit7 = 0 -> ERM
    write(REG_CONTROL3, 0xA8);                       // ERM open loop, RTP unsigned
    write(REG_LIBRARY, 1);                           // ERM library (for effects)

    // Voltage registers: ~20.58 mV/LSB (rated), ~21.96 mV/LSB (overdrive clamp)
    write(REG_RATED_V, constrain((int)(ratedVolts / 0.02058f), 0, 255));
    write(REG_OD_CLAMP, constrain((int)(ratedVolts / 0.02196f), 0, 255));

    write(REG_MODE, MODE_RTP);                       // real-time playback
    write(REG_RTP, 0);
    _ready = true;
    return true;
  }

  // Continuous vibration, 0-100 % (the "dimmer switch").
  void setIntensity(uint8_t pct) {
    if (!_ready) return;
    uint8_t v = (uint8_t)((min<uint8_t>(pct, 100) * 255UL) / 100);
    if (v != _lastRtp) {
      write(REG_RTP, v);
      _lastRtp = v;
    }
  }

  void start(const Pattern &p) {
    _p = p;
    _p.intensity = min<uint8_t>(_p.intensity, 100);
    if (_p.rampMs > _p.onMs / 2) _p.rampMs = _p.onMs / 2;
    _running = true;
    _burstOn = true;
    _phaseStart = _runStart = millis();
    setIntensity(_p.rampMs ? 0 : _p.intensity);
  }

  void stop() {
    _running = false;
    setIntensity(0);
  }

  bool running() const { return _running; }

  // Call frequently from loop() (or a FreeRTOS task). Non-blocking.
  void update() {
    if (!_running) return;
    uint32_t now = millis();
    if (_p.totalMs && now - _runStart >= _p.totalMs) { stop(); return; }

    uint32_t el = now - _phaseStart;
    if (_burstOn) {
      if (el >= _p.onMs) {
        if (_p.offMs == 0) { _phaseStart = now; el = 0; }   // continuous
        else { _burstOn = false; _phaseStart = now; setIntensity(0); return; }
      }
      float scale = 1.0f;
      if (_p.rampMs) {
        if (el < _p.rampMs) scale = (float)el / _p.rampMs;
        else if (el > _p.onMs - _p.rampMs) scale = (float)(_p.onMs - el) / _p.rampMs;
      }
      setIntensity((uint8_t)(_p.intensity * constrain(scale, 0.0f, 1.0f)));
    } else if (el >= _p.offMs) {
      _burstOn = true;
      _phaseStart = now;
    }
  }

private:
  enum : uint8_t {
    REG_STATUS = 0x00, REG_MODE = 0x01, REG_RTP = 0x02, REG_LIBRARY = 0x03,
    REG_RATED_V = 0x16, REG_OD_CLAMP = 0x17, REG_FEEDBACK = 0x1A, REG_CONTROL3 = 0x1D,
    MODE_RTP = 0x05
  };

  bool write(uint8_t reg, uint8_t val) {
    _w.beginTransmission(_addr);
    _w.write(reg);
    _w.write(val);
    return _w.endTransmission() == 0;
  }
  bool read(uint8_t reg, uint8_t &val) {
    _w.beginTransmission(_addr);
    _w.write(reg);
    if (_w.endTransmission(false) != 0) return false;
    if (_w.requestFrom(_addr, (uint8_t)1) != 1) return false;
    val = _w.read();
    return true;
  }

  TwoWire &_w;
  int8_t _en;
  uint8_t _addr;
  bool _ready = false, _running = false, _burstOn = false;
  uint8_t _lastRtp = 0xFF;
  uint32_t _phaseStart = 0, _runStart = 0;
  Pattern _p;
};