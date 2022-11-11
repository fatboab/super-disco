from machine import Pin
from rp2 import asm_pio, PIO, StateMachine
import ustruct


# UART settings for sending the MIDI commands.
UART_BAUD = 31250
UART_TX_PIN = 0

# MIDI settings.
MIDI_CHANNEL = 1
MIDI_COMMANDS = (
    0x80,  # Note Off
    0x90,  # Note On
)
MIDI_OCTAVE = 0
MIDI_OCTAVES = (-2, -1, 0, 1, 2)

# The MIDI note of our first button in octave 0. For us, this is Middle C, or 60.
BASE_MIDI_NOTE = 60

# The number of note buttons in the keyboard
NUM_BUTTONS = 4


@asm_pio(out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT, sideset_init=PIO.OUT_HIGH)
def uart_tx():
    """
    https://github.com/raspberrypi/pico-micropython-examples/blob/master/pio/pio_uart_tx.py
    """
    # Block with TX deasserted until data available
    pull()
    # Initialise bit counter, assert start bit for 8 cycles
    set(x, 7)  .side(0)       [7]
    # Shift out 8 data bits, 8 execution cycles per bit
    label("bitloop")
    out(pins, 1)              [6]
    jmp(x_dec, "bitloop")
    # Assert stop bit for 8 cycles total (incl 1 for pull())
    nop()      .side(1)       [6]


@asm_pio(set_init=(PIO.IN_LOW) * NUM_BUTTONS, in_shiftdir=PIO.SHIFT_LEFT)
def note_buttons():
    """ State machine function to read the state of all note buttons at once."""
    wrap_target()

    in_(pins, 4)
    mov(x, isr)
    jmp(x_not_y, "push")
    jmp("clear_isr")

    label("push")
    mov(y, x)
    push()

    label("clear_isr")
    set(x, 0)
    mov(isr, x)

    wrap()


@asm_pio(set_init=PIO.OUT_LOW)
def led_off():
    """ State machine function to set a pin low. """
    set(pins, 0)


@asm_pio(set_init=PIO.OUT_LOW)
def led_on():
    """ State machine function to set a pin high. """
    set(pins, 1)


def button_state_from_mask(mask,  bit) -> int:
    """Returns the set state of the bit within the bit mask; 1 is set, 0 otherwise"""
    return (mask >> bit) & 1


def construct_midi_message(command, data1, data2=0) -> bytes:
    """Creates a packed ustruct containing the midi message to send via UART."""
    if command not in MIDI_COMMANDS:
        raise ValueError("Invalid Command: {}".format(command))

    # Change the channel if necessary...
    command += MIDI_CHANNEL - 1

    return ustruct.pack("bbb", command, data1, data2)


def apply_octave(note) -> int:
    if MIDI_OCTAVE not in MIDI_OCTAVES:
        raise ValueError("Octave {}, not supported".format(MIDI_OCTAVE))

    return note + (MIDI_OCTAVE * 12)


def note_off(note, velocity=0) -> bytes:
    """Construct a 'Note Off' message"""
    return construct_midi_message(0x80, apply_octave(note), velocity)


def note_on(note, velocity=127) -> bytes:
    """Construct a 'Note On' message"""
    return construct_midi_message(0x90, apply_octave(note), velocity)


# State machine to write out the MIDI command over UART
state_machine_1 = StateMachine(1, uart_tx, freq=8 * UART_BAUD, out_base=Pin(UART_TX_PIN, Pin.OUT),
                               sideset_base=Pin(UART_TX_PIN, Pin.OUT))

# State machine to read the value of all the buttons in a oner...
state_machine_2 = StateMachine(2, note_buttons, freq=2000, in_base=Pin(9, Pin.IN, Pin.PULL_DOWN))

# Simple dual state machine LED blinking...
state_machine_3 = StateMachine(5, led_off, freq=20000, set_base=Pin(25))
state_machine_4 = StateMachine(6, led_on, freq=20002, set_base=Pin(25))


state_machine_1.active(1)
state_machine_2.active(1)
state_machine_3.active(1)
state_machine_4.active(0)

current_active_buttons = 0

while True:
    # Set the latest button state and compare it against the last state we have
    latest_button_state = state_machine_2.get()

    # Bit shift both last and current states to see what's changed, and in what direction
    for i in range(NUM_BUTTONS):
        # Get the button state from each mask
        current = button_state_from_mask(current_active_buttons, i)
        latest = button_state_from_mask(latest_button_state, i)

        # Work out if we need to send a note on or note off command
        if current ^ latest:
            midi_message = note_on(BASE_MIDI_NOTE + i) if latest & 1 else note_off(BASE_MIDI_NOTE + i)
            state_machine_1.put(midi_message)

    # Store the current state of the buttons
    current_active_buttons = latest_button_state

    # Fiddle the LED if any note is on
    state_machine_4.active(1 if current_active_buttons else 0)
