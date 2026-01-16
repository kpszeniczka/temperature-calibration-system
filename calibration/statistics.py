import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class StatisticsCalculator:
    @staticmethod
    def calculate_mean(values: List[float]) -> float:
        if not values:
            return 0.0
        return float(np.mean(values))

    @staticmethod
    def calculate_std(values: List[float], ddof: int = 1) -> float:
        if len(values) < 2:
            return 0.0
        return float(np.std(values, ddof=ddof))

    @staticmethod
    def calculate_std_of_mean(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        std = np.std(values, ddof=1)
        return float(std / np.sqrt(len(values)))

    @staticmethod
    def calculate_min_max(values: List[float]) -> Tuple[float, float]:
        if not values:
            return 0.0, 0.0
        return float(np.min(values)), float(np.max(values))

    @staticmethod
    def calculate_range(values: List[float]) -> float:
        if not values:
            return 0.0
        return float(np.max(values) - np.min(values))

    @staticmethod
    def remove_outliers(values: List[float], n_sigma: float = 3.0) -> List[float]:
        if len(values) < 3:
            return values
        arr = np.array(values)
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        if std == 0:
            return values
        mask = np.abs(arr - mean) <= n_sigma * std
        return arr[mask].tolist()

    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float, float]:
        if len(x) != len(y) or len(x) < 2:
            return 0.0, 0.0, 0.0
        x_arr = np.array(x)
        y_arr = np.array(y)
        coeffs = np.polyfit(x_arr, y_arr, 1)
        slope = float(coeffs[0])
        intercept = float(coeffs[1])
        y_pred = slope * x_arr + intercept
        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        return slope, intercept, float(r_squared)


class CalibrationPointStatistics:
    def __init__(self, channel: str, point_temperature: float):
        self.channel = channel
        self.point_temperature = point_temperature
        self.measured_temps: List[float] = []
        self.reference_temps: List[float] = []
        self.raw_values: List[float] = []
        self.timestamps: List[float] = []

    def add_measurement(self, measured: float, reference: float, 
                       raw_value: float = 0.0, timestamp: float = 0.0):
        self.measured_temps.append(measured)
        self.reference_temps.append(reference)
        self.raw_values.append(raw_value)
        self.timestamps.append(timestamp)

    def calculate_statistics(self) -> Dict:
        calc = StatisticsCalculator()
        
        n = len(self.measured_temps)
        if n == 0:
            return {}

        avg_measured = calc.calculate_mean(self.measured_temps)
        avg_reference = calc.calculate_mean(self.reference_temps)
        avg_raw = calc.calculate_mean(self.raw_values)
        
        std_measured = calc.calculate_std(self.measured_temps)
        std_reference = calc.calculate_std(self.reference_temps)
        
        errors = [m - r for m, r in zip(self.measured_temps, self.reference_temps)]
        avg_error = calc.calculate_mean(errors)
        max_abs_error = max(abs(e) for e in errors) if errors else 0.0
        
        return {
            "channel": self.channel,
            "point_temperature": self.point_temperature,
            "n_measurements": n,
            "avg_measured_temp": avg_measured,
            "avg_reference_temp": avg_reference,
            "avg_raw_value": avg_raw,
            "std_dev_measured": std_measured,
            "std_dev_reference": std_reference,
            "avg_error": avg_error,
            "max_absolute_error": max_abs_error,
            "min_measured": min(self.measured_temps),
            "max_measured": max(self.measured_temps),
        }


class SessionStatistics:
    def __init__(self):
        self.point_stats: Dict[str, Dict[float, CalibrationPointStatistics]] = {}

    def add_point_statistics(self, channel: str, point_temp: float, 
                            stats: CalibrationPointStatistics):
        if channel not in self.point_stats:
            self.point_stats[channel] = {}
        self.point_stats[channel][point_temp] = stats

    def get_channel_summary(self, channel: str) -> Dict:
        if channel not in self.point_stats:
            return {}
        
        points = self.point_stats[channel]
        all_errors = []
        all_stds = []
        
        for point_temp, stats in points.items():
            result = stats.calculate_statistics()
            if result:
                all_errors.append(result.get("avg_error", 0))
                all_stds.append(result.get("std_dev_measured", 0))
        
        return {
            "channel": channel,
            "n_points": len(points),
            "temperatures": sorted(points.keys()),
            "mean_error": np.mean(all_errors) if all_errors else 0,
            "max_error": max(abs(e) for e in all_errors) if all_errors else 0,
            "mean_std": np.mean(all_stds) if all_stds else 0,
        }

    def get_full_report(self) -> Dict:
        report = {
            "channels": {},
            "summary": {}
        }
        
        for channel in self.point_stats:
            report["channels"][channel] = {}
            for point_temp, stats in self.point_stats[channel].items():
                report["channels"][channel][point_temp] = stats.calculate_statistics()
            report["summary"][channel] = self.get_channel_summary(channel)
        
        return report
