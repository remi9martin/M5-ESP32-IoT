"""
BALA-C Plus - Dance Bot
========================
Device: BALA-C Plus (ESP32 self-balancing)
Difficulty: Easy

Pre-programmed dance moves synced to timing.
Leans, spins, and pulses to the beat!
"""

import time
from machine import Pin, I2C

try:
    from m5stack import BalaC
    bala = BalaC()
    HAS_BALA = True
except:
    HAS_BALA = False

# Dance moves
MOVE_LEAN_LEFT = 0
MOVE_LEAN_RIGHT = 1
MOVE_SPIN_CW = 2
MOVE_SPIN_CCW = 3
MOVE_PULSE = 4
MOVE_REST = 5

def execute_move(move, speed=50):
    if not HAS_BALA:
        moves = ["LEAN_L", "LEAN_R", "SPIN_CW", "SPIN_CCW", "PULSE", "REST"]
        print(f"  {moves[move]}")
        return
    
    if move == MOVE_LEAN_LEFT:
        bala.set_motor(-speed, speed)
    elif move == MOVE_LEAN_RIGHT:
        bala.set_motor(speed, -speed)
    elif move == MOVE_SPIN_CW:
        bala.set_motor(speed, speed)
    elif move == MOVE_SPIN_CCW:
        bala.set_motor(-speed, -speed)
    elif move == MOVE_PULSE:
        bala.set_motor(speed, -speed)
        time.sleep(0.1)
        bala.set_motor(-speed, speed)
    else:
        bala.set_motor(0, 0)

# Dance choreography (move, duration in beats)
DANCE = [
    (MOVE_REST, 2),
    (MOVE_LEAN_LEFT, 1),
    (MOVE_LEAN_RIGHT, 1),
    (MOVE_LEAN_LEFT, 1),
    (MOVE_LEAN_RIGHT, 1),
    (MOVE_SPIN_CW, 2),
    (MOVE_PULSE, 1),
    (MOVE_PULSE, 1),
    (MOVE_SPIN_CCW, 2),
    (MOVE_REST, 1),
    (MOVE_PULSE, 0.5),
    (MOVE_PULSE, 0.5),
    (MOVE_PULSE, 0.5),
    (MOVE_PULSE, 0.5),
    (MOVE_SPIN_CW, 4),
    (MOVE_REST, 2),
]

def main():
    print("BALA-C Dance Bot!")
    print("Starting dance sequence...\n")
    
    BPM = 120  # Beats per minute
    beat_time = 60 / BPM  # Seconds per beat
    
    try:
        while True:
            print("--- Dance Start ---")
            for move, beats in DANCE:
                execute_move(move)
                time.sleep(beat_time * beats)
            
            execute_move(MOVE_REST)
            print("--- Loop ---\n")
            time.sleep(1)
            
    except KeyboardInterrupt:
        if HAS_BALA:
            bala.set_motor(0, 0)
        print("\nDance stopped!")

if __name__ == "__main__":
    main()
