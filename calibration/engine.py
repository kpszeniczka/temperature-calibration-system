import time
import threading
import logging
from typing import List, Dict, Optional, Callable, Tuple
from collections import defaultdict, deque
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from config import (CALIBRATION_CHANNELS, REFERENCE_CHANNEL, STABILITY_TOLERANCE,
                    STABILITY_TIME_SECONDS, THERMAL_EQUILIBRIUM_THRESHOLD,
                    CHANNEL_SWITCH_DELAY, MEASUREMENTS_PER_POINT, PARKING_TEMPERATURE,
                    MAX_STDDEV_THRESHOLD, USE_SIMULATORS)
from devices.simulators import DeviceFactory
from calibration.statistics import CalibrationPointStatistics, SessionStatistics, StatisticsCalculator
from calibration.uncertainty import create_uncertainty_calculator, calculate_full_uncertainty

logger = logging.getLogger(__name__)


class CalibrationEngine(QObject):
    measurement_taken = pyqtSignal(str, float, float)
    channel_changed = pyqtSignal(str)
    stability_changed = pyqtSignal(bool, str)
    point_completed = pyqtSignal(int, float, dict)
    calibration_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    status_updated = pyqtSignal(dict)

    def __init__(self, use_simulators: bool = None):
        super().__init__()
        
        if use_simulators is None:
            use_simulators = USE_SIMULATORS
        
        self.use_simulators = use_simulators
        self.cropico = DeviceFactory.create_cropico(use_simulators)
        self.furnace = DeviceFactory.create_furnace(use_simulators)
        
        self.database = None
        self.logger = None
        
        self.session_id: Optional[int] = None
        self.is_running = False
        self.is_paused = False
        self._stop_requested = False
        
        self.active_channels: List[str] = [REFERENCE_CHANNEL]
        self.channel_sensor_types: Dict[str, str] = {}
        self.calibration_points: List[float] = []
        self.current_point_index = 0
        self.current_channel_index = 0
        
        self.channel_readings: Dict[str, List[float]] = defaultdict(list)
        self.reference_readings: List[float] = []
        self.last_channel_values: Dict[str, float] = {}
        
        self.temp_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.time_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.furnace_history: deque = deque(maxlen=1000)
        self.furnace_time_history: deque = deque(maxlen=1000)
        
        self.session_stats = SessionStatistics()
        self.point_stats: Dict[str, CalibrationPointStatistics] = {}
        
        self._stability_start_time: Optional[float] = None
        self._last_switch_time: float = 0
        
        self._worker_thread: Optional[threading.Thread] = None

    def set_database(self, database):
        self.database = database

    def set_logger(self, data_logger):
        self.logger = data_logger

    def connect_devices(self, cropico_port: int, furnace_port: int) -> Tuple[bool, bool]:
        cropico_ok = self.cropico.connect(cropico_port)
        furnace_ok = self.furnace.connect(furnace_port)
        
        if self.use_simulators and cropico_ok and furnace_ok:
            self.cropico.simulator.furnace_temp = self.furnace.simulator.current_temperature
        
        return cropico_ok, furnace_ok

    def disconnect_devices(self):
        self.cropico.disconnect()
        self.furnace.disconnect()

    def configure_channels(self, channels: List[str], sensor_types: Dict[str, str]):
        self.active_channels = channels.copy()
        self.channel_sensor_types = sensor_types.copy()
        
        if REFERENCE_CHANNEL not in self.active_channels:
            self.active_channels.insert(0, REFERENCE_CHANNEL)
        
        for channel in self.active_channels:
            sensor_type = self.channel_sensor_types.get(channel, "PT100")
            self.cropico.configure_channel(channel, sensor_type)

    def set_calibration_points(self, points: List[float]):
        self.calibration_points = sorted(points)
        logger.info(f"Calibration points set: {self.calibration_points}")

    def start_session(self, operator: str, client: str = "", 
                     order_number: str = "", ambient_temp: float = None,
                     humidity: float = None, notes: str = "") -> Optional[int]:
        if self.database:
            self.session_id = self.database.create_session(
                operator=operator,
                client=client,
                order_number=order_number,
                ambient_temperature=ambient_temp,
                relative_humidity=humidity,
                notes=notes
            )
            logger.info(f"Session started with ID: {self.session_id}")
        return self.session_id

    def start_calibration(self):
        if self.is_running:
            logger.warning("Calibration already running")
            return
        
        self.is_running = True
        self.is_paused = False
        self._stop_requested = False
        self.current_point_index = 0
        self.current_channel_index = 0
        
        self.channel_readings.clear()
        self.reference_readings.clear()
        self.session_stats = SessionStatistics()
        self.point_stats.clear()
        
        self._worker_thread = threading.Thread(target=self._calibration_worker, daemon=True)
        self._worker_thread.start()
        logger.info("Calibration started")

    def stop_calibration(self):
        self._stop_requested = True
        self.is_running = False
        logger.info("Calibration stop requested")

    def pause_calibration(self):
        self.is_paused = True
        logger.info("Calibration paused")

    def resume_calibration(self):
        self.is_paused = False
        logger.info("Calibration resumed")

    def _calibration_worker(self):
        try:
            for point_idx, target_temp in enumerate(self.calibration_points):
                if self._stop_requested:
                    break
                
                self.current_point_index = point_idx
                logger.info(f"Starting point {point_idx + 1}/{len(self.calibration_points)}: {target_temp}°C")
                
                self.furnace.set_setpoint(target_temp)
                
                if self.use_simulators:
                    self.cropico.simulator.set_furnace_temperature(target_temp)
                
                if not self._wait_for_stability(target_temp):
                    if self._stop_requested:
                        break
                    continue
                
                for channel in self.active_channels:
                    if channel not in self.point_stats:
                        self.point_stats[channel] = {}
                    self.point_stats[channel] = CalibrationPointStatistics(channel, target_temp)
                
                point_results = self._measure_point(target_temp)
                
                if point_results:
                    self.point_completed.emit(point_idx, target_temp, point_results)
                    self._save_point_results(point_idx, target_temp, point_results)
            
            if not self._stop_requested:
                self.furnace.set_setpoint(PARKING_TEMPERATURE)
                self._finalize_session()
            
        except Exception as e:
            logger.exception(f"Calibration worker error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.is_running = False

    def _wait_for_stability(self, target_temp: float) -> bool:
        self._stability_start_time = None
        stable_count = 0
        
        while not self._stop_requested:
            while self.is_paused and not self._stop_requested:
                time.sleep(0.5)
            
            success, furnace_pv = self.furnace.read_temperature()
            if not success:
                time.sleep(1)
                continue
            
            self._update_furnace_history(furnace_pv)
            
            if self.use_simulators:
                self.cropico.simulator.set_furnace_temperature(furnace_pv)
            
            diff = abs(furnace_pv - target_temp)
            is_stable = diff <= STABILITY_TOLERANCE
            
            if is_stable:
                if self._stability_start_time is None:
                    self._stability_start_time = time.time()
                    stable_count = 0
                
                stable_count += 1
                elapsed = time.time() - self._stability_start_time
                
                self.stability_changed.emit(True, 
                    f"Stabilizacja: {elapsed:.0f}/{STABILITY_TIME_SECONDS}s")
                
                if elapsed >= STABILITY_TIME_SECONDS:
                    if self._check_thermal_equilibrium():
                        logger.info(f"Stability achieved at {target_temp}°C")
                        return True
                    else:
                        self.stability_changed.emit(False, "Oczekiwanie na równowagę termiczną")
            else:
                self._stability_start_time = None
                stable_count = 0
                self.stability_changed.emit(False, 
                    f"Różnica: {diff:.2f}°C (cel: <{STABILITY_TOLERANCE}°C)")
            
            self._update_status()
            time.sleep(1)
        
        return False

    def _check_thermal_equilibrium(self) -> bool:
        if len(self.active_channels) < 2:
            return True
        
        temps = {}
        for channel in self.active_channels:
            sensor_type = self.channel_sensor_types.get(channel, "PT100")
            self.cropico.configure_channel(channel, sensor_type)
            time.sleep(0.5)
            success, temp = self.cropico.read_temperature()
            if success and temp != float('inf'):
                temps[channel] = temp
                self.last_channel_values[channel] = temp
        
        if len(temps) < 2:
            return True
        
        temp_values = list(temps.values())
        max_diff = max(temp_values) - min(temp_values)
        
        return max_diff <= THERMAL_EQUILIBRIUM_THRESHOLD

    def _measure_point(self, target_temp: float) -> Dict:
        self.channel_readings.clear()
        self.reference_readings.clear()
        
        for measurement_num in range(MEASUREMENTS_PER_POINT):
            if self._stop_requested:
                break
            
            while self.is_paused and not self._stop_requested:
                time.sleep(0.5)
            
            for channel_idx, channel in enumerate(self.active_channels):
                if self._stop_requested:
                    break
                
                sensor_type = self.channel_sensor_types.get(channel, "PT100")
                self.cropico.configure_channel(channel, sensor_type)
                self.channel_changed.emit(channel)
                
                time.sleep(CHANNEL_SWITCH_DELAY)
                
                success, temp = self.cropico.read_temperature()
                success_raw, raw_value = self.cropico.get_raw_value()
                
                if success and temp != float('inf'):
                    self.channel_readings[channel].append(temp)
                    self.last_channel_values[channel] = temp
                    
                    self._update_temp_history(channel, temp)
                    
                    ref_temp = self.last_channel_values.get(REFERENCE_CHANNEL, target_temp)
                    if channel == REFERENCE_CHANNEL:
                        self.reference_readings.append(temp)
                        ref_temp = temp
                    
                    self.measurement_taken.emit(channel, temp, ref_temp)
                    
                    if channel in self.point_stats:
                        self.point_stats[channel].add_measurement(
                            temp, ref_temp, 
                            raw_value if success_raw else 0,
                            time.time()
                        )
                    
                    self._save_measurement(channel, temp, ref_temp, raw_value if success_raw else 0, target_temp)
                else:
                    logger.warning(f"Failed to read channel {channel}")
            
            self._update_status()
        
        return self._calculate_point_results(target_temp)

    def _calculate_point_results(self, target_temp: float) -> Dict:
        calc = StatisticsCalculator()
        results = {}
        
        ref_temps = self.channel_readings.get(REFERENCE_CHANNEL, [])
        ref_mean = calc.calculate_mean(ref_temps) if ref_temps else target_temp
        
        for channel in self.active_channels:
            temps = self.channel_readings.get(channel, [])
            if not temps:
                continue
            
            mean_temp = calc.calculate_mean(temps)
            std_dev = calc.calculate_std(temps)
            error = mean_temp - ref_mean
            
            sensor_type = self.channel_sensor_types.get(channel, "PT100")
            uncertainty = calculate_full_uncertainty(
                std_dev, len(temps), target_temp, sensor_type
            )
            
            unc_calc = create_uncertainty_calculator(sensor_type)
            sensor_class = unc_calc.classify_sensor(abs(error), target_temp)
            
            results[channel] = {
                "channel": channel,
                "point_temperature": target_temp,
                "avg_measured_temp": mean_temp,
                "avg_reference_temp": ref_mean,
                "std_dev": std_dev,
                "n_measurements": len(temps),
                "error": error,
                "max_absolute_error": max(abs(t - ref_mean) for t in temps),
                "standard_uncertainty": uncertainty["combined"],
                "expanded_uncertainty": uncertainty["expanded"],
                "sensor_class": sensor_class,
                "is_compliant": sensor_class not in ["Poza klasą", ""]
            }
            
            if channel in self.point_stats:
                self.session_stats.add_point_statistics(channel, target_temp, self.point_stats[channel])
        
        return results

    def _save_measurement(self, channel: str, measured: float, reference: float, 
                         raw_value: float, calibration_point: float):
        if self.database and self.session_id:
            success, furnace_pv = self.furnace.read_temperature()
            success_sp, furnace_sp = self.furnace.read_setpoint()
            
            self.database.add_measurement(
                session_id=self.session_id,
                channel=self.active_channels.index(channel),
                channel_name=channel,
                measured_temperature=measured,
                reference_temperature=reference,
                furnace_pv=furnace_pv if success else 0,
                furnace_sp=furnace_sp if success_sp else 0,
                raw_value=raw_value,
                absolute_error=measured - reference,
                calibration_point=calibration_point
            )
        
        if self.logger:
            self.logger.log_measurement(
                channel=channel,
                measured=measured,
                reference=reference,
                error=measured - reference
            )

    def _save_point_results(self, point_idx: int, target_temp: float, results: Dict):
        if self.database and self.session_id:
            for channel, data in results.items():
                self.database.add_calibration_result(
                    session_id=self.session_id,
                    channel=self.active_channels.index(channel),
                    channel_name=channel,
                    point_temperature=target_temp,
                    avg_measured_temp=data["avg_measured_temp"],
                    avg_reference_temp=data["avg_reference_temp"],
                    avg_raw_value=0,
                    std_dev=data["std_dev"],
                    max_absolute_error=data["max_absolute_error"],
                    standard_uncertainty=data["standard_uncertainty"],
                    expanded_uncertainty=data["expanded_uncertainty"],
                    sensor_class=data["sensor_class"],
                    is_compliant=data["is_compliant"]
                )

    def _finalize_session(self):
        if self.database and self.session_id:
            self.database.update_session_end_time(self.session_id)
        
        full_results = self.session_stats.get_full_report()
        self.calibration_completed.emit(full_results)
        logger.info("Calibration session completed")

    def _update_temp_history(self, channel: str, temp: float):
        now = time.time()
        self.temp_history[channel].append(temp)
        self.time_history[channel].append(now)

    def _update_furnace_history(self, temp: float):
        now = time.time()
        self.furnace_history.append(temp)
        self.furnace_time_history.append(now)

    def _update_status(self):
        success, furnace_pv = self.furnace.read_temperature()
        success_sp, furnace_sp = self.furnace.read_setpoint()
        
        status = {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_point": self.current_point_index + 1,
            "total_points": len(self.calibration_points),
            "current_target": self.calibration_points[self.current_point_index] if self.calibration_points else 0,
            "furnace_pv": furnace_pv if success else None,
            "furnace_sp": furnace_sp if success_sp else None,
            "current_channel": self.active_channels[self.current_channel_index] if self.active_channels else None,
            "last_values": dict(self.last_channel_values)
        }
        self.status_updated.emit(status)

    def get_current_status(self) -> Dict:
        success, furnace_pv = self.furnace.read_temperature()
        success_sp, furnace_sp = self.furnace.read_setpoint()
        
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "session_id": self.session_id,
            "current_point_index": self.current_point_index,
            "total_points": len(self.calibration_points),
            "current_target": self.calibration_points[self.current_point_index] if self.calibration_points else None,
            "furnace_pv": furnace_pv if success else None,
            "furnace_sp": furnace_sp if success_sp else None,
            "active_channels": self.active_channels,
            "last_channel_values": dict(self.last_channel_values)
        }

    def get_plot_data(self) -> Dict:
        return {
            "channels": {
                ch: {
                    "times": list(self.time_history[ch]),
                    "temps": list(self.temp_history[ch])
                }
                for ch in self.active_channels
            },
            "furnace": {
                "times": list(self.furnace_time_history),
                "temps": list(self.furnace_history)
            }
        }

    def read_current_channel(self) -> Dict:
        channel = self.active_channels[self.current_channel_index] if self.active_channels else None
        if channel:
            success, temp = self.cropico.read_temperature()
            if success:
                return {
                    "channel": channel,
                    "temperature": temp,
                    "timestamp": datetime.now().isoformat()
                }
        return {}


from typing import Tuple
