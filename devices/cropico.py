import serial
import time
import re
import logging
from typing import Optional, Tuple
from config import (CROPICO_BAUDRATE, CROPICO_BYTESIZE, CROPICO_PARITY,
                    CROPICO_STOPBITS, CROPICO_TIMEOUT, CROPICO_READ_TIMEOUT_MS)

logger = logging.getLogger(__name__)


class CropicoDevice:
    def __init__(self, use_simulator: bool = False):
        self.ser: Optional[serial.Serial] = None
        self.connected = False
        self.port_number: Optional[int] = None
        self.use_simulator = use_simulator
        self.simulator = None
        self.current_channel = "A0"
        self.device_id = ""

        if use_simulator:
            from devices.simulators import CropicoSimulator
            self.simulator = CropicoSimulator()

    def connect(self, port_number: int) -> bool:
        if self.use_simulator:
            self.connected = True
            self.port_number = port_number
            self.device_id = "CROPICO,3001,SIMULATOR,1.0"
            logger.info(f"Cropico simulator connected on virtual COM{port_number}")
            return True

        try:
            port_name = f"COM{port_number}"
            self.ser = serial.Serial()
            self.ser.port = port_name
            self.ser.baudrate = CROPICO_BAUDRATE
            self.ser.bytesize = CROPICO_BYTESIZE
            self.ser.parity = CROPICO_PARITY
            self.ser.stopbits = CROPICO_STOPBITS
            self.ser.timeout = CROPICO_TIMEOUT
            self.ser.xonxoff = False
            self.ser.rtscts = False
            self.ser.dsrdtr = False
            self.ser.open()
            self.ser.dtr = True
            self.ser.rts = True
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self._write("*RST\r\n")
            time.sleep(0.3)
            self._write("*IDN?\r\n")
            response = self._read(CROPICO_READ_TIMEOUT_MS)
            if response and "CROPICO" in response.upper():
                self.device_id = response.strip()
                self._write("SYST:REM\r\n")
                time.sleep(0.1)
                self.connected = True
                self.port_number = port_number
                logger.info(f"Cropico connected: {self.device_id}")
                return True
            else:
                self.ser.close()
                logger.warning(f"Device on COM{port_number} is not Cropico: {response}")
                return False
        except serial.SerialException as e:
            logger.error(f"Failed to connect to COM{port_number}: {e}")
            if self.ser and self.ser.is_open:
                self.ser.close()
            return False

    def disconnect(self):
        if self.use_simulator:
            self.connected = False
            logger.info("Cropico simulator disconnected")
            return
        if self.ser and self.ser.is_open:
            try:
                self._write("SYST:LOC\r\n")
                time.sleep(0.1)
            except:
                pass
            self.ser.close()
        self.connected = False
        logger.info("Cropico disconnected")

    def _write(self, command: str):
        if self.ser and self.ser.is_open:
            self.ser.write(command.encode('ascii'))
            logger.debug(f"TX: {command.strip()}")

    def _read(self, timeout_ms: int = 3000) -> Optional[str]:
        if not self.ser or not self.ser.is_open:
            return None
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        buffer = ""
        while (time.time() - start_time) < timeout_sec:
            if self.ser.in_waiting > 0:
                char = self.ser.read(1).decode('ascii', errors='ignore')
                buffer += char
                if '\n' in buffer:
                    logger.debug(f"RX: {buffer.strip()}")
                    return buffer.strip()
            else:
                time.sleep(0.01)
        if buffer:
            logger.debug(f"RX (timeout): {buffer.strip()}")
            return buffer.strip()
        return None

    def configure_channel(self, channel: str, sensor_type: str = "PT100") -> bool:
        if self.use_simulator:
            self.current_channel = channel
            return True

        if not self.connected:
            return False

        try:
            scanner = channel[0]
            channel_num = int(channel[1])
            self._write(f"CONF:CHAN {scanner},{channel_num}\r\n")
            time.sleep(0.1)

            if sensor_type == "PT100":
                self._write("CONF:TEMP:RTD PT100,4W,100,0.00385\r\n")
            elif sensor_type.startswith("TC_"):
                tc_type = sensor_type.split("_")[1]
                self._write(f"CONF:TEMP:TC {tc_type},INT\r\n")
            time.sleep(0.1)
            self.current_channel = channel
            logger.info(f"Configured channel {channel} as {sensor_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure channel {channel}: {e}")
            return False

    def read_temperature(self) -> Tuple[bool, float]:
        if self.use_simulator:
            temp = self.simulator.read_temperature(self.current_channel)
            return True, temp

        if not self.connected:
            return False, 0.0

        try:
            self._write("TRIG:MODE IMM\r\n")
            time.sleep(0.2)
            self._write("READ?\r\n")
            response = self._read(CROPICO_READ_TIMEOUT_MS)

            if response:
                match = re.search(r'([+-]?\d+\.?\d*)', response)
                if match:
                    temp = float(match.group(1))
                    if -200 <= temp <= 2000:
                        return True, temp
                    else:
                        logger.warning(f"Temperature out of range: {temp}")
                        return False, 0.0
                if "OVF" in response.upper() or "OVERFLOW" in response.upper():
                    logger.warning(f"Sensor overflow on {self.current_channel}")
                    return False, float('inf')
            return False, 0.0
        except Exception as e:
            logger.error(f"Failed to read temperature: {e}")
            return False, 0.0

    def read_channel(self, channel: str, sensor_type: str = "PT100") -> Tuple[bool, float]:
        if not self.configure_channel(channel, sensor_type):
            return False, 0.0
        time.sleep(0.3)
        return self.read_temperature()

    def read_current_channel_value(self) -> Tuple[float, str]:
        success, temp = self.read_temperature()
        if success:
            return temp, self.current_channel
        return 0.0, self.current_channel

    def get_raw_value(self) -> Tuple[bool, float]:
        if self.use_simulator:
            return True, self.simulator.get_raw_value(self.current_channel)
        if not self.connected:
            return False, 0.0
        try:
            self._write("MEAS:RES?\r\n")
            response = self._read(CROPICO_READ_TIMEOUT_MS)
            if response:
                match = re.search(r'([+-]?\d+\.?\d*)', response)
                if match:
                    return True, float(match.group(1))
            return False, 0.0
        except Exception as e:
            logger.error(f"Failed to read raw value: {e}")
            return False, 0.0

    def self_test(self) -> bool:
        if self.use_simulator:
            return True
        if not self.connected:
            return False
        try:
            self._write("*TST?\r\n")
            response = self._read(5000)
            return response and "0" in response
        except:
            return False

    @staticmethod
    def scan_ports() -> list:
        found_ports = []
        for port_num in range(1, 20):
            try:
                port_name = f"COM{port_num}"
                ser = serial.Serial()
                ser.port = port_name
                ser.baudrate = CROPICO_BAUDRATE
                ser.bytesize = CROPICO_BYTESIZE
                ser.parity = CROPICO_PARITY
                ser.stopbits = CROPICO_STOPBITS
                ser.timeout = 0.5
                ser.open()
                ser.dtr = True
                ser.rts = True
                time.sleep(0.3)
                ser.reset_input_buffer()
                ser.write(b"*IDN?\r\n")
                time.sleep(0.3)
                response = ""
                while ser.in_waiting > 0:
                    response += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                ser.close()
                if "CROPICO" in response.upper():
                    found_ports.append({
                        "port": port_num,
                        "device": "Cropico 3001",
                        "id": response.strip()
                    })
            except:
                pass
        return found_ports
