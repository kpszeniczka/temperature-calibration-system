import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from config import LOG_DIR

logger = logging.getLogger(__name__)


class DataLogger:
    def __init__(self, session_name: str = None):
        self.log_dir = Path(LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if session_name:
            base_name = f"{session_name}_{timestamp}"
        else:
            base_name = f"calibration_{timestamp}"
        
        self.detailed_log_path = self.log_dir / f"{base_name}_detailed.csv"
        self.summary_log_path = self.log_dir / f"{base_name}_summary.csv"
        
        self._init_detailed_log()
        self._init_summary_log()
        
        self.measurement_count = 0
        logger.info(f"Data logger initialized: {self.detailed_log_path}")

    def _init_detailed_log(self):
        with open(self.detailed_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                'Timestamp',
                'Event',
                'Channel',
                'Measured_Temp_C',
                'Reference_Temp_C',
                'Error_C',
                'Furnace_PV_C',
                'Furnace_SP_C',
                'Raw_Value',
                'Calibration_Point_C',
                'Notes'
            ])

    def _init_summary_log(self):
        with open(self.summary_log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                'Channel',
                'Point_Temperature_C',
                'Avg_Measured_C',
                'Avg_Reference_C',
                'Std_Dev_C',
                'Max_Error_C',
                'Uncertainty_C',
                'Sensor_Class',
                'N_Measurements'
            ])

    def log_measurement(self, channel: str, measured: float, reference: float,
                       error: float = None, furnace_pv: float = None,
                       furnace_sp: float = None, raw_value: float = None,
                       calibration_point: float = None, notes: str = ""):
        if error is None:
            error = measured - reference
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        with open(self.detailed_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                timestamp,
                'MEASUREMENT',
                channel,
                f"{measured:.4f}",
                f"{reference:.4f}",
                f"{error:.4f}",
                f"{furnace_pv:.2f}" if furnace_pv is not None else "",
                f"{furnace_sp:.2f}" if furnace_sp is not None else "",
                f"{raw_value:.4f}" if raw_value is not None else "",
                f"{calibration_point:.1f}" if calibration_point is not None else "",
                notes
            ])
        
        self.measurement_count += 1

    def log_event(self, event: str, channel: str = "", notes: str = ""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        with open(self.detailed_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                timestamp,
                event,
                channel,
                "", "", "", "", "", "", "",
                notes
            ])

    def log_channel_switch(self, new_channel: str):
        self.log_event('CHANNEL_SWITCH', new_channel)

    def log_stability_achieved(self, temperature: float):
        self.log_event('STABILITY_ACHIEVED', notes=f"Temperature: {temperature:.2f}°C")

    def log_point_start(self, point_index: int, temperature: float):
        self.log_event('POINT_START', notes=f"Point {point_index + 1}: {temperature:.1f}°C")

    def log_point_complete(self, point_index: int, temperature: float):
        self.log_event('POINT_COMPLETE', notes=f"Point {point_index + 1}: {temperature:.1f}°C")

    def log_error(self, error_message: str, channel: str = ""):
        self.log_event('ERROR', channel, error_message)

    def log_summary_result(self, channel: str, point_temperature: float,
                          avg_measured: float, avg_reference: float,
                          std_dev: float, max_error: float,
                          uncertainty: float, sensor_class: str,
                          n_measurements: int):
        with open(self.summary_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                channel,
                f"{point_temperature:.1f}",
                f"{avg_measured:.4f}",
                f"{avg_reference:.4f}",
                f"{std_dev:.4f}",
                f"{max_error:.4f}",
                f"{uncertainty:.4f}",
                sensor_class,
                n_measurements
            ])

    def log_session_header(self, session_info: Dict):
        self.log_event('SESSION_START', 
                      notes=f"Operator: {session_info.get('operator', 'N/A')}, "
                            f"Client: {session_info.get('client', 'N/A')}, "
                            f"Order: {session_info.get('order_number', 'N/A')}")
        
        if session_info.get('ambient_temperature'):
            self.log_event('ENVIRONMENT',
                          notes=f"Ambient: {session_info['ambient_temperature']:.1f}°C, "
                                f"Humidity: {session_info.get('relative_humidity', 'N/A')}%")

    def log_session_end(self):
        self.log_event('SESSION_END', notes=f"Total measurements: {self.measurement_count}")

    def get_log_paths(self) -> Dict[str, str]:
        return {
            "detailed": str(self.detailed_log_path),
            "summary": str(self.summary_log_path)
        }


def read_csv_log(file_path: str) -> List[Dict]:
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            data.append(dict(row))
    return data
