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
MIDI_OCTAVE = 2

# The MIDI note of our first button in octave 0. For us, this is Middle C, or 60.
BASE_MIDI_NOTE = 60

# The number of note buttons in the keyboard
NUM_BUTTONS = 4


@asm_pio(out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT, sideset_init=PIO.OUT_HIGH)
def uart_tx():
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


@asm_pio(set_init=PIO.OUT_LOW)
def led_off():
    """ State machine function to set a pin low. """
    set(pins, 0)


@asm_pio(set_init=PIO.OUT_LOW)
def led_on():
    """ State machine function to set a pin high. """
    set(pins, 1)


@asm_pio(set_init=(PIO.IN_LOW) * NUM_BUTTONS, in_shiftdir=PIO.SHIFT_LEFT)
def note_buttons():
    """ State machine function to read the state of all note buttons at once. """
    in_(pins, 4)
    push()


def button_changed(mask,  bit) -> int:
    """Returns the set state of the bit within the bit mask; 1 is set, 0 otherwise"""
    return (mask >> bit) & 1


def determine_midi_command(current_mask, new_mask, bit) -> str:
    """Given the bit masks of the current and new state of the buttons, determines if we need to issue a note_on or
    note_off MIDI message for the named bit."""
    current = button_changed(current_mask, bit)
    new = button_changed(new_mask, bit)

    return "note_off" if new < current else "note_on"


def construct_midi_message(command, data1, data2=0) -> bytes:
    """Creates a packed ustruct containing the midi message to send via UART."""
    if command not in MIDI_COMMANDS:
        raise ValueError("Invalid Command: {}".format(command))

    command += MIDI_CHANNEL - 1

    return ustruct.pack("bbb", command, data1, data2)


def apply_octave(note) -> int:
    if MIDI_OCTAVE not in (-2, -1, 0, 1, 2):
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
state_machine_2 = StateMachine(2, note_buttons, freq=20000, in_base=Pin(9, Pin.IN, Pin.PULL_DOWN))

# Simple dual state machine LED blinking...
state_machine_3 = StateMachine(5, led_off, freq=20000, set_base=Pin(25))
state_machine_4 = StateMachine(6, led_on, freq=20002, set_base=Pin(25))


state_machine_1.active(1)
state_machine_2.active(1)
state_machine_3.active(1)
state_machine_4.active(0)

current_active_buttons = 0

while True:
    latest_button_state = state_machine_2.get()

    if current_active_buttons != latest_button_state:
        # print("Input (PIO): {0:04b} ({0})".format(latest_button_state))

        # We only need to know about buttons that have changed state...
        changed_button_mask = current_active_buttons ^ latest_button_state
        # print("Changed button mask: {0:04b} ({0})".format(changed_button_mask))

        for i in range(NUM_BUTTONS):
            # print("bit {} on - {}".format(i, bool(bit_on(changed_buttons, i))))
            if button_changed(changed_button_mask, i):
                midi_command = determine_midi_command(current_active_buttons, latest_button_state, i)
                # print("Button {} midi message to send - {}".format(i, midi_command))

                midi_message = globals()[midi_command](BASE_MIDI_NOTE + i)
                # print("MIDI message: {}".format(midi_message))

                state_machine_1.put(midi_message)

        # Store the current state of the buttons...
        current_active_buttons = latest_button_state

    state_machine_4.active(1 if current_active_buttons else 0)
