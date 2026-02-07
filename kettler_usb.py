"""
KettlerUSB - Serial communication with Kettler bike trainer
Handles USB serial protocol, auto-reconnect, and data parsing
"""

import time
import logging
import threading
from pyee.base import EventEmitter
import serial

logger = logging.getLogger(__name__)

EOL = '\r\n'
PORT_NAME = '/dev/ttyUSB0'
DEBUG = True


class KettlerUSB(EventEmitter):
    """
    Manages serial communication with Kettler bike via USB
    """
    
    def __init__(self):
        super().__init__()
        logger.info('[KettlerUSB] Constructor')
        
        self.port = None
        self.running = False
        self.read_thread = None
        self.poll_thread = None
        
        # Initialization sequence
        self.init_messages = ["VE", "ID", "VE", "KI", "CA", "RS", "CM", "SP1"]
        
        # Power control
        self.write_power = False
        self.power = -1
        
        # Debug timing
        self.last_time = None
        
    def direct_write(self, data):
        """Write command to serial port"""
        if DEBUG:
            logger.info(f'[KettlerUSB] write: {data}')
        try:
            if self.port and self.port.is_open:
                self.port.write((data + EOL).encode('ascii'))
        except Exception as e:
            logger.error(f'[KettlerUSB] Write error: {e}')
            
    def read_and_dispatch(self, data):
        """
        Parse incoming serial data and emit events
        
        Args:
            data: String received from serial port
        """
        if not isinstance(data, str):
            logger.error('[KettlerUSB] Strange data type')
            logger.error(data)
            return
            
        if DEBUG:
            if self.last_time is None:
                self.last_time = time.time()
            delta = int((time.time() - self.last_time) * 1000)
            logger.info(f'[KettlerUSB] read [{delta}ms]: {data}')
            self.last_time = time.time()
            
        states = data.split('\t')
        
        # Parse ST response (8 fields)
        # Format: HR\tRPM\tSpeed\tDistance\tPower\tEnergy\tTime\tCurrentPower
        # Example: 101\t047\t074\t002\t025\t0312\t01:12\t025
        if len(states) == 8:
            data_out = {}
            
            # Speed (column 3, in tenths of km/h)
            try:
                speed = int(states[2])
                data_out['speed'] = speed * 0.1
            except (ValueError, IndexError):
                pass
                
            # Current power on brake (column 8)
            try:
                power = int(states[7])
                data_out['power'] = power
            except (ValueError, IndexError):
                pass
                
            # Target power (column 5)
            try:
                target_power = int(states[4])
                data_out['targetPower'] = target_power
            except (ValueError, IndexError):
                pass
                
            # Cadence/RPM (column 2)
            try:
                cadence = int(states[1])
                data_out['cadence'] = cadence
                data_out['rpm'] = cadence
            except (ValueError, IndexError):
                pass
                
            # Heart rate (column 1)
            try:
                hr = int(states[0])
                data_out['hr'] = hr
            except (ValueError, IndexError):
                pass
                
            if data_out:
                self.emit('data', data_out)
                
        # Parse key press response (4 fields)
        elif len(states) == 4:
            try:
                key = int(states[3])
                self.emit('key', key)
            except (ValueError, IndexError):
                pass
        else:
            if DEBUG:
                logger.info('[KettlerUSB] Unrecognized packet')
                
    def open(self):
        """Open serial port and start communication"""
        logger.info('[KettlerUSB] Opening port')
        self.emit('connecting')
        self.running = True
        
        # Start connection thread
        self.read_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self.read_thread.start()
        
    def _connection_loop(self):
        """Main connection loop with auto-reconnect"""
        while self.running:
            try:
                self._internal_open()
            except Exception as e:
                logger.error(f'[KettlerUSB] Connection error: {e}')
                time.sleep(10)
                
    def _internal_open(self):
        """Try to open serial port"""
        try:
            logger.info(f'[KettlerUSB] Attempting to open {PORT_NAME}')
            self.port = serial.Serial(
                port=PORT_NAME,
                baudrate=57600,
                timeout=1
            )
            
            logger.info('[KettlerUSB] Port opened')
            self.emit('open')
            
            # Initialize
            self._init()
            time.sleep(0.5)
            
            self.emit('start')
            
            # Start polling after 3 seconds
            time.sleep(3)
            self._start_polling()
            
            # Read loop
            while self.running and self.port and self.port.is_open:
                try:
                    if self.port.in_waiting > 0:
                        line = self.port.readline().decode('ascii').strip()
                        if line:
                            self.read_and_dispatch(line)
                except Exception as e:
                    logger.error(f'[KettlerUSB] Read error: {e}')
                    break
                    
            logger.info('[KettlerUSB] Connection closed')
            
        except serial.SerialException as e:
            logger.error(f'[KettlerUSB] Port open failed: {e}')
            logger.info('[KettlerUSB] Will retry in 10s')
            time.sleep(10)
        except Exception as e:
            logger.error(f'[KettlerUSB] Unexpected error: {e}')
            time.sleep(10)
        finally:
            if self.port and self.port.is_open:
                self.port.close()
                
    def _init(self):
        """Send initialization sequence"""
        logger.info('[KettlerUSB] Initializing bike')
        for msg in self.init_messages:
            self.direct_write(msg)
            time.sleep(0.15)
            
    def _start_polling(self):
        """Start polling thread for bike state"""
        if self.poll_thread and self.poll_thread.is_alive():
            return
            
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        
    def _poll_loop(self):
        """Poll bike state every 2 seconds"""
        while self.running and self.port and self.port.is_open:
            try:
                if self.write_power:
                    self.direct_write(f"PW{self.power}")
                    self.write_power = False
                else:
                    self.direct_write("ST")
                time.sleep(1)
            except Exception as e:
                logger.error(f'[KettlerUSB] Poll error: {e}')
                break
                
    def restart(self):
        """Restart connection"""
        logger.info('[KettlerUSB] Restarting')
        if self.port and self.port.is_open:
            self.stop()
            self.port.close()
            self.emit('stop')
        time.sleep(1)
        
    def stop(self):
        """Stop communication and close port"""
        logger.info('[KettlerUSB] Stopping')
        self.direct_write("VE")
        self.direct_write("ID")
        self.direct_write("VE")
        
    def set_power(self, power):
        """
        Set target power resistance on bike
        
        Args:
            power: Target power in watts
        """
        p = max(0, int(power))
        if p != self.power:
            self.power = p
            self.write_power = True
            
    def close(self):
        """Close serial port and stop threads"""
        self.running = False
        if self.port and self.port.is_open:
            self.stop()
            self.port.close()
