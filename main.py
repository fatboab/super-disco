from machine import Pin, UART
from midi import Controller


class Note:
    def __init__(self, mask, midi):
        self.mask = mask
        self.midi = midi

    def __repr__(self):
        return '<Note: mask: {mask} midi: {midi}>'.format(
            mask=self.mask,
            midi=self.midi
        )


class Button:
    def __init__(self, pin, note, initial_state=0):
        self.pin = pin
        self.note = note
        self.state = initial_state

    def __repr__(self):
        return '<Button: pin: {pin} note: {note} state: {state}>'.format(
            pin=self.pin,
            note=self.note,
            state=self.state
        )


# MIDI controller, defaults to channel 1...
midi_tx_pin = UART(0, baudrate=31250, tx=Pin(0))
controller = Controller(midi_tx_pin)

# Assume we're using the octave of C4 (middle C), where A4 is 440 Hz. So the MIDI key range is 60 - 71...
NOTE_C = Note(int('000000000001', 2), 60)
NOTE_CS = Note(int('000000000010', 2), 61)
NOTE_D = Note(int('000000000100', 2), 62)
NOTE_DS = Note(int('000000001000', 2), 63)
NOTE_E = Note(int('000000010000', 2), 64)
NOTE_F = Note(int('000000100000', 2), 65)
NOTE_FS = Note(int('000001000000', 2), 66)
NOTE_G = Note(int('000010000000', 2), 67)
NOTE_GS = Note(int('000100000000', 2), 68)
NOTE_A = Note(int('001000000000', 2), 69)
NOTE_AS = Note(int('010000000000', 2), 70)
NOTE_B = Note(int('100000000000', 2), 71)

buttons = [
    Button(Pin(16, Pin.IN, Pin.PULL_DOWN), NOTE_C),
    Button(Pin(17, Pin.IN, Pin.PULL_DOWN), NOTE_D),
    Button(Pin(18, Pin.IN, Pin.PULL_DOWN), NOTE_E),
    Button(Pin(19, Pin.IN, Pin.PULL_DOWN), NOTE_F)
]

note_mask = int('000000000000', 2)

led = Pin(25, Pin.OUT)

while True:
    # Iterate over the buttons...
    for button in buttons:
        new_state = button.pin.value()

        # If the button state has changed, then update the LED state...
        if button.state != new_state:
            # Store the new state...
            button.state = new_state

            # Update the note mask to indicate teh change in state of this button...
            note_mask ^= button.note.mask

            # Send either an on or off command...
            controller.note_on(button.note.midi) if button.state else controller.note_off(button.note.midi)

    # Switch the LED on if any buttons are pressed, switch it off otherwise...
    led.high() if note_mask else led.low()
