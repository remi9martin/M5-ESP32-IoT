"""
BALA2 Fire - Guard Dog Mode
============================
Device: BALA2 Fire (M5Fire + self-balancing base)
Difficulty: Medium

Balances in place, uses IMU to detect motion.
Spins toward detected motion, buzzer "barks"!
"""

import time
from machine import Pin, PWM

try:
    from m5stack import Bala2, IMU
    bala = Bala2()
    imu = IMU()
    HAS_BALA = True
except:
    HAS_BALA = False

try:
    buzzer = PWM(Pin(25), freq=500, duty=0)
except:
    buzzer = None

# Detection thresholds
MOTION_THRESH = 0.3  # Gyro threshold
BARK_DURATION = 0.5

alert_mode = False
last_gyro = [0, 0, 0]

def bark():
    """Sound the alarm!"""
    print("BARK! BARK!")
    if buzzer:
        for _ in range(3):
            buzzer.freq(800)
            buzzer.duty(512)
            time.sleep(0.1)
            buzzer.freq(400)
            time.sleep(0.1)
        buzzer.duty(0)

def spin_toward(direction):
    """Spin toward detected motion"""
    speed = 60
    if HAS_BALA:
        if direction > 0:
            bala.set_motor(speed, -speed)
        else:
            bala.set_motor(-speed, speed)
        time.sleep(0.3)
        bala.set_motor(0, 0)
    print(f"Spinning {'left' if direction < 0 else 'right'}")

def read_gyro():
    if HAS_BALA:
        return imu.gyro()
    import random
    return [random.uniform(-0.5, 0.5) for _ in range(3)]

def detect_motion():
    global last_gyro
    gyro = read_gyro()
    
    # Check for significant change
    dx = abs(gyro[0] - last_gyro[0])
    dy = abs(gyro[1] - last_gyro[1])
    
    last_gyro = gyro
    
    if dx > MOTION_THRESH or dy > MOTION_THRESH:
        return gyro[0]  # Return direction
    return 0

def main():
    print("BALA2 Guard Dog Mode")
    print("Watching for motion...\n")
    
    try:
        while True:
            motion = detect_motion()
            
            if abs(motion) > 0:
                print(f"Motion detected!")
                bark()
                spin_toward(motion)
                time.sleep(1)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        if buzzer:
            buzzer.duty(0)
        if HAS_BALA:
            bala.set_motor(0, 0)
        print("Guard dog off duty!")

if __name__ == "__main__":
    main()
