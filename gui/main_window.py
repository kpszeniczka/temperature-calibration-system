import sys
import logging
from typing import Dict, List, Optional
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QLabel, QPushButton, QLineEdit,
                             QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QStatusBar, QMenuBar, QMenu, QAction,
                             QFileDialog, QDialog, QFormLayout, QDialogButtonBox,
                             QTabWidget, QTextEdit, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from config import (CALIBRATION_CHANNELS, DEFAULT_CALIBRATION_POINTS,
                    SENSOR_TYPES, USE_SIMULATORS, MEASUREMENTS_PER_POINT,
                    STABILITY_TOLERANCE, STABILITY_TIME_SECONDS)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    start_calibration_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Wzorcowania Czujników Temperatury")
        self.setMinimumSize(1000, 700)
        
        self.calibration_engine = None
        self.calibration_window = None
        
        self.channel_checkboxes: Dict[str, QCheckBox] = {}
        self.channel_type_combos: Dict[str, QComboBox] = {}
        self.point_spinboxes: List[QDoubleSpinBox] = []
        
        self._init_ui()
        self._init_menu()
        self._init_statusbar()
        
        self.use_simulators = USE_SIMULATORS
        self._update_simulator_status()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._create_connection_group())
        left_layout.addWidget(self._create_channels_group())
        left_layout.addStretch()
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self._create_points_group())
        right_layout.addWidget(self._create_session_group())
        right_layout.addWidget(self._create_control_group())
        right_layout.addStretch()
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 500])
        
        main_layout.addWidget(splitter)

    def _create_connection_group(self) -> QGroupBox:
        group = QGroupBox("Połączenie z urządzeniami")
        layout = QVBoxLayout()
        
        cropico_layout = QHBoxLayout()
        cropico_layout.addWidget(QLabel("Cropico 3001 - Port COM:"))
        self.cropico_port_spin = QSpinBox()
        self.cropico_port_spin.setRange(1, 20)
        self.cropico_port_spin.setValue(3)
        cropico_layout.addWidget(self.cropico_port_spin)
        self.cropico_status_label = QLabel("●")
        self.cropico_status_label.setStyleSheet("color: gray; font-size: 16px;")
        cropico_layout.addWidget(self.cropico_status_label)
        layout.addLayout(cropico_layout)
        
        furnace_layout = QHBoxLayout()
        furnace_layout.addWidget(QLabel("Piec Pegasus - Port COM:"))
        self.furnace_port_spin = QSpinBox()
        self.furnace_port_spin.setRange(1, 20)
        self.furnace_port_spin.setValue(4)
        furnace_layout.addWidget(self.furnace_port_spin)
        self.furnace_status_label = QLabel("●")
        self.furnace_status_label.setStyleSheet("color: gray; font-size: 16px;")
        furnace_layout.addWidget(self.furnace_status_label)
        layout.addLayout(furnace_layout)
        
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Skanuj porty")
        self.scan_btn.clicked.connect(self._scan_ports)
        btn_layout.addWidget(self.scan_btn)
        
        self.connect_btn = QPushButton("Połącz")
        self.connect_btn.clicked.connect(self._connect_devices)
        btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Rozłącz")
        self.disconnect_btn.clicked.connect(self._disconnect_devices)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group

    def _create_channels_group(self) -> QGroupBox:
        group = QGroupBox("Konfiguracja kanałów")
        layout = QVBoxLayout()
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Kanał"))
        header_layout.addWidget(QLabel("Aktywny"))
        header_layout.addWidget(QLabel("Typ czujnika"))
        layout.addLayout(header_layout)
        
        for channel in CALIBRATION_CHANNELS:
            row_layout = QHBoxLayout()
            
            label = QLabel(channel)
            label.setFixedWidth(40)
            row_layout.addWidget(label)
            
            checkbox = QCheckBox()
            checkbox.setChecked(channel in ["A0", "B0"])
            self.channel_checkboxes[channel] = checkbox
            row_layout.addWidget(checkbox)
            
            combo = QComboBox()
            combo.addItems(list(SENSOR_TYPES.keys()))
            if channel == "A0":
                combo.setCurrentText("PT100")
            self.channel_type_combos[channel] = combo
            row_layout.addWidget(combo)
            
            layout.addLayout(row_layout)
        
        note_label = QLabel("Kanał A0 lub B0 służy jako kanał referencyjny")
        note_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(note_label)
        
        group.setLayout(layout)
        return group

    def _create_points_group(self) -> QGroupBox:
        group = QGroupBox("Punkty wzorcowania [°C]")
        layout = QVBoxLayout()
        
        self.points_table = QTableWidget(10, 1)
        self.points_table.setHorizontalHeaderLabels(["Temperatura [°C]"])
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.points_table.verticalHeader().setVisible(True)
        
        for i, temp in enumerate(DEFAULT_CALIBRATION_POINTS):
            item = QTableWidgetItem(f"{temp:.1f}")
            self.points_table.setItem(i, 0, item)
        
        for i in range(len(DEFAULT_CALIBRATION_POINTS), 10):
            item = QTableWidgetItem("")
            self.points_table.setItem(i, 0, item)
        
        layout.addWidget(self.points_table)
        
        btn_layout = QHBoxLayout()
        sort_btn = QPushButton("Sortuj")
        sort_btn.clicked.connect(self._sort_points)
        btn_layout.addWidget(sort_btn)
        
        clear_btn = QPushButton("Wyczyść")
        clear_btn.clicked.connect(self._clear_points)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group

    def _create_session_group(self) -> QGroupBox:
        group = QGroupBox("Dane sesji")
        layout = QFormLayout()
        
        self.operator_edit = QLineEdit()
        layout.addRow("Operator:", self.operator_edit)
        
        self.client_edit = QLineEdit()
        layout.addRow("Zleceniodawca:", self.client_edit)
        
        self.order_edit = QLineEdit()
        layout.addRow("Nr zlecenia:", self.order_edit)
        
        self.ambient_temp_spin = QDoubleSpinBox()
        self.ambient_temp_spin.setRange(15.0, 30.0)
        self.ambient_temp_spin.setValue(22.0)
        self.ambient_temp_spin.setSuffix(" °C")
        layout.addRow("Temp. otoczenia:", self.ambient_temp_spin)
        
        self.humidity_spin = QDoubleSpinBox()
        self.humidity_spin.setRange(20.0, 80.0)
        self.humidity_spin.setValue(45.0)
        self.humidity_spin.setSuffix(" %")
        layout.addRow("Wilgotność:", self.humidity_spin)
        
        group.setLayout(layout)
        return group

    def _create_control_group(self) -> QGroupBox:
        group = QGroupBox("Sterowanie")
        layout = QVBoxLayout()
        
        self.start_btn = QPushButton("ROZPOCZNIJ WZORCOWANIE")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_btn.clicked.connect(self._start_calibration)
        layout.addWidget(self.start_btn)
        
        group.setLayout(layout)
        return group

    def _init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("Plik")
        
        load_action = QAction("Wczytaj konfigurację...", self)
        load_action.triggered.connect(self._load_config)
        file_menu.addAction(load_action)
        
        save_action = QAction("Zapisz konfigurację...", self)
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Zakończ", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        sim_menu = menubar.addMenu("Symulacja")
        
        self.sim_action = QAction("Tryb symulacji", self, checkable=True)
        self.sim_action.setChecked(USE_SIMULATORS)
        self.sim_action.triggered.connect(self._toggle_simulation)
        sim_menu.addAction(self.sim_action)
        
        history_menu = menubar.addMenu("Historia")
        
        view_sessions = QAction("Przeglądaj sesje...", self)
        view_sessions.triggered.connect(self._view_sessions)
        history_menu.addAction(view_sessions)
        
        help_menu = menubar.addMenu("Pomoc")
        
        about_action = QAction("O programie", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.sim_status_label = QLabel()
        self.statusbar.addPermanentWidget(self.sim_status_label)
        
        self.statusbar.showMessage("Gotowy")

    def set_calibration_engine(self, engine):
        self.calibration_engine = engine

    def _scan_ports(self):
        self.statusbar.showMessage("Skanowanie portów...")
        QMessageBox.information(self, "Skanowanie", 
            "Funkcja skanowania portów.\nW trybie symulacji użyj dowolnych numerów portów.")
        self.statusbar.showMessage("Gotowy")

    def _connect_devices(self):
        if self.calibration_engine is None:
            QMessageBox.warning(self, "Błąd", "Silnik wzorcowania nie został zainicjalizowany.")
            return
        
        cropico_port = self.cropico_port_spin.value()
        furnace_port = self.furnace_port_spin.value()
        
        self.statusbar.showMessage("Łączenie z urządzeniami...")
        
        cropico_ok, furnace_ok = self.calibration_engine.connect_devices(cropico_port, furnace_port)
        
        if cropico_ok:
            self.cropico_status_label.setStyleSheet("color: green; font-size: 16px;")
        else:
            self.cropico_status_label.setStyleSheet("color: red; font-size: 16px;")
        
        if furnace_ok:
            self.furnace_status_label.setStyleSheet("color: green; font-size: 16px;")
        else:
            self.furnace_status_label.setStyleSheet("color: red; font-size: 16px;")
        
        if cropico_ok and furnace_ok:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.statusbar.showMessage("Połączono z urządzeniami")
        else:
            msg = []
            if not cropico_ok:
                msg.append("Cropico 3001")
            if not furnace_ok:
                msg.append("Piec Pegasus")
            QMessageBox.warning(self, "Błąd połączenia", 
                f"Nie udało się połączyć z: {', '.join(msg)}")
            self.statusbar.showMessage("Błąd połączenia")

    def _disconnect_devices(self):
        if self.calibration_engine:
            self.calibration_engine.disconnect_devices()
        
        self.cropico_status_label.setStyleSheet("color: gray; font-size: 16px;")
        self.furnace_status_label.setStyleSheet("color: gray; font-size: 16px;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.statusbar.showMessage("Rozłączono")

    def _sort_points(self):
        points = self._get_calibration_points()
        points.sort()
        for i, temp in enumerate(points):
            self.points_table.item(i, 0).setText(f"{temp:.1f}")
        for i in range(len(points), 10):
            self.points_table.item(i, 0).setText("")

    def _clear_points(self):
        for i in range(10):
            self.points_table.item(i, 0).setText("")

    def _get_calibration_points(self) -> List[float]:
        points = []
        for i in range(10):
            item = self.points_table.item(i, 0)
            if item and item.text().strip():
                try:
                    temp = float(item.text().replace(",", "."))
                    if temp > 0:
                        points.append(temp)
                except ValueError:
                    pass
        return points

    def _get_active_channels(self) -> List[str]:
        return [ch for ch, cb in self.channel_checkboxes.items() if cb.isChecked()]

    def _get_sensor_types(self) -> Dict[str, str]:
        return {ch: combo.currentText() 
                for ch, combo in self.channel_type_combos.items()}

    def _start_calibration(self):
        if self.calibration_engine is None:
            QMessageBox.warning(self, "Błąd", "Silnik wzorcowania nie został zainicjalizowany.")
            return
        
        if not self.calibration_engine.cropico.connected:
            reply = QMessageBox.question(self, "Brak połączenia",
                "Urządzenia nie są połączone. Czy połączyć teraz?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._connect_devices()
            else:
                return
        
        points = self._get_calibration_points()
        if not points:
            QMessageBox.warning(self, "Błąd", "Nie zdefiniowano punktów wzorcowania.")
            return
        
        channels = self._get_active_channels()
        if len(channels) < 2:
            QMessageBox.warning(self, "Błąd", 
                "Wybierz co najmniej 2 kanały (referencyjny + wzorcowany).")
            return
        
        if not self.operator_edit.text().strip():
            QMessageBox.warning(self, "Błąd", "Podaj nazwisko operatora.")
            return
        
        config = {
            'operator': self.operator_edit.text().strip(),
            'client': self.client_edit.text().strip(),
            'order_number': self.order_edit.text().strip(),
            'ambient_temperature': self.ambient_temp_spin.value(),
            'relative_humidity': self.humidity_spin.value(),
            'channels': channels,
            'sensor_types': self._get_sensor_types(),
            'calibration_points': sorted(points)
        }
        
        self._open_calibration_window(config)

    def _open_calibration_window(self, config: dict):
        from gui.calibration_window import CalibrationWindow
        
        self.calibration_engine.configure_channels(config['channels'], config['sensor_types'])
        self.calibration_engine.set_calibration_points(config['calibration_points'])
        
        self.calibration_engine.start_session(
            operator=config['operator'],
            client=config['client'],
            order_number=config['order_number'],
            ambient_temp=config['ambient_temperature'],
            humidity=config['relative_humidity']
        )
        
        self.calibration_window = CalibrationWindow(self.calibration_engine, config)
        self.calibration_window.closed.connect(self._on_calibration_window_closed)
        self.calibration_window.show()
        self.hide()

    def _on_calibration_window_closed(self):
        self.show()
        self.statusbar.showMessage("Wzorcowanie zakończone")

    def _toggle_simulation(self, checked):
        self.use_simulators = checked
        self._update_simulator_status()
        
        if self.calibration_engine:
            QMessageBox.information(self, "Zmiana trybu",
                "Zmiana trybu wymaga ponownego uruchomienia aplikacji.")

    def _update_simulator_status(self):
        if self.use_simulators:
            self.sim_status_label.setText("SYMULACJA")
            self.sim_status_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.sim_status_label.setText("SPRZĘT")
            self.sim_status_label.setStyleSheet("color: green; font-weight: bold;")

    def _load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Wczytaj konfigurację",
                                                   "", "JSON (*.json)")
        if filename:
            self.statusbar.showMessage(f"Wczytano: {filename}")

    def _save_config(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Zapisz konfigurację",
                                                   "", "JSON (*.json)")
        if filename:
            self.statusbar.showMessage(f"Zapisano: {filename}")

    def _view_sessions(self):
        QMessageBox.information(self, "Historia sesji", 
            "Funkcja przeglądania historycznych sesji wzorcowania.")

    def _show_about(self):
        QMessageBox.about(self, "O programie",
            "<h3>System Wzorcowania Czujników Temperatury</h3>"
            "<p>Wersja 1.0</p>"
            "<p>Projekt inżynierski AGH</p>"
            "<p>Katedra Techniki Cieplnej i Ochrony Środowiska</p>")

    def closeEvent(self, event):
        if self.calibration_engine and self.calibration_engine.is_running:
            reply = QMessageBox.question(self, "Potwierdzenie",
                "Wzorcowanie jest w toku. Czy na pewno zakończyć?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.calibration_engine.stop_calibration()
        
        self._disconnect_devices()
        event.accept()
