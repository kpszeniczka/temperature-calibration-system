import serial
import serial.tools.list_ports
import logging
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

logger = logging.getLogger(__name__)


class PortScannerThread(QThread):
    port_found = pyqtSignal(dict)
    scan_complete = pyqtSignal()
    progress_update = pyqtSignal(int, int)

    def __init__(self, port_range=(1, 20)):
        super().__init__()
        self.port_range = port_range
        self._stop_requested = False

    def run(self):
        total = self.port_range[1] - self.port_range[0] + 1
        
        for i, port_num in enumerate(range(self.port_range[0], self.port_range[1] + 1)):
            if self._stop_requested:
                break
            
            self.progress_update.emit(i + 1, total)
            
            result = self._check_port(port_num)
            if result:
                self.port_found.emit(result)
        
        self.scan_complete.emit()

    def _check_port(self, port_num: int) -> Optional[Dict]:
        port_name = f"COM{port_num}"
        
        try:
            ser = serial.Serial(
                port=port_name,
                baudrate=9600,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=0.5
            )
            
            ser.dtr = True
            ser.rts = True
            
            import time
            time.sleep(0.2)
            
            ser.reset_input_buffer()
            ser.write(b"*IDN?\r\n")
            time.sleep(0.3)
            
            response = ""
            while ser.in_waiting > 0:
                response += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
            
            ser.close()
            
            if "CROPICO" in response.upper():
                return {
                    "port": port_num,
                    "device": "Cropico 3001",
                    "protocol": "SCPI",
                    "id": response.strip()
                }
            
            ser = serial.Serial(
                port=port_name,
                baudrate=9600,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=0.5
            )
            
            import struct
            slave_id = 0x01
            function = 0x03
            address = 0x8002
            count = 2
            
            frame = struct.pack('>BBHH', slave_id, function, address, count)
            crc = 0xFFFF
            for byte in frame:
                crc ^= byte
                for _ in range(8):
                    if crc & 0x0001:
                        crc = (crc >> 1) ^ 0xA001
                    else:
                        crc >>= 1
            frame += struct.pack('<H', crc)
            
            ser.reset_input_buffer()
            ser.write(frame)
            time.sleep(0.2)
            
            response = ser.read(9)
            ser.close()
            
            if len(response) >= 9 and response[0] == slave_id:
                return {
                    "port": port_num,
                    "device": "Pegasus Furnace",
                    "protocol": "Modbus RTU",
                    "id": f"Slave ID: {slave_id}"
                }
            
        except serial.SerialException:
            pass
        except Exception as e:
            logger.debug(f"Error checking COM{port_num}: {e}")
        
        return None

    def stop(self):
        self._stop_requested = True


class PortScannerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Skanowanie portÃ³w COM")
        self.setMinimumSize(500, 400)
        
        self.found_devices: List[Dict] = []
        self.scanner_thread: Optional[PortScannerThread] = None
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Skanowanie portÃ³w COM w poszukiwaniu urzÄ…dzeÅ„...")
        layout.addWidget(info_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Oczekiwanie...")
        layout.addWidget(self.progress_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Port", "UrzÄ…dzenie", "ProtokÃ³Å‚", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        
        self.scan_btn = QPushButton("Skanuj")
        self.scan_btn.clicked.connect(self._start_scan)
        btn_layout.addWidget(self.scan_btn)
        
        self.stop_btn = QPushButton("Zatrzymaj")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_scan)
        btn_layout.addWidget(self.stop_btn)
        
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("Zamknij")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)

    def _start_scan(self):
        self.table.setRowCount(0)
        self.found_devices.clear()
        
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.scanner_thread = PortScannerThread()
        self.scanner_thread.port_found.connect(self._on_port_found)
        self.scanner_thread.scan_complete.connect(self._on_scan_complete)
        self.scanner_thread.progress_update.connect(self._on_progress_update)
        self.scanner_thread.start()

    def _stop_scan(self):
        if self.scanner_thread:
            self.scanner_thread.stop()

    def _on_port_found(self, device: Dict):
        self.found_devices.append(device)
        
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(f"COM{device['port']}"))
        self.table.setItem(row, 1, QTableWidgetItem(device['device']))
        self.table.setItem(row, 2, QTableWidgetItem(device['protocol']))
        self.table.setItem(row, 3, QTableWidgetItem(device.get('id', 'N/A')))

    def _on_scan_complete(self):
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_label.setText(f"ZakoÅ„czono. Znaleziono {len(self.found_devices)} urzÄ…dzeÅ„.")
        self.progress_bar.setValue(100)

    def _on_progress_update(self, current: int, total: int):
        progress = int(current / total * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"Sprawdzanie COM{current}...")

    def get_found_devices(self) -> List[Dict]:
        return self.found_devices

    def closeEvent(self, event):
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self.scanner_thread.wait()
        event.accept()


def scan_ports_simple() -> List[Dict]:
    available_ports = []
    
    ports = serial.tools.list_ports.comports()
    for port in ports:
        available_ports.append({
            "port": port.device,
            "description": port.description,
            "hwid": port.hwid
        })
    
    return available_ports
