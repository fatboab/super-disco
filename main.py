from machine import Pin, PWM
import utime

led = Pin(25, Pin.OUT)


# https://projects.raspberrypi.org/en/projects/getting-started-with-the-pico/5
def simple_blink():
    while True:
        led.toggle()
        utime.sleep(1)


# https://projects.raspberrypi.org/en/projects/getting-started-with-the-pico/7
def pwm_fade_in_fade_out():
    # Construct PWM object, with LED on Pin(25), also set the PWM frequency...
    pwm = PWM(led)
    pwm.freq(1000)

    while True:
        # Fade the LED in and out...
        for duty in range(65025):
            pwm.duty_u16(duty)
            utime.sleep(0.0001)
        for duty in range(65025, 0, -1):
            pwm.duty_u16(duty)
            utime.sleep(0.0001)


# https://github.com/micropython/micropython/blob/master/examples/rp2/pwm_fade.py
def pwm_periodic_flash():
    # Construct PWM object, with LED on Pin(25), also set the PWM frequency...
    pwm = PWM(led)
    pwm.freq(1000)

    while True:
        # Fade the LED in and out a few times.
        duty = 0
        direction = 1
        for _ in range(8 * 256):
            duty += direction
            if duty > 255:
                duty = 255
                direction = -1
            elif duty < 0:
                duty = 0
                direction = 1
            pwm.duty_u16(duty * duty)
            utime.sleep(0.001)

        utime.sleep(1)


# simple_blink()
# pwm_fade_in_fade_out()
pwm_periodic_flash()
