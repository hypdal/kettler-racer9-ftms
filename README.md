# Kettler USB to BLE Bridge

Bridge classic Kettler Racer 9 exercise bike to modern Bluetooth-enabled fitness apps (Kinomap, MyWhoosh, etc.) via FTMS (Fitness Machine Service) and Cycling Power Service.

**Pure Python implementation with native BlueZ D-Bus GATT server support.**

## Credits

This project is based on [kettlerUSB2BLE](https://github.com/bbashinskiy/kettlerUSB2BLE) 
by bbashinskiy. Thank you for the foundation!

## Features

- **FTMS (Fitness Machine Service)** - Full control from cycling apps
- **Cycling Power Service** - Real-time power and cadence monitoring
- **ERG Mode** - Target power control
- **SIM Mode** - Physics-based resistance with wind speed, grade, rolling resistance
- **Web Dashboard** - Real-time monitoring at `http://your-pi-ip:3000`
- **GPIO Buttons** - Hardware gear shift controls (optional)
- **Native BlueZ GATT** - Proper D-Bus implementation for latest Raspberry Pi OS
- **Python 3** - Clean, maintainable codebase

## Hardware Requirements

- **Raspberry Pi Zero 2 W** (or any Pi with Bluetooth)
- **Micro SD Card** (8GB minimum)
- **USB Power Supply** (1A minimum)
- **USB-A to Micro-USB Cable** (for connecting bike to Pi)

## Setup (Quick Start)

### 1. Flash Raspberry Pi OS

Use **Raspberry Pi Imager** (download from https://www.raspberrypi.com/software/):

1. Open Raspberry Pi Imager
2. **Choose Device** → Raspberry Pi Zero 2 W
3. **Choose OS** → Raspberry Pi OS (latest, 64-bit recommended)
4. **Choose Storage** → Your SD card
5. **Advanced Options** (click the gear icon):
   - **Hostname:** kettler
   - **Username:** kettler
   - **Password:** (set your password)
   - **Configure WiFi:** Enable, enter SSID & password
   - **Locale/Timezone:** Set to your region
   - **SSH:** Enable (password auth)
6. Click **Save** and flash

### 2. Boot and Connect

Insert SD card into Pi Zero 2 W and power on. Wait 2-3 minutes for first boot.

Find your Pi's IP address (check your router or use: `nmap -sn 192.168.1.0/24`)

SSH into the Pi:
```bash
ssh kettler@<pi-ip-address>
# Password: (the one you set in Imager)
```

### 3. Install Python Dependencies

```bash
# Update system packages
sudo apt update

# Install Python pip and Bluetooth libraries
sudo apt install -y python3-pip python3-dev libdbus-1-dev libglib2.0-dev git

# Verify Python 3 is installed (should be 3.9+)
python3 --version
```

**Note:** BlueZ is pre-installed on Raspberry Pi OS.

### 4. Setup Bluetooth Permissions

```bash
# Unblock Bluetooth (if RF-kill is enabled)
sudo rfkill unblock bluetooth

# Power on Bluetooth adapter
sudo hciconfig hci0 up

# Verify adapter is UP and RUNNING
hciconfig
# Should show: UP RUNNING PSCAN ISCAN

# Add user to bluetooth group (optional, for better permissions)
sudo usermod -a -G bluetooth $USER

# Log out and back in for group to take effect
exit
# SSH back in
```

### 5. Copy Project to Pi

From your computer (not the Pi):
```bash
# Copy the project to your Pi
git clone 

```

### 6. Install Python Packages

On the Pi:
```bash
cd ~/kettler-racer9-ftms
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Install Python dependencies
pip3 install -r requirements.txt
```

**⏳ First install takes 2-3 minutes**

### 7. Test the Installation

```bash
python3 server.py
```

You should see output like:
```
[INFO] === Kettler USB to BLE Bridge ===
[INFO] Pure Python implementation with bluezero
[INFO] [BikeState] Starting
[INFO] [KettlerUSB] Constructor
[INFO] [KettlerBLE] Initializing on adapter XX:XX:XX:XX:XX:XX
[INFO] Starting web server on port 3000...
[INFO] [KettlerBLE] Starting BLE peripheral...
[INFO] [KettlerBLE] Added FTMS service with 5 characteristics
[INFO] [KettlerBLE] Added Cycling Power service with 3 characteristics
[INFO] [KettlerBLE] ✓ BLE server started and advertising as "KettlerBLE"
[INFO] [KettlerBLE] Services exposed:
[INFO] [KettlerBLE]   • Fitness Machine (FTMS) - 1826
[INFO] [KettlerBLE]   • Cycling Power - 1818
 * Running on http://0.0.0.0:3000
```

Press **Ctrl+C** to stop. If you see errors, check [Troubleshooting](#troubleshooting) below.

### 8. Connect Bike USB

1. Connect USB cable from Pi's **data USB port** (center micro-USB) to your Kettler bike's USB port
2. Restart the application: `python3 server.py`
3. You should hear a sound from the bike confirming USB connection

### 9. (Optional) Set Up Automatic Startup

Create a systemd service to auto-start the application on boot:

```bash
sudo nano /etc/systemd/system/kettler.service
```

Paste this content:
```ini
[Unit]
Description=Kettler USB to BLE Bridge
After=network-online.target bluetooth.target
Wants=network-online.target

[Service]
Type=simple
User=kettler
WorkingDirectory=/home/kettler/kettlerUSB2BLE
ExecStart=/usr/bin/python3 server.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

Save (Ctrl+X, Y, Enter), then enable:

```bash
sudo systemctl enable kettler.service
sudo systemctl start kettler.service
sudo systemctl status kettler.service
```

View logs anytime:
```bash
journalctl -u kettler -f
```

## Usage

### Web Dashboard

Open browser to: `http://kettler.local:3000` (or `http://<pi-ip>:3000`)

Features:
- Real-time power, speed, cadence, HR display
- Gear up/down buttons
- Mode switcher (ERG vs SIM)
- Connection status indicator

### Pair with Zwift / Apps

1. In your fitness app (Zwift, MyWhoosh, etc.), search for Bluetooth devices
2. Look for **"KettlerBLE"** device
3. Pair (usually no PIN required)
4. App should recognize it as FTMS bike with power meter
5. Start workout!

### Hardware Buttons (Optional)

If you solder GPIO buttons:
- **GPIO 7** = Gear Down
- **GPIO 11** = Gear Up

## Architecture

```
Kettler Bike USB Port
        ↓
   PySerial (kettler_usb.py)
        ↓
    BikeState (bike_state.py - in-memory state machine)
        ↙          ↘
    Flask Web UI    BlueZ GATT Server (kettler_ble.py)
   (port 3000)      ↓ (D-Bus native with bluezero)
                 BLE Advertisement
                    ↓
          Fitness Apps (FTMS Client)
```

**Technology Stack:**
- **Python 3.9+** - Main application language
- **Flask + Flask-SocketIO** - Web server with WebSocket support
- **PySerial** - USB serial communication
- **bluezero 0.8.0** - BlueZ D-Bus bindings for proper GATT peripheral mode
- **pyee** - Event emitter pattern

**Key Services:**
- **FTMS (0x1826):** Fitness Machine Service
  - Indoor Bike Data (0x2AD2) - notify
  - Fitness Control Point (0x2AD9) - write + indicate
  - Fitness Machine Status (0x2ADA) - notify
  - Fitness Machine Feature (0x2ACC) - read
  - Supported Power Range (0x2AD8) - read

- **Cycling Power (0x1818):** Standard Power Meter Service
  - Cycling Power Measurement (0x2A63) - notify
  - Cycling Power Feature (0x2A65) - read
  - Sensor Location (0x2A5D) - read

## Troubleshooting

### Application won't start

**Check logs:**
```bash
journalctl -u kettler -f  # If running as service
# OR
python3 server.py  # Run directly to see errors
```

**Common issues:**
- "ModuleNotFoundError: No module named 'bluezero'" → Run `pip3 install -r requirements.txt` again
- "Cannot find /dev/hci0" → Bluetooth adapter not detected (check hardware)
- "Permission denied /dev/ttyUSB0" → Add user to dialout group: `sudo usermod -a -G dialout kettler`
- "D-Bus connection failed" → Make sure BlueZ daemon is running: `sudo systemctl status bluetooth`

### Bike USB not detected

1. Verify cable is in **data port** (center micro-USB), not power port
2. Try different USB cable
3. Check with: `lsusb` - should show Kettler device or FTDI serial adapter
4. Check if `/dev/ttyUSB0` exists: `ls -l /dev/ttyUSB*`
5. Add to dialout group: `sudo usermod -a -G dialout kettler`, then logout/login
6. Restart Pi: `sudo reboot`

### Not visible in Zwift/other apps

1. Make sure service is running: `systemctl status kettler`
2. Check Bluetooth is powered: `hciconfig` should show "UP RUNNING"
3. Test advertising: `sudo bluetoothctl` then `scan on` - should see "KettlerBLE"
4. In app, scan for devices again
5. Check Bluetooth is enabled on your phone/device
6. Try: `sudo systemctl restart kettler`
7. Some devices require being close (<2m) initially for pairing

### Web dashboard not loading

- Is service running? `systemctl status kettler`
- Check IP: `hostname -I`
- Try `http://<ip>:3000` directly instead of hostname
- Check firewall not blocking port 3000: `sudo ufw status`
- Make sure you're on the same WiFi network

### Characteristic value not updating

1. Verify bike USB is connected and recognized (`ls /dev/ttyUSB*`)
2. Check logs: `journalctl -u kettler -f`
3. Look for `[KettlerUSB] read` messages - if missing, USB not communicating
4. Make sure app has **subscribed to notifications** (look for `notifications ENABLED` in logs)
5. Verify `characteristic.set_value()` push notifications in logs (`✓ Pushed` messages)
6. Try unplugging/replugging bike USB cable
7. Sometimes requires app restart to start receiving notifications

### BLE GATT errors

- "org.bluez.Error.Failed" → BlueZ daemon issue, restart: `sudo systemctl restart bluetooth`
- "Method not found" → bluezero version issue, reinstall: `pip3 install --upgrade bluezero`
- "characteristic.set_value() AttributeError" → Client not subscribed, check notifications are enabled
- Services not visible → Check with: `bluetoothctl`, then `scan on` to see "KettlerBLE" advertising

## Development

### Project Structure
```
.
├── server.py                  # Main Flask app entry point
├── kettler_ble.py             # BlueZ GATT server (D-Bus native)
├── bike_state.py              # In-memory state machine
├── kettler_usb.py             # PySerial communication with bike
├── requirements.txt           # Python dependencies
├── public/
│   └── css/style.css         # Web UI styling
└── views/
    └── index.ejs             # Web dashboard template (Jinja2)
```

### Making Changes

After modifying files, restart the service:
```bash
sudo systemctl restart kettler
journalctl -u kettler -f  # Watch logs
```

### Adding New Features

To add new GATT characteristics with push notifications:
1. Edit `kettler_ble.py` - add characteristic in service methods with `notify_callback`
2. Add notify callback handler to store characteristic reference when client subscribes
3. Add update method (e.g., `_update_new_characteristic()`) with `characteristic.set_value()` call
4. Call update method from `notify_ftms()` when data arrives
5. No rebuild needed - Python!
6. Restart: `sudo systemctl restart kettler`

### Testing Changes

```bash
# Run directly to see all output
python3 server.py

# Or with more debug logging
export PYTHONUNBUFFERED=1
python3 server.py
```

## Known Limitations

- **Single BLE connection** - One fitness app at a time (standard for most trainers)
- **D-Bus latency** - Small delay (~50ms) for GATT operations via D-Bus
- **GPIO button support** - Requires additional RPi.GPIO package (not included by default)
- **Push notifications** - Requires bluezero 0.8.0+ with `set_value()` support

## Performance

On Pi Zero 2W:
- **CPU Usage:** 3-5% (idle), 8-12% (active streaming)
- **Memory:** ~80MB Python + Flask + bluezero
- **Response Time:** <50ms for push notifications via `characteristic.set_value()`
- **Power Consumption:** ~0.5W typical

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Test on real hardware (Pi Zero 2W + Kettler bike)
4. Submit PR with description

## License

MIT License - see LICENSE file

## Credits

- Original Node.js implementation by project contributors
- Python rewrite for better BlueZ D-Bus support
- FTMS specification: Bluetooth SIG
- Community testing and feedback

## Support

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions
- **Wiki:** Project Wiki for advanced topics

---

**Happy cycling! 🚴**
- 40MB RAM usage
- All GATT notifications keep up with 50ms bike update rate

## License

MIT

## Contributing

Found a bug or want to improve? Open an issue or PR on GitHub.

## References

- [Bluetooth FTMS Spec](https://www.bluetooth.com/specifications/gatt/services/)
- [BlueZ Documentation](http://www.bluez.org/)
- [Raspberry Pi OS Docs](https://www.raspberrypi.com/documentation/)
- [GATT Characteristic Specs](https://www.bluetooth.com/specifications/gatt/characteristics/)

---

**Questions?** Check the GitHub issues or run with `python3 server.py` to see real-time output and debug.
