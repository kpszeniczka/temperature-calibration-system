import time
import random
import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class FurnaceSimulator:
    def __init__(self, initial_temp: float = 25.0):
        self.current_temperature = initial_temp
        self.setpoint = initial_temp
        self.heating_rate = 2.0
        self.cooling_rate = 0.5
        self.last_update = time.time()
        self.noise_amplitude = 0.05
        self.overshoot_factor = 0.02
        self._overshoot_active = False
        self._overshoot_peak = 0.0

    def _update_temperature(self):
        now = time.time()
        dt = now - self.last_update
        self.last_update = now

        if dt > 10:
            dt = 0.1

        diff = self.setpoint - self.current_temperature
        
        if abs(diff) < 0.1:
            if self._overshoot_active:
                recovery_rate = 0.3
                overshoot_diff = self._overshoot_peak - self.current_temperature
                if abs(overshoot_diff) > 0.05:
                    self.current_temperature += recovery_rate * dt * (-1 if overshoot_diff < 0 else 1)
                else:
                    self._overshoot_active = False
            self.current_temperature += random.gauss(0, self.noise_amplitude * 0.5)
        elif diff > 0:
            rate = self.heating_rate * (1 - math.exp(-abs(diff) / 50))
            self.current_temperature += rate * dt
            if self.current_temperature > self.setpoint:
                self._overshoot_active = True
                self._overshoot_peak = self.setpoint + self.overshoot_factor * self.setpoint
                self.current_temperature = min(self.current_temperature, self._overshoot_peak)
        else:
            rate = self.cooling_rate * (1 - math.exp(-abs(diff) / 30))
            self.current_temperature -= rate * dt
            if self.current_temperature < self.setpoint:
                self._overshoot_active = True
                self._overshoot_peak = self.setpoint - self.overshoot_factor * abs(self.setpoint - 25)
                self.current_temperature = max(self.current_temperature, self._overshoot_peak)

        self.current_temperature += random.gauss(0, self.noise_amplitude)

    def read_temperature(self) -> float:
        self._update_temperature()
        return round(self.current_temperature, 3)

    def set_setpoint(self, temperature: float):
        self.setpoint = temperature
        self._overshoot_active = False
        logger.debug(f"Furnace simulator setpoint: {temperature}°C")

    def get_status(self) -> Dict:
        self._update_temperature()
        return {
            "pv": self.current_temperature,
            "sp": self.setpoint,
            "heating": self.current_temperature < self.setpoint - 0.5,
            "cooling": self.current_temperature > self.setpoint + 0.5,
            "stable": abs(self.current_temperature - self.setpoint) < 0.5
        }


class CropicoSimulator:
    def __init__(self):
        self.furnace_temp = 25.0
        self.channel_offsets = {
            "A0": 0.0,
            "B0": random.uniform(-0.05, 0.05),
            "B1": random.uniform(-0.1, 0.1),
            "B2": random.uniform(-0.15, 0.15),
            "B3": random.uniform(-0.2, 0.2),
            "B4": random.uniform(-0.3, 0.3),
        }
        self.channel_temps = {ch: 25.0 for ch in self.channel_offsets}
        self.thermal_time_constant = 5.0
        self.noise_amplitude = 0.01
        self.last_update = time.time()
        self.faulty_channel = None

    def set_furnace_temperature(self, temp: float):
        self.furnace_temp = temp

    def set_faulty_channel(self, channel: str):
        self.faulty_channel = channel
        logger.warning(f"Simulator: Channel {channel} set as faulty")

    def _update_channel_temps(self):
        now = time.time()
        dt = now - self.last_update
        self.last_update = now

        if dt > 10:
            dt = 0.1

        for channel in self.channel_temps:
            target = self.furnace_temp + self.channel_offsets[channel]
            diff = target - self.channel_temps[channel]
            tau = self.thermal_time_constant
            self.channel_temps[channel] += diff * (1 - math.exp(-dt / tau))
            self.channel_temps[channel] += random.gauss(0, self.noise_amplitude)

    def read_temperature(self, channel: str) -> float:
        self._update_channel_temps()

        if channel == self.faulty_channel:
            return float('inf')

        if channel in self.channel_temps:
            return round(self.channel_temps[channel], 4)
        return 0.0

    def get_raw_value(self, channel: str) -> float:
        temp = self.read_temperature(channel)
        if temp == float('inf'):
            return 9999.999
        r0 = 100.0
        alpha = 0.00385
        resistance = r0 * (1 + alpha * temp)
        resistance += random.gauss(0, 0.001)
        return round(resistance, 4)

    def get_all_temperatures(self) -> Dict[str, float]:
        self._update_channel_temps()
        return {ch: round(t, 4) for ch, t in self.channel_temps.items()
                if ch != self.faulty_channel}


class DeviceFactory:
    @staticmethod
    def create_cropico(use_simulator: bool = False):
        from devices.cropico import CropicoDevice
        return CropicoDevice(use_simulator=use_simulator)

    @staticmethod
    def create_furnace(use_simulator: bool = False):
        from devices.furnace import PegasusFurnace
        return PegasusFurnace(use_simulator=use_simulator)
