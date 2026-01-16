import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class CalibrationDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DATABASE_PATH)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibration_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                operator TEXT,
                client TEXT,
                order_number TEXT,
                ambient_temperature REAL,
                relative_humidity REAL,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_info (
                sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                channel INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                sensor_type TEXT,
                manufacturer TEXT,
                serial_number TEXT,
                description TEXT,
                FOREIGN KEY (session_id) REFERENCES calibration_sessions(session_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS measurements (
                measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                channel INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                measured_temperature REAL NOT NULL,
                reference_temperature REAL NOT NULL,
                furnace_pv REAL,
                furnace_sp REAL,
                raw_value REAL,
                absolute_error REAL,
                calibration_point REAL,
                FOREIGN KEY (session_id) REFERENCES calibration_sessions(session_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibration_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                channel INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                point_temperature REAL NOT NULL,
                avg_measured_temp REAL,
                avg_reference_temp REAL,
                avg_raw_value REAL,
                std_dev REAL,
                max_absolute_error REAL,
                standard_uncertainty REAL,
                expanded_uncertainty REAL,
                sensor_class TEXT,
                is_compliant INTEGER,
                FOREIGN KEY (session_id) REFERENCES calibration_sessions(session_id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_measurements_session 
            ON measurements(session_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_session 
            ON calibration_results(session_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sensor_session 
            ON sensor_info(session_id)
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def create_session(self, operator: str, client: str = "", 
                      order_number: str = "", ambient_temperature: float = None,
                      relative_humidity: float = None, notes: str = "") -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO calibration_sessions 
            (start_time, operator, client, order_number, ambient_temperature, 
             relative_humidity, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), operator, client, order_number,
              ambient_temperature, relative_humidity, notes))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created session {session_id} for operator {operator}")
        return session_id

    def update_session_end_time(self, session_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE calibration_sessions 
            SET end_time = ? 
            WHERE session_id = ?
        ''', (datetime.now().isoformat(), session_id))
        
        conn.commit()
        conn.close()

    def add_sensor_info(self, session_id: int, channel: int, channel_name: str,
                       sensor_type: str = "", manufacturer: str = "",
                       serial_number: str = "", description: str = ""):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sensor_info 
            (session_id, channel, channel_name, sensor_type, manufacturer, 
             serial_number, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, channel, channel_name, sensor_type, manufacturer,
              serial_number, description))
        
        conn.commit()
        conn.close()

    def add_measurement(self, session_id: int, channel: int, channel_name: str,
                       measured_temperature: float, reference_temperature: float,
                       furnace_pv: float = None, furnace_sp: float = None,
                       raw_value: float = None, absolute_error: float = None,
                       calibration_point: float = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO measurements 
            (session_id, timestamp, channel, channel_name, measured_temperature,
             reference_temperature, furnace_pv, furnace_sp, raw_value, 
             absolute_error, calibration_point)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, datetime.now().timestamp(), channel, channel_name,
              measured_temperature, reference_temperature, furnace_pv, furnace_sp,
              raw_value, absolute_error, calibration_point))
        
        conn.commit()
        conn.close()

    def add_calibration_result(self, session_id: int, channel: int, channel_name: str,
                              point_temperature: float, avg_measured_temp: float,
                              avg_reference_temp: float, avg_raw_value: float,
                              std_dev: float, max_absolute_error: float,
                              standard_uncertainty: float, expanded_uncertainty: float,
                              sensor_class: str, is_compliant: bool):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO calibration_results 
            (session_id, channel, channel_name, point_temperature, avg_measured_temp,
             avg_reference_temp, avg_raw_value, std_dev, max_absolute_error,
             standard_uncertainty, expanded_uncertainty, sensor_class, is_compliant)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, channel, channel_name, point_temperature, avg_measured_temp,
              avg_reference_temp, avg_raw_value, std_dev, max_absolute_error,
              standard_uncertainty, expanded_uncertainty, sensor_class,
              1 if is_compliant else 0))
        
        conn.commit()
        conn.close()

    def get_session(self, session_id: int) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM calibration_sessions WHERE session_id = ?
        ''', (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None

    def get_all_sessions(self, limit: int = 100) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM calibration_sessions 
            ORDER BY start_time DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_session_measurements(self, session_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM measurements 
            WHERE session_id = ? 
            ORDER BY timestamp
        ''', (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_session_results(self, session_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM calibration_results 
            WHERE session_id = ? 
            ORDER BY channel, point_temperature
        ''', (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_session_sensors(self, session_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM sensor_info WHERE session_id = ?
        ''', (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_full_session_data(self, session_id: int) -> Dict:
        return {
            "session": self.get_session(session_id),
            "sensors": self.get_session_sensors(session_id),
            "measurements": self.get_session_measurements(session_id),
            "results": self.get_session_results(session_id)
        }

    def delete_session(self, session_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM measurements WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM calibration_results WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM sensor_info WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM calibration_sessions WHERE session_id = ?', (session_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"Deleted session {session_id}")

    def export_session_to_dict(self, session_id: int) -> Dict:
        data = self.get_full_session_data(session_id)
        
        for m in data.get("measurements", []):
            if "timestamp" in m:
                m["timestamp_iso"] = datetime.fromtimestamp(m["timestamp"]).isoformat()
        
        return data
