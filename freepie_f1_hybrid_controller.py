"""FreePIE hybrid F1 controller (keyboard -> vJoy) with SimHub telemetry.

Run FreePIE as Administrator so key injection works with the game.
SimHub format (Arduino > Custom Protocol):
format([DataCorePlugin.GameData.SpeedKmh],'0')+','+format([DataCorePlugin.GameData.Rpms],'0')+','+format([DataCorePlugin.GameData.MaxRpm],'0')+','+[DataCorePlugin.GameData.Gear]
Example: 250,11800,13000,6
"""

# FreePIE script entry point
if starting:
    # Serial telemetry
    serial_port_name = "COM4"
    serial_baud = 115200
    serial_connected = False
    serial_last_line = ""
    serial_fail_count = 0
    serial_fail_limit = 10
    last_telemetry_time = 0.0
    telemetry_timeout_s = 0.35

    # Telemetry state
    speed = 0.0
    rpm = 0.0
    max_rpm = 13000.0
    gear_num = 1

    # Prediction state (fallback)
    predicted_rpm = 0.0
    predicted_speed = 0.0
    throttle_hold_time = 0.0
    last_space_state = False

    # Throttle control
    throttle_output = 0.0
    throttle_ramp_per_s = 3.5  # fast ramp to gear target
    throttle_release_per_s = 7.0
    punch_ratio = 0.70  # 70% of gear limit

    # Shift control
    is_shifting = False
    shift_end_time = 0.0
    shift_cooldown_s = 0.20
    upshift_rpm = 12200.0
    downshift_rpm = 4500.0

    # vJoy
    v_joy = 0.0

    # Attempt to open serial on startup
    try:
        serial.open(serial_port_name, serial_baud)
        serial_connected = True
    except:
        serial_connected = False

# Helper: gear-based throttle limit
def gear_throttle_limit(gear_value):
    if gear_value <= 1:
        return 0.65
    if gear_value == 2:
        return 0.85
    return 1.0

# Helper: parse telemetry line
def parse_telemetry(line):
    parts = line.strip().split(",")
    if len(parts) != 4:
        return None
    try:
        parsed_speed = float(parts[0])
        parsed_rpm = float(parts[1])
        parsed_max_rpm = float(parts[2])
        parsed_gear = int(parts[3])
        return (parsed_speed, parsed_rpm, parsed_max_rpm, parsed_gear)
    except:
        return None

now = time.time()

# Read telemetry when available
if serial_connected:
    try:
        while serial.available() > 0:
            serial_last_line = serial.readLine()
        if serial_last_line:
            parsed = parse_telemetry(serial_last_line)
            if parsed:
                speed, rpm, max_rpm, gear_num = parsed
                last_telemetry_time = now
                serial_fail_count = 0
            else:
                serial_fail_count += 1
    except:
        serial_fail_count += 1

telemetry_ok = (now - last_telemetry_time) <= telemetry_timeout_s and serial_fail_count < serial_fail_limit

# Fallback prediction if telemetry fails
space_pressed = keyboard.getKeyDown(Key.Space)
if space_pressed:
    throttle_hold_time += time.delta
else:
    throttle_hold_time = 0.0

if not telemetry_ok:
    # Simple physics-inspired estimate based on throttle hold duration
    predicted_rpm = min(13500.0, predicted_rpm + (6000.0 * throttle_hold_time * time.delta))
    predicted_rpm = max(1000.0, predicted_rpm - (4500.0 * (1.0 - throttle_output) * time.delta))
    predicted_speed = max(0.0, predicted_speed + (20.0 * throttle_output * time.delta) - (15.0 * (1.0 - throttle_output) * time.delta))
    rpm = predicted_rpm
    speed = predicted_speed

# Shift logic with debounce
if is_shifting and now >= shift_end_time:
    is_shifting = False

braking = keyboard.getKeyDown(Key.Down)
if not is_shifting:
    if rpm >= upshift_rpm:
        keyboard.setKeyDown(Key.Up)
        time.delay(50)
        keyboard.setKeyUp(Key.Up)
        is_shifting = True
        shift_end_time = now + shift_cooldown_s
    elif rpm <= downshift_rpm and braking:
        keyboard.setKeyDown(Key.Down)
        time.delay(50)
        keyboard.setKeyUp(Key.Down)
        is_shifting = True
        shift_end_time = now + shift_cooldown_s

# Throttle logic
gear_limit = gear_throttle_limit(gear_num)
target_throttle = gear_limit if space_pressed else 0.0

if space_pressed and not last_space_state:
    # Punch start: jump to 70% of gear limit
    throttle_output = max(throttle_output, gear_limit * punch_ratio)

if space_pressed:
    throttle_output = min(target_throttle, throttle_output + throttle_ramp_per_s * time.delta)
else:
    throttle_output = max(0.0, throttle_output - throttle_release_per_s * time.delta)

last_space_state = space_pressed

# Send to vJoy
v_joy = throttle_output
vJoy[0].y = v_joy

# Diagnostics
diagnostics.watch(v_joy)
diagnostics.watch(gear_num)
diagnostics.watch(rpm)
diagnostics.watch(speed)
