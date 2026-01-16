import os
from pathlib import Path

USE_SIMULATORS = True

CROPICO_BAUDRATE = 9600
CROPICO_BYTESIZE = 8
CROPICO_PARITY = 'N'
CROPICO_STOPBITS = 1
CROPICO_TIMEOUT = None
CROPICO_READ_TIMEOUT_MS = 3000

FURNACE_BAUDRATE = 9600
FURNACE_BYTESIZE = 8
FURNACE_PARITY = 'N'
FURNACE_STOPBITS = 1
FURNACE_TIMEOUT = 1.0
FURNACE_SLAVE_ID = 0x01

FURNACE_PV_ADDRESS = 0x8002
FURNACE_SP_ADDRESS = 0x8004

MODBUS_READ_HOLDING = 0x03
MODBUS_WRITE_MULTIPLE = 0x10

CALIBRATION_CHANNELS = ["A0", "B0", "B1", "B2", "B3", "B4"]
REFERENCE_CHANNEL = "A0"
MAX_CALIBRATION_POINTS = 10

DEFAULT_CALIBRATION_POINTS = [50.0, 100.0, 150.0, 200.0, 250.0]
PARKING_TEMPERATURE = 30.0

STABILITY_TOLERANCE = 0.5
STABILITY_TIME_SECONDS = 60
THERMAL_EQUILIBRIUM_THRESHOLD = 0.3
CHANNEL_SWITCH_DELAY = 10
MEASUREMENTS_PER_POINT = 10
MAX_STDDEV_THRESHOLD = 0.05

REFERENCE_UNCERTAINTY = 0.01
RESOLUTION_UNCERTAINTY = 0.001
STABILITY_UNCERTAINTY = 0.02
HOMOGENEITY_UNCERTAINTY = 0.05
DRIFT_UNCERTAINTY = 0.01

PT100_CLASS_AA_TOLERANCE = lambda t: 0.1 + 0.0017 * abs(t)
PT100_CLASS_A_TOLERANCE = lambda t: 0.15 + 0.002 * abs(t)
PT100_CLASS_B_TOLERANCE = lambda t: 0.3 + 0.005 * abs(t)
PT100_CLASS_C_TOLERANCE = lambda t: 0.6 + 0.01 * abs(t)

TC_K_CLASS_1_TOLERANCE = lambda t: max(1.5, 0.004 * abs(t))
TC_K_CLASS_2_TOLERANCE = lambda t: max(2.5, 0.0075 * abs(t))
TC_S_CLASS_1_TOLERANCE = lambda t: max(1.0, 0.003 * (t - 1100)) if t > 1100 else 1.0

DATA_DIR = Path("calibration_data")
DATA_DIR.mkdir(exist_ok=True)
DATABASE_PATH = DATA_DIR / "calibration.db"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

ENABLE_API = True
API_HOST = "0.0.0.0"
API_PORT = 8000
WEBSOCKET_UPDATE_INTERVAL = 2.0

SENSOR_TYPES = {
    "PT100": {"description": "Platynowy czujnik rezystancyjny PT100", "standard": "IEC 60751"},
    "TC_K": {"description": "Termopara typu K (NiCr-NiAl)", "standard": "IEC 60584"},
    "TC_S": {"description": "Termopara typu S (PtRh10-Pt)", "standard": "IEC 60584"},
    "TC_J": {"description": "Termopara typu J (Fe-CuNi)", "standard": "IEC 60584"},
    "TC_T": {"description": "Termopara typu T (Cu-CuNi)", "standard": "IEC 60584"},
    "TC_N": {"description": "Termopara typu N (NiCrSi-NiSi)", "standard": "IEC 60584"},
    "TC_R": {"description": "Termopara typu R (PtRh13-Pt)", "standard": "IEC 60584"},
    "TC_B": {"description": "Termopara typu B (PtRh30-PtRh6)", "standard": "IEC 60584"},
}