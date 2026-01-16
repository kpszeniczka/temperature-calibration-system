import logging
from typing import Dict, List
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QLabel, QPushButton, QProgressBar,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QStatusBar, QSplitter, QFrame,
                             QTextEdit)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

logger = logging.getLogger(__name__)


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4):
        self.fig = Figure(figsize=(width, height), dpi=100)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.channel_lines = {}
        self.furnace_line = None
        self.colors = {
            'A0': '#2196F3',
            'B0': '#4CAF50',
            'B1': '#FF9800',
            'B2': '#9C27B0',
            'B3': '#F44336',
            'B4': '#00BCD4',
            'furnace': '#795548'
        }
        
        self._init_plot()

    def _init_plot(self):
        self.axes.set_xlabel('Czas [s]')
        self.axes.set_ylabel('Temperatura [°C]')
        self.axes.set_title('Przebieg temperatur')
        self.axes.grid(True, alpha=0.3)
        self.fig.tight_layout()

    def update_plot(self, data: Dict):
        self.axes.clear()
        self._init_plot()
        
        for channel, channel_data in data.get('channels', {}).items():
            times = channel_data.get('times', [])
            temps = channel_data.get('temps', [])
            if times and temps:
                if len(times) > 1:
                    times = [t - times[0] for t in times]
                color = self.colors.get(channel, '#000000')
                self.axes.plot(times, temps, label=channel, color=color, linewidth=1.5)
        
        furnace_data = data.get('furnace', {})
        furnace_times = furnace_data.get('times', [])
        furnace_temps = furnace_data.get('temps', [])
        if furnace_times and furnace_temps:
            if len(furnace_times) > 1:
                furnace_times = [t - furnace_times[0] for t in furnace_times]
            self.axes.plot(furnace_times, furnace_temps, label='Piec', 
                          color=self.colors['furnace'], linewidth=2, linestyle='--')
        
        if data.get('channels') or furnace_data:
            self.axes.legend(loc='upper right', fontsize=8)
        
        self.draw()


class CalibrationWindow(QMainWindow):
    closed = pyqtSignal()
    
    def __init__(self, engine, config: dict):
        super().__init__()
        self.engine = engine
        self.config = config
        
        self.setWindowTitle("Wzorcowanie w toku")
        self.setMinimumSize(1200, 800)
        
        self._init_ui()
        self._connect_signals()
        self._init_timer()
        
        QTimer.singleShot(500, self._start_calibration)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._create_status_group())
        top_layout.addWidget(self._create_current_values_group())
        main_layout.addLayout(top_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_plot_group())
        splitter.addWidget(self._create_results_group())
        splitter.setSizes([700, 500])
        main_layout.addWidget(splitter)
        
        main_layout.addWidget(self._create_control_group())
        
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Inicjalizacja...")

    def _create_status_group(self) -> QGroupBox:
        group = QGroupBox("Status wzorcowania")
        layout = QVBoxLayout()
        
        self.point_label = QLabel("Punkt: 0/0")
        self.point_label.setFont(QFont('Arial', 14, QFont.Bold))
        layout.addWidget(self.point_label)
        
        self.target_label = QLabel("Temperatura zadana: -- °C")
        layout.addWidget(self.target_label)
        
        self.stability_label = QLabel("Stabilizacja: --")
        layout.addWidget(self.stability_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.channel_label = QLabel("Aktywny kanał: --")
        layout.addWidget(self.channel_label)
        
        group.setLayout(layout)
        return group

    def _create_current_values_group(self) -> QGroupBox:
        group = QGroupBox("Aktualne odczyty")
        layout = QVBoxLayout()
        
        self.value_labels: Dict[str, QLabel] = {}
        
        furnace_layout = QHBoxLayout()
        furnace_layout.addWidget(QLabel("Piec PV:"))
        self.furnace_pv_label = QLabel("-- °C")
        self.furnace_pv_label.setFont(QFont('Arial', 12, QFont.Bold))
        furnace_layout.addWidget(self.furnace_pv_label)
        furnace_layout.addWidget(QLabel("SP:"))
        self.furnace_sp_label = QLabel("-- °C")
        furnace_layout.addWidget(self.furnace_sp_label)
        layout.addLayout(furnace_layout)
        
        layout.addWidget(QLabel("Temperatury kanałów:"))
        
        for channel in self.config.get('channels', []):
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(f"{channel}:"))
            value_label = QLabel("-- °C")
            value_label.setFont(QFont('Arial', 11))
            self.value_labels[channel] = value_label
            row_layout.addWidget(value_label)
            row_layout.addStretch()
            layout.addLayout(row_layout)
        
        group.setLayout(layout)
        return group

    def _create_plot_group(self) -> QGroupBox:
        group = QGroupBox("Wykres temperatur")
        layout = QVBoxLayout()
        
        self.plot_canvas = PlotCanvas(self, width=8, height=5)
        layout.addWidget(self.plot_canvas)
        
        group.setLayout(layout)
        return group

    def _create_results_group(self) -> QGroupBox:
        group = QGroupBox("Wyniki")
        layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Kanał", "T zadana", "T śr.", "Błąd", "U(k=2)", "Klasa"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.results_table)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        group.setLayout(layout)
        return group

    def _create_control_group(self) -> QGroupBox:
        group = QGroupBox("Sterowanie")
        layout = QHBoxLayout()
        
        self.pause_btn = QPushButton("PAUZA")
        self.pause_btn.setMinimumWidth(120)
        self.pause_btn.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("ZATRZYMAJ")
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self._stop_calibration)
        layout.addWidget(self.stop_btn)
        
        layout.addStretch()
        
        self.report_btn = QPushButton("Generuj raport")
        self.report_btn.setEnabled(False)
        self.report_btn.clicked.connect(self._generate_report)
        layout.addWidget(self.report_btn)
        
        self.close_btn = QPushButton("Zamknij")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)
        
        group.setLayout(layout)
        return group

    def _connect_signals(self):
        self.engine.measurement_taken.connect(self._on_measurement)
        self.engine.channel_changed.connect(self._on_channel_changed)
        self.engine.stability_changed.connect(self._on_stability_changed)
        self.engine.point_completed.connect(self._on_point_completed)
        self.engine.calibration_completed.connect(self._on_calibration_completed)
        self.engine.error_occurred.connect(self._on_error)
        self.engine.status_updated.connect(self._on_status_updated)

    def _init_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(1000)

    def _start_calibration(self):
        self.engine.start_calibration()
        self._log("RozpoczÄ™to wzorcowanie")
        self.statusbar.showMessage("Wzorcowanie w toku")

    def _update_display(self):
        plot_data = self.engine.get_plot_data()
        self.plot_canvas.update_plot(plot_data)
        
        for channel, value in self.engine.last_channel_values.items():
            if channel in self.value_labels:
                self.value_labels[channel].setText(f"{value:.3f} °C")
        
        status = self.engine.get_current_status()
        if status.get('furnace_pv') is not None:
            self.furnace_pv_label.setText(f"{status['furnace_pv']:.2f} °C")
        if status.get('furnace_sp') is not None:
            self.furnace_sp_label.setText(f"{status['furnace_sp']:.1f} °C")

    def _on_measurement(self, channel: str, temp: float, ref_temp: float):
        if channel in self.value_labels:
            self.value_labels[channel].setText(f"{temp:.3f} °C")

    def _on_channel_changed(self, channel: str):
        self.channel_label.setText(f"Aktywny kanał: {channel}")

    def _on_stability_changed(self, is_stable: bool, message: str):
        self.stability_label.setText(f"Stabilizacja: {message}")
        if is_stable:
            self.stability_label.setStyleSheet("color: green;")
        else:
            self.stability_label.setStyleSheet("color: orange;")

    def _on_point_completed(self, point_idx: int, target_temp: float, results: Dict):
        total_points = len(self.config.get('calibration_points', []))
        self.point_label.setText(f"Punkt: {point_idx + 1}/{total_points}")
        self.target_label.setText(f"Temperatura zadana: {target_temp:.1f} °C")
        
        progress = int((point_idx + 1) / total_points * 100) if total_points > 0 else 0
        self.progress_bar.setValue(progress)
        
        self._add_results_to_table(results)
        self._log(f"Punkt {point_idx + 1} ({target_temp:.1f}°C) zakończony")

    def _add_results_to_table(self, results: Dict):
        for channel, data in results.items():
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            
            self.results_table.setItem(row, 0, QTableWidgetItem(channel))
            self.results_table.setItem(row, 1, QTableWidgetItem(f"{data['point_temperature']:.1f}"))
            self.results_table.setItem(row, 2, QTableWidgetItem(f"{data['avg_measured_temp']:.3f}"))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{data['error']:+.3f}"))
            self.results_table.setItem(row, 4, QTableWidgetItem(f"±{data['expanded_uncertainty']:.3f}"))
            self.results_table.setItem(row, 5, QTableWidgetItem(data['sensor_class']))
            
            if not data.get('is_compliant', True):
                for col in range(6):
                    item = self.results_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200))

    def _on_calibration_completed(self, results: Dict):
        self.progress_bar.setValue(100)
        self.stability_label.setText("ZAKOŃCZONO")
        self.stability_label.setStyleSheet("color: blue; font-weight: bold;")
        
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.report_btn.setEnabled(True)
        
        self._log("Wzorcowanie zakończone pomyślnie")
        self.statusbar.showMessage("Wzorcowanie zakończone")
        
        QMessageBox.information(self, "Zakończono", 
            "Wzorcowanie zostało zakończone.\nMożesz wygenerować raport.")

    def _on_error(self, error_msg: str):
        self._log(f"BŁĄD: {error_msg}")
        self.statusbar.showMessage(f"Błąd: {error_msg}")

    def _on_status_updated(self, status: Dict):
        if status.get('current_point') is not None:
            total = status.get('total_points', 0)
            current = status.get('current_point', 0)
            self.point_label.setText(f"Punkt: {current}/{total}")
        
        if status.get('current_target') is not None:
            self.target_label.setText(f"Temperatura zadana: {status['current_target']:.1f} °C")

    def _toggle_pause(self):
        if self.engine.is_paused:
            self.engine.resume_calibration()
            self.pause_btn.setText("PAUZA")
            self._log("Wznowiono wzorcowanie")
        else:
            self.engine.pause_calibration()
            self.pause_btn.setText("WZNÓW")
            self._log("Wstrzymano wzorcowanie")

    def _stop_calibration(self):
        reply = QMessageBox.question(self, "Potwierdzenie",
            "Czy na pewno zatrzymać wzorcowanie?",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.engine.stop_calibration()
            self._log("Wzorcowanie zatrzymane przez użytkownika")
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.report_btn.setEnabled(True)

    def _generate_report(self):
        if self.engine.database and self.engine.session_id:
            try:
                from data.report_generator import generate_calibration_certificate
                session_data = self.engine.database.get_full_session_data(self.engine.session_id)
                report_path = generate_calibration_certificate(session_data)
                self._log(f"Raport zapisany: {report_path}")
                QMessageBox.information(self, "Raport", f"Raport został zapisany:\n{report_path}")
            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie udało się wygenerować raportu:\n{e}")
        else:
            QMessageBox.warning(self, "Błąd", "Brak danych do wygenerowania raportu.")

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        if self.engine.is_running:
            reply = QMessageBox.question(self, "Potwierdzenie",
                "Wzorcowanie jest w toku. Czy na pewno zamknąć?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.engine.stop_calibration()
        
        self.update_timer.stop()
        self.closed.emit()
        event.accept()
