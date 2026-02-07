#!/usr/bin/env python3
"""
Kettler USB to BLE Bridge - Main Server
Pure Python implementation with bluezero for BlueZ integration
"""

import sys
import logging
import threading
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from bike_state import BikeState
from kettler_usb import KettlerUSB
from kettler_ble import KettlerBLE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__, template_folder='views')
app.config['SECRET_KEY'] = 'kettler-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# Global state
bike_state = None
kettler_usb = None
kettler_ble = None

# Status tracking
usb_status = {'connected': False, 'error': 'Bike not connected'}
ble_status = {'enabled': False, 'error': None}
ble_ready = threading.Event()


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.ejs')


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection"""
    logger.info('Socket client connected')
    # Send current status
    logger.info(f'Sending USB status: {usb_status}')
    logger.info(f'Sending BLE status: {ble_status}')
    emit('usbStatus', usb_status)
    emit('bleStatus', ble_status)
    if bike_state:
        emit('targetPower', bike_state.target_power)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnection"""
    logger.info('Socket client disconnected')


@socketio.on('key')
def handle_key(key_event):
    """Handle key events from web interface"""
    logger.info(f'Key event received: {key_event}')
    
    if not bike_state:
        return
        
    if key_event == 'PowerUp':
        logger.info('Power Up command')
        bike_state.add_power(20)
    elif key_event == 'PowerDn':
        logger.info('Power Down command')
        bike_state.add_power(-20)
    elif key_event == 'GearUp':
        logger.info('Gear Up command')
        bike_state.gear_up()
    elif key_event == 'GearDn':
        logger.info('Gear Down command')
        bike_state.gear_down()
    elif key_event == 'pause':
        logger.info('Pause command')
        bike_state.set_target_power(140)
    else:
        logger.warning(f'Unknown key event: {key_event}')


@socketio.on('mode')
def handle_mode(new_mode):
    """Handle mode switch requests"""
    logger.info(f'Mode switch requested: {new_mode}')
    
    if not bike_state:
        return
        
    if new_mode == 'SIM':
        logger.info('Switching to SIM mode')
        bike_state.set_external_condition(0, 3, 0.005, 0.39)
    elif new_mode == 'ERG':
        logger.info('Switching to ERG mode')
        bike_state.set_target_power(100)


def ble_control_callback(message, *args):
    """
    Callback from BLE server when control commands are received
    """
    success = False
    
    if message == 'reset':
        logger.info('[server.py] - Bike reset')
        if kettler_usb:
            kettler_usb.restart()
        if bike_state:
            bike_state.restart()
        success = True
        
    elif message == 'control':
        logger.info('[server.py] - Bike is under control')
        if bike_state:
            bike_state.set_control()
        success = True
        
    elif message == 'power':
        power = args[0] if args else 100
        logger.info(f'[server.py] - Bike in ERG Mode: {power}W')
        if bike_state:
            bike_state.set_target_power(power)
        success = True
        
    elif message == 'simulation':
        windspeed = float(args[0]) if len(args) > 0 else 0
        grade = float(args[1]) if len(args) > 1 else 0
        crr = float(args[2]) if len(args) > 2 else 0.005
        cw = float(args[3]) if len(args) > 3 else 0.39
        logger.info(f'[server.py] - Bike SIM Mode - wind: {windspeed*3.6:.1f}km/h, grade: {grade:.1f}%')
        if bike_state:
            bike_state.set_external_condition(windspeed, grade, crr, cw)
        success = True
        
    return success


def setup_bike_state_events():
    """Configure event handlers for bike state changes"""
    if not bike_state:
        return
        
    bike_state.on('mode', lambda mode: socketio.emit('mode', mode))
    bike_state.on('gear', lambda gear: socketio.emit('gear', gear))
    bike_state.on('grade', lambda grade: socketio.emit('grade', f'{grade}%'))
    bike_state.on('windspeed', lambda ws: socketio.emit('windspeed', ws))
    bike_state.on('simpower', lambda sp: (
        socketio.emit('simpower', sp),
        kettler_usb.set_power(sp) if kettler_usb else None
    ))
    bike_state.on('targetPower', lambda tp: socketio.emit('targetPower', tp))


def setup_usb_events():
    """Configure event handlers for USB serial port"""
    if not kettler_usb:
        return
        
    def on_error(error_msg):
        logger.error(f'USB Error: {error_msg}')
        usb_status['connected'] = False
        usb_status['error'] = 'Bike not connected'
        socketio.emit('error', error_msg)
        socketio.emit('usbStatus', usb_status)
        
    def on_connecting():
        logger.info('USB connecting...')
        usb_status['connected'] = False
        usb_status['error'] = 'Connecting to bike...'
        socketio.emit('status', 'Connecting to bike...')
        socketio.emit('usbStatus', usb_status)
        
    def on_start():
        logger.info('USB connected')
        usb_status['connected'] = True
        usb_status['error'] = None
        socketio.emit('status', 'Bike connected')
        socketio.emit('usbStatus', usb_status)
        
    def on_data(data):
        # Update bike state
        if bike_state:
            bike_state.set_data(data)
        
        # Send to web clients
        if 'speed' in data:
            socketio.emit('speed', f"{data['speed']:.1f}")
        if 'power' in data:
            socketio.emit('power', data['power'])
        if 'targetPower' in data:
            socketio.emit('targetPower', data['targetPower'])
        if 'hr' in data:
            socketio.emit('hr', data['hr'])
        if 'rpm' in data:
            socketio.emit('rpm', data['rpm'])
        
        # Send to BLE
        if kettler_ble:
            kettler_ble.notify_ftms(data)
    
    kettler_usb.on('error', on_error)
    kettler_usb.on('connecting', on_connecting)
    kettler_usb.on('start', on_start)
    kettler_usb.on('data', on_data)


def start_ble_server():
    """Start the BLE GATT server in background"""
    global kettler_ble, ble_status
    
    def on_ble_ready(enabled, error):
        """Callback when BLE is ready"""
        ble_status['enabled'] = enabled
        ble_status['error'] = error if not enabled else None
        ble_ready.set()
    
    try:
        kettler_ble = KettlerBLE(ble_control_callback)
        kettler_ble.start(status_callback=on_ble_ready)  # This blocks!
    except Exception as e:
        logger.error(f'[BLE] ✗ Exception: {e}')
        ble_status['enabled'] = False
        ble_status['error'] = 'Bluetooth disabled'
        ble_ready.set()
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    global bike_state, kettler_usb
    
    logger.info('=== Kettler USB to BLE Bridge ===')
    logger.info('Pure Python implementation with bluezero')
    
    # Initialize components
    bike_state = BikeState()
    bike_state.set_gear(4)
    setup_bike_state_events()
    
    kettler_usb = KettlerUSB()
    setup_usb_events()
    
    # Start USB serial communication
    kettler_usb.open()
    
    # Start BLE server in background thread
    ble_thread = threading.Thread(target=start_ble_server, daemon=True)
    ble_thread.start()
    
    # Wait for BLE to initialize (max 10 seconds)
    logger.info('Waiting for BLE initialization...')
    if ble_ready.wait(timeout=10):
        logger.info(f'BLE ready: enabled={ble_status["enabled"]}, error={ble_status["error"]}')
    else:
        logger.warning('BLE initialization timeout - may still be starting in background')
        logger.info(f'Current BLE status: enabled={ble_status["enabled"]}, error={ble_status["error"]}')
    
    logger.info('Starting web server on port 3000...')
    logger.info('Dashboard: http://kettlerble:3000')
    
    # Run Flask app with SocketIO
    socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True, log_output=False)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('\nShutdown requested... exiting')
        sys.exit(0)
    except Exception as e:
        logger.error(f'Fatal error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
