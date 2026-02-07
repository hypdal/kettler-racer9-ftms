#!/usr/bin/env python3
"""
Kettler Speed Calibration Analyzer
Analyzes the relationship between RPM and Speed from USB data
"""

import re
import sys

def analyze_logs(log_lines):
    """Analyze Kettler USB data for speed/RPM correlation"""
    
    data_points = []
    
    # Parse log lines
    for line in log_lines:
        # Look for read lines with data
        # Format: [INFO] [KettlerUSB] read [996ms]: 000   057     122     000     035     0002   00:19    035
        match = re.search(r'read \[\d+ms\]:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d:]+)\s+(\d+)', line)
        
        if match:
            hr = int(match.group(1))
            rpm = int(match.group(2))
            speed_raw = int(match.group(3))
            distance = int(match.group(4))
            target_power = int(match.group(5))
            energy = int(match.group(6))
            time_str = match.group(7)
            current_power = int(match.group(8))
            
            # Speed in km/h (Kettler sends in 0.1 km/h)
            speed_kmh = speed_raw * 0.1
            
            # Skip zero values
            if rpm > 0 and speed_kmh > 0:
                data_points.append({
                    'rpm': rpm,
                    'speed': speed_kmh,
                    'power': current_power,
                    'ratio': speed_kmh / rpm if rpm > 0 else 0
                })
    
    if not data_points:
        print("❌ No valid data points found in logs!")
        return
    
    # Analysis
    print("\n" + "="*80)
    print("KETTLER SPEED ANALYSIS")
    print("="*80)
    
    print(f"\n📊 Found {len(data_points)} data points")
    
    # Calculate statistics
    ratios = [p['ratio'] for p in data_points]
    avg_ratio = sum(ratios) / len(ratios)
    min_ratio = min(ratios)
    max_ratio = max(ratios)
    
    print(f"\n🔢 Speed/RPM Ratio Statistics:")
    print(f"   Average: {avg_ratio:.3f} km/h per RPM")
    print(f"   Min:     {min_ratio:.3f}")
    print(f"   Max:     {max_ratio:.3f}")
    print(f"   Variation: {(max_ratio - min_ratio):.3f}")
    
    # Expected ratio for typical bike
    # At 90 RPM on a road bike: ~36 km/h → ratio ~0.4
    # At 60 RPM: ~24 km/h → ratio ~0.4
    print(f"\n💡 Expected ratio for typical bike: 0.3-0.5 km/h per RPM")
    
    if avg_ratio < 0.15:
        print(f"\n⚠️  WARNING: Ratio is VERY LOW ({avg_ratio:.3f})")
        print(f"   This means Kettler is reporting unrealistically low speeds!")
        print(f"   Possible causes:")
        print(f"   • Wrong wheel circumference setting in Kettler")
        print(f"   • Kettler speed sensor misconfigured")
        print(f"   • Speed value means something else (not actual speed)")
    elif avg_ratio > 0.6:
        print(f"\n⚠️  WARNING: Ratio is VERY HIGH ({avg_ratio:.3f})")
        print(f"   This means Kettler is reporting unrealistically high speeds!")
    else:
        print(f"\n✅ Ratio looks reasonable")
    
    # Sample data points
    print(f"\n📋 Sample Data Points:")
    print(f"{'RPM':<8} {'Speed (km/h)':<15} {'Power (W)':<12} {'Ratio':<10}")
    print("-" * 80)
    
    # Show every 5th point or max 20 points
    step = max(1, len(data_points) // 20)
    for i in range(0, len(data_points), step):
        p = data_points[i]
        print(f"{p['rpm']:<8} {p['speed']:<15.1f} {p['power']:<12} {p['ratio']:<10.3f}")
    
    # Speed calculation recommendation
    print("\n" + "="*80)
    print("RECOMMENDED FIX")
    print("="*80)
    
    if avg_ratio < 0.25:
        # Speed too low - need multiplier
        multiplier = 0.35 / avg_ratio  # Target ratio of 0.35
        print(f"\n🔧 Speed is too LOW by a factor of {multiplier:.2f}x")
        print(f"\nOption 1: Multiply Kettler speed in BLE transmission:")
        print(f"   In KettlerBLE.py, change line ~208:")
        print(f"   speed = data.get('speed', 0)")
        print(f"   speed_value = int(speed * 100 * {multiplier:.2f})  # ← Apply multiplier")
        
        print(f"\nOption 2: Fix in Kettler USB parser:")
        print(f"   In KettlerUSB.py, change line ~59:")
        print(f"   speed = int(states[2])")
        print(f"   data_out['speed'] = speed * 0.1 * {multiplier:.2f}  # ← Apply multiplier")
        
        print(f"\n💡 With this fix:")
        print(f"   60 RPM would show ~{60 * avg_ratio * multiplier:.1f} km/h (currently {60 * avg_ratio:.1f} km/h)")
        
    elif avg_ratio > 0.5:
        # Speed too high
        multiplier = 0.35 / avg_ratio
        print(f"\n🔧 Speed is too HIGH by a factor of {1/multiplier:.2f}x")
        print(f"   Apply multiplier of {multiplier:.2f}")
    else:
        print(f"\n✅ Speed values look correct!")
        print(f"   The problem might be elsewhere (BLE transmission, Kinomap settings)")
    
    # Alternative: Calculate speed from RPM
    print(f"\n" + "="*80)
    print("ALTERNATIVE: Calculate Speed from RPM")
    print("="*80)
    print(f"\nInstead of using Kettler's speed, calculate it from RPM:")
    print(f"\nIn KettlerBLE.py _update_indoor_bike_data(), replace:")
    print(f"   speed = data.get('speed', 0)")
    print(f"\nWith:")
    print(f"   # Calculate speed from RPM (assumes ~2.1m wheel circumference)")
    print(f"   rpm = data.get('rpm', 0)")
    print(f"   wheel_circumference_m = 2.1  # Adjust based on your setup")
    print(f"   speed = (rpm * wheel_circumference_m * 60) / 1000  # km/h")
    
    print("\n" + "="*80)

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║            KETTLER SPEED CALIBRATION ANALYZER                        ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) > 1:
        # Read from file
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            print(f"📁 Analyzing log file: {filename}")
            analyze_logs(lines)
        except FileNotFoundError:
            print(f"❌ File not found: {filename}")
            sys.exit(1)
    else:
        # Read from stdin
        print("📋 Paste your log output (Ctrl+D when done):")
        print("-" * 80)
        lines = sys.stdin.readlines()
        analyze_logs(lines)

if __name__ == '__main__':
    main()