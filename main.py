import sys
import os
import logging
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config import USE_SIMULATORS, DATA_DIR
from calibration.engine import CalibrationEngine
from data.database import CalibrationDatabase
from data.logger import DataLogger
from gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DATA_DIR / 'application.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def start_api_server(engine):
    try:
        from api.remote_api import set_calibration_engine, run_api_server
        set_calibration_engine(engine)
        run_api_server()
    except ImportError as e:
        logger.warning(f"Could not start API server: {e}")
    except Exception as e:
        logger.error(f"API server error: {e}")


def main():
    logger.info("=" * 60)
    logger.info("Starting Temperature Calibration System")
    logger.info(f"Simulation mode: {USE_SIMULATORS}")
    logger.info("=" * 60)
    
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("System Wzorcowania Czujników Temperatury")
    app.setOrganizationName("AGH KTCiOS")
    app.setOrganizationDomain("agh.edu.pl")
    
    app.setStyle('Fusion')
    
    logger.info("Initializing calibration engine...")
    engine = CalibrationEngine(use_simulators=USE_SIMULATORS)
    
    logger.info("Initializing database...")
    database = CalibrationDatabase()
    engine.set_database(database)
    
    logger.info("Creating main window...")
    window = MainWindow()
    window.set_calibration_engine(engine)
    
    api_enabled = os.environ.get('ENABLE_API', 'true').lower() == 'true'
    if api_enabled:
        logger.info("Starting API server in background thread...")
        api_thread = threading.Thread(target=start_api_server, args=(engine,), daemon=True)
        api_thread.start()
    
    window.show()
    
    logger.info("Application started successfully")
    
    exit_code = app.exec_()
    
    logger.info("Application closing...")
    engine.disconnect_devices()
    
    logger.info("Application closed")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)
