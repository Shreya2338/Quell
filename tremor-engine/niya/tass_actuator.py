from typing import Dict, Any

class TASSActuator:
    def __init__(self, min_hz: int = 20, max_hz: int = 250):
        self.min_hz = min_hz
        self.max_hz = max_hz
        self.current_state = 0
        self.current_hz = 0

    def hz_to_percent(self, hz: int) -> float:
        """Converts frequency in Hertz to percentage (0 - 100%) for UI sliders."""
        if hz <= 0:
            return 0.0
        pct = ((hz - self.min_hz) / (self.max_hz - self.min_hz)) * 100.0
        return max(0.0, min(100.0, round(pct, 1)))

    def percent_to_hz(self, pct: float) -> int:
        """Converts percentage (0 - 100%) to Hertz."""
        if pct <= 0:
            return 0
        hz = self.min_hz + (pct / 100.0) * (self.max_hz - self.min_hz)
        return int(round(hz))

    def update_hardware_state(self, actuation_state: int, actuation_intensity: int):
        self.current_state = actuation_state
        self.current_hz = actuation_intensity

    def create_vibration_command(self, length_ms: int, intensity_val: int, is_percent: bool = False) -> Dict[str, int]:
        """Generates outbound vibration payload for hardware."""
        hz_val = self.percent_to_hz(intensity_val) if is_percent else intensity_val
        return {
            "length": int(length_ms),
            "intensity": int(hz_val)
        }

    def create_calibration_command(self) -> Dict[str, bool]:
        """Generates outbound calibration payload for hardware."""
        return {
            "calibrate_now": True
        }
