from machine import Pin


class Button:
    def __init__(self, pin, initial_state=0):
        self.pin = pin
        self.state = initial_state


led = Pin(25, Pin.OUT)

buttons = [
    Button(Pin(16, Pin.IN, Pin.PULL_DOWN)),
    Button(Pin(17, Pin.IN, Pin.PULL_DOWN)),
    Button(Pin(18, Pin.IN, Pin.PULL_DOWN)),
    Button(Pin(19, Pin.IN, Pin.PULL_DOWN))
]

pressed = 0

while True:
    # Iterate over the buttons...
    for button in buttons:
        new_state = button.pin.value()

        # If the button state has changed, then update the LED state...
        if button.state != new_state:
            button.state = new_state
            pressed += 1 if button.state else -1

    # Switch the LED on if any buttons are pressed, switch it off otherwise...
    led.high() if pressed else led.low()
