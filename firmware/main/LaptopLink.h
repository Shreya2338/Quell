#pragma once
#include <WiFi.h>
#include <stdarg.h>
#include <stdio.h>

class LaptopLink {
public:
  static const size_t MAX_LINE_LEN = 128;

  // host == nullptr -> use the WiFi gateway IP. Laptop is host
  void begin(const char* ssid, const char* pass, uint16_t port, const char* host = nullptr) {
    _ssid = ssid;
    _pass = pass;
    _port = port;
    _useGateway = (host == nullptr);
    if (!_useGateway) _hostIP.fromString(host);

    if (!_mutex) _mutex = xSemaphoreCreateMutex();

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);          // disable modem sleep: much lower latency
    WiFi.setAutoReconnect(true);
    WiFi.begin(_ssid, _pass);
    _lastWifiTry = millis();
  }

  void update() {
    xSemaphoreTake(_mutex, portMAX_DELAY);
    uint32_t now = millis();

    if (WiFi.status() != WL_CONNECTED) {
      _connected = false;
      if (_wifiUp) {
        _wifiUp = false;
        if (_dbg) _dbg->println("[link] WiFi lost");
      }
      if (_dbg && now - _lastDbg > 2000) {
        _lastDbg = now;
        // 1 = SSID not found, 4 = connect failed (wrong password?), 6 = disconnected
        _dbg->printf("[link] waiting for WiFi, status=%d\n", (int)WiFi.status());
      }
      if (now - _lastWifiTry > WIFI_RETRY_MS) {
        WiFi.disconnect();
        WiFi.begin(_ssid, _pass);
        _lastWifiTry = now;
      }
      xSemaphoreGive(_mutex);
      return;
    }

    if (!_wifiUp) {
      _wifiUp = true;
      if (_dbg) {
        _dbg->printf("[link] WiFi connected. ESP32 IP=%s gateway=%s RSSI=%d dBm\n",
                     WiFi.localIP().toString().c_str(),
                     WiFi.gatewayIP().toString().c_str(), (int)WiFi.RSSI());
      }
    }

    if (!_client.connected()) {
      if (_connected) {            // just dropped
        if (_dbg) _dbg->println("[link] TCP connection lost");
        _client.stop();
        _connected = false;
        _len = 0;
        _lineReady = false;
      }
      if (now - _lastTcpTry > TCP_RETRY_MS) {
        _lastTcpTry = now;
        IPAddress ip = _useGateway ? WiFi.gatewayIP() : _hostIP;
        bool ok = _client.connect(ip, _port, CONNECT_TIMEOUT_MS);
        if (_dbg) {
          _dbg->printf("[link] TCP connect to %s:%u -> %s\n", ip.toString().c_str(),
                       (unsigned)_port, ok ? "OK" : "FAILED");
        }
        if (ok) {
          _client.setNoDelay(true);  // send small packets immediately
          _connected = true;
        }
      }
      xSemaphoreGive(_mutex);
      return;
    }

    while (_client.available() && !_lineReady) {
      int c = _client.read();
      if (c < 0) break;
      if (c == '\r') continue;
      if (c == '\n') {
        _line[_len] = 0;
        _lineReady = true;
      } else if (_len < MAX_LINE_LEN - 1) {
        _line[_len++] = (char)c;
      }
    }
    xSemaphoreGive(_mutex);
  }

  bool connected() const { return _connected; }

  void setDebug(Print* p) { _dbg = p; }

  bool readLine(char* out, size_t outSize) {
    xSemaphoreTake(_mutex, portMAX_DELAY);
    bool ready = _lineReady;
    if (ready) {
      strncpy(out, _line, outSize - 1);
      out[outSize - 1] = 0;
      _len = 0;
      _lineReady = false;
    }
    xSemaphoreGive(_mutex);
    return ready;
  }

  size_t send(const uint8_t* data, size_t len) {
    if (!_connected) return 0;
    xSemaphoreTake(_mutex, portMAX_DELAY);
    size_t n = _client.write(data, len);
    xSemaphoreGive(_mutex);
    return n;
  }

  size_t print(const char* s) { return send((const uint8_t*)s, strlen(s)); }

  size_t println(const char* s) {
    char buf[MAX_LINE_LEN + 2];
    int n = snprintf(buf, sizeof(buf), "%s\n", s);
    return send((const uint8_t*)buf, n > 0 ? (size_t)n : 0);
  }

  size_t printf(const char* fmt, ...) __attribute__((format(printf, 2, 3))) {
    char buf[192];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n < 0) return 0;
    if (n >= (int)sizeof(buf)) n = sizeof(buf) - 1;
    return send((const uint8_t*)buf, (size_t)n);
  }

private:
  static const uint32_t WIFI_RETRY_MS = 8000;
  static const uint32_t TCP_RETRY_MS = 1000;
  static const uint32_t CONNECT_TIMEOUT_MS = 1000;

  const char* _ssid = nullptr;
  const char* _pass = nullptr;
  uint16_t _port = 0;
  bool _useGateway = true;
  IPAddress _hostIP;

  WiFiClient _client;
  SemaphoreHandle_t _mutex = nullptr;
  volatile bool _connected = false;
  bool _wifiUp = false;
  Print* _dbg = nullptr;
  uint32_t _lastDbg = 0;

  char _line[MAX_LINE_LEN];
  size_t _len = 0;
  bool _lineReady = false;

  uint32_t _lastWifiTry = 0;
  uint32_t _lastTcpTry = 0;
};