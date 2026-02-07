"""
BikeState - Manages the state of the Kettler bike trainer
Handles modes (ERG/SIM), gear, target power, and physics calculations
"""

import logging
from pyee.base import EventEmitter

logger = logging.getLogger(__name__)

MIN_GEAR = 1
MAX_GEAR = 20


class BikeState(EventEmitter):
    """
    Manages bike trainer state and calculations
    Supports ERG mode (fixed power) and SIM mode (physics simulation)
    """
    
    def __init__(self):
        super().__init__()
        logger.info('[BikeState] Starting')
        
        # Current sensor data from bike
        self.data = None
        
        # External conditions for simulation mode
        self.external = None
        
        # Mode: 'ERG' (fixed power) or 'SIM' (physics simulation)
        self.mode = 'ERG'
        
        # Virtual gear (1-10)
        self.gear = 1
        
        # Target power in watts (ERG mode)
        self.target_power = None
        
    def restart(self):
        """Reset the trainer to initial state"""
        self.mode = 'ERG'
        self.emit('mode', self.mode)
        self.data = None
        
    def set_control(self):
        """Called when BLE client takes control"""
        pass
        
    def set_data(self, data):
        """
        Update current bike data from USB serial
        
        Args:
            data: Dict with speed, power, rpm, hr, targetPower, etc.
        """
        self.data = data
        
        # Initialize target_power from bike data on first reception
        if self.target_power is None and 'targetPower' in data:
            self.target_power = data['targetPower']
            logger.info(f'[BikeState] Initialized targetPower from bike: {self.target_power}')
            self.emit('targetPower', self.target_power)
        
        # Trigger calculations
        self.compute()
        
    def set_gear(self, gear):
        """Set the virtual gear (1-10)"""
        self.gear = max(MIN_GEAR, min(MAX_GEAR, gear))
        self.emit('gear', self.gear)
        
    def gear_up(self):
        """Increase gear by 1"""
        self.gear = min(MAX_GEAR, self.gear + 1)
        self.emit('gear', self.gear)
        
    def gear_down(self):
        """Decrease gear by 1"""
        self.gear = max(MIN_GEAR, self.gear - 1)
        self.emit('gear', self.gear)
        
    def set_target_power(self, power):
        """
        Set target power in ERG mode
        
        Args:
            power: Power in watts
        """
        self.mode = 'ERG'
        self.emit('mode', self.mode)
        self.target_power = int(power)
        self.emit('targetPower', self.target_power)
        self.emit('simpower', self.target_power)
        
    def add_power(self, increment):
        """
        Adjust target power by increment
        
        Args:
            increment: Power change in watts (can be negative)
        """
        if self.target_power is None:
            self.target_power = 100
            
        self.target_power += increment
        # Clamp between 0 and 1000W
        self.target_power = max(0, min(1000, self.target_power))
        self.emit('targetPower', self.target_power)
        self.emit('simpower', self.target_power)
        
    def set_external_condition(self, windspeed, grade, crr, cw):
        """
        Set external conditions for SIM mode
        
        Args:
            windspeed: Wind speed in m/s
            grade: Grade in percent
            crr: Rolling resistance coefficient
            cw: Wind resistance coefficient
        """
        self.mode = 'SIM'
        self.emit('mode', self.mode)
        
        self.external = {
            'windspeed': windspeed,
            'grade': grade,
            'crr': crr,
            'cw': cw
        }
        
        self.emit('windspeed', round(windspeed * 3.6, 1))
        self.emit('grade', round(grade, 1))
        
    def compute(self):
        """
        Calculate simulated power based on physics
        Only active in SIM mode
        """
        # Skip if in ERG mode
        if self.mode == 'ERG':
            return
            
        # Need bike data
        if self.data is None:
            return
            
        # Need external conditions
        if self.external is None:
            return
            
        # Get current RPM
        rpm = self.data.get('rpm', 80)
        
        # Physics-based power calculation
        # Base power adjusted for RPM and grade
        simpower = 170 * (1 + 1.15 * (rpm - 80.0) / 80.0) * (1.0 + 3 * self.external['grade'] / 100.0)
        
        # Apply gear multiplier
        simpower = max(0.0, simpower * (1.0 + 0.1 * (self.gear - 5)))
        
        # Round to 1 decimal
        simpower = round(simpower, 1)
        
        logger.debug(f'[BikeState] SIM - rpm: {rpm}, grade: {self.external["grade"]}, gear: {self.gear}, power: {simpower}')
        
        self.emit('simpower', simpower)
