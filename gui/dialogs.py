from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QLineEdit, QDoubleSpinBox, QComboBox,
                             QPushButton, QDialogButtonBox, QGroupBox,
                             QTextEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt
from typing import Dict, List, Optional
from config import SENSOR_TYPES


class SensorInfoDialog(QDialog):
    def __init__(self, channel: str, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setWindowTitle(f"Informacje o czujniku - {channel}")
        self.setMinimumWidth(400)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(SENSOR_TYPES.keys()))
        form_layout.addRow("Typ czujnika:", self.type_combo)
        
        self.manufacturer_edit = QLineEdit()
        form_layout.addRow("Producent:", self.manufacturer_edit)
        
        self.serial_edit = QLineEdit()
        form_layout.addRow("Nr fabryczny:", self.serial_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Opis:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_sensor_info(self) -> Dict:
        return {
            "channel": self.channel,
            "sensor_type": self.type_combo.currentText(),
            "manufacturer": self.manufacturer_edit.text(),
            "serial_number": self.serial_edit.text(),
            "description": self.description_edit.toPlainText()
        }

    def set_sensor_info(self, info: Dict):
        if info.get("sensor_type"):
            index = self.type_combo.findText(info["sensor_type"])
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        self.manufacturer_edit.setText(info.get("manufacturer", ""))
        self.serial_edit.setText(info.get("serial_number", ""))
        self.description_edit.setText(info.get("description", ""))


class SessionInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informacje o sesji wzorcowania")
        self.setMinimumWidth(450)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.operator_edit = QLineEdit()
        form_layout.addRow("Operator:", self.operator_edit)
        
        self.client_edit = QLineEdit()
        form_layout.addRow("Zleceniodawca:", self.client_edit)
        
        self.order_edit = QLineEdit()
        form_layout.addRow("Nr zlecenia:", self.order_edit)
        
        self.ambient_spin = QDoubleSpinBox()
        self.ambient_spin.setRange(15.0, 35.0)
        self.ambient_spin.setValue(22.0)
        self.ambient_spin.setSuffix(" °C")
        form_layout.addRow("Temperatura otoczenia:", self.ambient_spin)
        
        self.humidity_spin = QDoubleSpinBox()
        self.humidity_spin.setRange(20.0, 80.0)
        self.humidity_spin.setValue(45.0)
        self.humidity_spin.setSuffix(" %")
        form_layout.addRow("Wilgotność względna:", self.humidity_spin)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        form_layout.addRow("Notatki:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_session_info(self) -> Dict:
        return {
            "operator": self.operator_edit.text(),
            "client": self.client_edit.text(),
            "order_number": self.order_edit.text(),
            "ambient_temperature": self.ambient_spin.value(),
            "relative_humidity": self.humidity_spin.value(),
            "notes": self.notes_edit.toPlainText()
        }

    def validate(self) -> bool:
        if not self.operator_edit.text().strip():
            QMessageBox.warning(self, "Walidacja", "Podaj nazwisko operatora.")
            return False
        return True


class CalibrationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia wzorcowania")
        self.setMinimumWidth(400)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        stability_group = QGroupBox("Stabilność temperatury")
        stability_layout = QFormLayout()
        
        self.stability_tolerance_spin = QDoubleSpinBox()
        self.stability_tolerance_spin.setRange(0.1, 5.0)
        self.stability_tolerance_spin.setValue(0.5)
        self.stability_tolerance_spin.setSuffix(" °C")
        stability_layout.addRow("Tolerancja:", self.stability_tolerance_spin)
        
        self.stability_time_spin = QDoubleSpinBox()
        self.stability_time_spin.setRange(10, 300)
        self.stability_time_spin.setValue(60)
        self.stability_time_spin.setSuffix(" s")
        stability_layout.addRow("Czas stabilizacji:", self.stability_time_spin)
        
        stability_group.setLayout(stability_layout)
        layout.addWidget(stability_group)
        
        measurement_group = QGroupBox("Pomiary")
        measurement_layout = QFormLayout()
        
        self.measurements_spin = QDoubleSpinBox()
        self.measurements_spin.setRange(3, 50)
        self.measurements_spin.setValue(10)
        self.measurements_spin.setDecimals(0)
        measurement_layout.addRow("Liczba pomiarów/punkt:", self.measurements_spin)
        
        self.switch_delay_spin = QDoubleSpinBox()
        self.switch_delay_spin.setRange(1, 60)
        self.switch_delay_spin.setValue(10)
        self.switch_delay_spin.setSuffix(" s")
        measurement_layout.addRow("Opóźnienie przełączania:", self.switch_delay_spin)
        
        self.max_stddev_spin = QDoubleSpinBox()
        self.max_stddev_spin.setRange(0.01, 1.0)
        self.max_stddev_spin.setValue(0.05)
        self.max_stddev_spin.setSuffix(" °C")
        measurement_layout.addRow("Maks. odch. standardowe:", self.max_stddev_spin)
        
        measurement_group.setLayout(measurement_layout)
        layout.addWidget(measurement_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> Dict:
        return {
            "stability_tolerance": self.stability_tolerance_spin.value(),
            "stability_time": int(self.stability_time_spin.value()),
            "measurements_per_point": int(self.measurements_spin.value()),
            "switch_delay": self.switch_delay_spin.value(),
            "max_stddev": self.max_stddev_spin.value()
        }


class ResultsViewDialog(QDialog):
    def __init__(self, results: List[Dict], parent=None):
        super().__init__(parent)
        self.results = results
        self.setWindowTitle("Wyniki wzorcowania")
        self.setMinimumSize(800, 500)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Kanał", "T zadana [°C]", "T średnia [°C]", "T ref. [°C]",
            "Błąd [°C]", "Odch. std [°C]", "U(k=2) [°C]", "Klasa"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for result in self.results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(result.get('channel_name', '')))
            self.table.setItem(row, 1, QTableWidgetItem(f"{result.get('point_temperature', 0):.1f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{result.get('avg_measured_temp', 0):.3f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{result.get('avg_reference_temp', 0):.3f}"))
            
            error = result.get('avg_measured_temp', 0) - result.get('avg_reference_temp', 0)
            self.table.setItem(row, 4, QTableWidgetItem(f"{error:+.3f}"))
            
            self.table.setItem(row, 5, QTableWidgetItem(f"{result.get('std_dev', 0):.4f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"±{result.get('expanded_uncertainty', 0):.3f}"))
            self.table.setItem(row, 7, QTableWidgetItem(result.get('sensor_class', '')))
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        
        export_btn = QPushButton("Eksportuj do CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)

    def _export_csv(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Zapisz wyniki", "", "CSV (*.csv)"
        )
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=';')
                    headers = []
                    for col in range(self.table.columnCount()):
                        headers.append(self.table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Eksport", f"Wyniki zapisano do:\n{filename}")
            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie udało siÄ™ zapisaÄ‡ pliku:\n{e}")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("O programie")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        title = QLabel("<h2>System Wzorcowania Czujników Temperatury</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        version = QLabel("<p>Wersja 1.0</p>")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        description = QLabel(
            "<p>Aplikacja do automatycznego wzorcowania czujników temperatury "
            "metodą porównawczą.</p>"
            "<p>Obsługiwane urządzenia:</p>"
            "<ul>"
            "<li>Termometr precyzyjny Cropico 3001</li>"
            "<li>Piec wzorcowy Pegasus</li>"
            "</ul>"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addStretch()
        
        institution = QLabel(
            "<p><b>AGH w Krakowie</b><br>"
            "Wydział Inżynierii Metalii i Informatyki Przemysłowej<br>"
            "Katedra Techniki Cieplnej i Ochrony Środowiska</p>"
        )
        institution.setAlignment(Qt.AlignCenter)
        layout.addWidget(institution)
        
        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
