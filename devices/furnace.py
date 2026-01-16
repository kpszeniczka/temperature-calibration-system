import serial
import struct
import time
import logging
from typing import Optional, Tuple
from config import (FURNACE_BAUDRATE, FURNACE_BYTESIZE, FURNACE_PARITY,
                    FURNACE_STOPBITS, FURNACE_TIMEOUT, FURNACE_SLAVE_ID,
                    FURNACE_PV_ADDRESS, FURNACE_SP_ADDRESS,
                    MODBUS_READ_HOLDING, MODBUS_WRITE_MULTIPLE)

logger = logging.getLogger(__name__)


class PegasusFurnace:
    def __init__(self, use_simulator: bool = False):
        self.ser: Optional[serial.Serial] = None
        self.connected = False
        self.port_number: Optional[int] = None
        self.use_simulator = use_simulator
        self.simulator = None
        self.slave_id = FURNACE_SLAVE_ID

        if use_simulator:
            from devices.simulators import FurnaceSimulator
            self.simulator = FurnaceSimulator()

    def connect(self, port_number: int) -> bool:
        if self.use_simulator:
            self.connected = True
            self.port_number = port_number
            logger.info(f"Furnace simulator connected on virtual COM{port_number}")
            return True

        try:
            port_name = f"COM{port_number}"
            self.ser = serial.Serial(
                port=port_name,
                baudrate=FURNACE_BAUDRATE,
                bytesize=FURNACE_BYTESIZE,
                parity=FURNACE_PARITY,
                stopbits=FURNACE_STOPBITS,
                timeout=FURNACE_TIMEOUT
            )
            time.sleep(0.2)
            success, pv = self.read_temperature()
            if success:
                self.connected = True
                self.port_number = port_number
                logger.info(f"Furnace connected on COM{port_number}, PV={pv:.1f}Â°C")
                return True
            else:
                self.ser.close()
                return False
        except serial.SerialException as e:
            logger.error(f"Failed to connect furnace to COM{port_number}: {e}")
            if self.ser and self.ser.is_open:
                self.ser.close()
            return False

    def disconnect(self):
        if self.use_simulator:
            self.connected = False
            logger.info("Furnace simulator disconnected")
            return
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
        logger.info("Furnace disconnected")

    def _calculate_crc(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def _build_read_request(self, address: int, count: int = 2) -> bytes:
        frame = struct.pack('>BBHH', self.slave_id, MODBUS_READ_HOLDING, address, count)
        crc = self._calculate_crc(frame)
        frame += struct.pack('<H', crc)
        return frame

    def _build_write_request(self, address: int, value: float) -> bytes:
        float_bytes = struct.pack('>f', value)
        reg_high = struct.unpack('>H', float_bytes[0:2])[0]
        reg_low = struct.unpack('>H', float_bytes[2:4])[0]
        frame = struct.pack('>BBHHB', self.slave_id, MODBUS_WRITE_MULTIPLE, 
                           address, 2, 4)
        frame += struct.pack('>HH', reg_high, reg_low)
        crc = self._calculate_crc(frame)
        frame += struct.pack('<H', crc)
        return frame

    def _parse_float_response(self, response: bytes) -> Optional[float]:
        if len(response) < 9:
            return None
        if response[0] != self.slave_id:
            return None
        if response[1] == (MODBUS_READ_HOLDING | 0x80):
            logger.error(f"Modbus exception: {response[2]}")
            return None
        byte_count = response[2]
        if byte_count != 4:
            return None
        float_bytes = response[3:7]
        crc_received = struct.unpack('<H', response[7:9])[0]
        crc_calculated = self._calculate_crc(response[0:7])
        if crc_received != crc_calculated:
            logger.error("CRC mismatch in response")
            return None
        value = struct.unpack('>f', float_bytes)[0]
        return value

    def read_temperature(self) -> Tuple[bool, float]:
        if self.use_simulator:
            return True, self.simulator.read_temperature()

        if not self.connected and not self.ser:
            return False, 0.0

        try:
            request = self._build_read_request(FURNACE_PV_ADDRESS)
            self.ser.reset_input_buffer()
            self.ser.write(request)
            time.sleep(0.1)
            response = self.ser.read(9)
            value = self._parse_float_response(response)
            if value is not None:
                return True, value
            return False, 0.0
        except Exception as e:
            logger.error(f"Failed to read furnace temperature: {e}")
            return False, 0.0

    def read_setpoint(self) -> Tuple[bool, float]:
        if self.use_simulator:
            return True, self.simulator.setpoint

        if not self.connected:
            return False, 0.0

        try:
            request = self._build_read_request(FURNACE_SP_ADDRESS)
            self.ser.reset_input_buffer()
            self.ser.write(request)
            time.sleep(0.1)
            response = self.ser.read(9)
            value = self._parse_float_response(response)
            if value is not None:
                return True, value
            return False, 0.0
        except Exception as e:
            logger.error(f"Failed to read setpoint: {e}")
            return False, 0.0

    def set_setpoint(self, temperature: float) -> bool:
        if self.use_simulator:
            self.simulator.set_setpoint(temperature)
            logger.info(f"Simulator setpoint set to {temperature}Â°C")
            return True

        if not self.connected:
            return False

        try:
            request = self._build_write_request(FURNACE_SP_ADDRESS, temperature)
            self.ser.reset_input_buffer()
            self.ser.write(request)
            time.sleep(0.2)
            response = self.ser.read(8)
            if len(response) >= 8:
                if response[1] == MODBUS_WRITE_MULTIPLE:
                    logger.info(f"Furnace setpoint set to {temperature}Â°C")
                    return True
                elif response[1] == (MODBUS_WRITE_MULTIPLE | 0x80):
                    logger.error(f"Modbus write exception: {response[2]}")
            return False
        except Exception as e:
            logger.error(f"Failed to set setpoint: {e}")
            return False

    def get_status(self) -> dict:
        success_pv, pv = self.read_temperature()
        success_sp, sp = self.read_setpoint()
        return {
            "connected": self.connected,
            "pv": pv if success_pv else None,
            "sp": sp if success_sp else None,
            "at_setpoint": abs(pv - sp) < 1.0 if (success_pv and success_sp) else False
        }

    @staticmethod
    def scan_ports() -> list:
        found_ports = []
        for port_num in range(1, 20):
            try:
                port_name = f"COM{port_num}"
                ser = serial.Serial(
                    port=port_name,
                    baudrate=FURNACE_BAUDRATE,
                    bytesize=FURNACE_BYTESIZE,
                    parity=FURNACE_PARITY,
                    stopbits=FURNACE_STOPBITS,
                    timeout=0.5
                )
                frame = struct.pack('>BBHH', FURNACE_SLAVE_ID, MODBUS_READ_HOLDING,
                                   FURNACE_PV_ADDRESS, 2)
                crc = 0xFFFF
                for byte in frame:
                    crc ^= byte
                    for _ in range(8):
                        if crc & 0x0001:
                            crc = (crc >> 1) ^ 0xA001
                        else:
                            crc >>= 1
                frame += struct.pack('<H', crc)
                ser.write(frame)
                time.sleep(0.2)
                response = ser.read(9)
                ser.close()
                if len(response) >= 9 and response[0] == FURNACE_SLAVE_ID:
                    found_ports.append({
                        "port": port_num,
                        "device": "Pegasus Furnace",
                        "id": f"Slave ID: {FURNACE_SLAVE_ID}"
                    })
            except:
                pass
        return found_ports
