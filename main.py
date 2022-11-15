from machine import Pin
from notes import NoteStack
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

# Two octave buttons
OCTAVE_BUTTON_DOWN = 9
OCTAVE_BUTTON_UP = 10

# Note buttons that make up the keyboard
NOTE_BUTTON_BASE = 11
NOTE_BUTTON_NUM = 2

current_active_buttons = 0
note_stack = NoteStack(behaviour=NoteStack.BEHAVIOUR_RETRIGGER_LAST)


@asm_pio(set_init=PIO.IN_LOW)
def handle_octave_down_button():
    """" State machine to handle the down octave button """
    wrap_target()

    wait(1, pin, 0)
    irq(block, rel(0))
    wait(0, pin, 0)

    wrap()


@asm_pio(set_init=PIO.IN_LOW)
def handle_octave_up_button():
    """" State machine to handle the down octave button """
    wrap_target()

    wait(1, pin, 0)
    irq(block, rel(0))
    wait(0, pin, 0)
    irq(clear, rel(0))

    wrap()


@asm_pio(set_init=(PIO.IN_LOW) * NOTE_BUTTON_NUM, in_shiftdir=PIO.SHIFT_LEFT)
def handle_note_buttons():
    """ State machine function to read the state of all note buttons at once."""
    wrap_target()

    in_(pins, 2)
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


@asm_pio(out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT, sideset_init=PIO.OUT_HIGH)
def handle_uart_tx():
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


def apply_octave(note, octave) -> int:
    return note + (octave * 12)


def construct_midi_message(command, data1, data2=0) -> bytes:
    """Creates a packed ustruct containing the midi message to send via UART."""
    if command not in MIDI_COMMANDS:
        raise ValueError("Invalid Command: {}".format(command))

    # Change the channel if necessary...
    command += MIDI_CHANNEL - 1

    return ustruct.pack("bbb", command, data1, data2)


def note_off(note, velocity=0) -> bytes:
    """Construct a 'Note Off' message"""
    return construct_midi_message(0x80, note, velocity)


def note_on(note, velocity=127) -> bytes:
    """Construct a 'Note On' message"""
    return construct_midi_message(0x90, note, velocity)


def retrigger_notes():
    """
    Do we need to re-trigger any notes...? I.e. send note off in their current octave and then send a note on in the
    current octave.
    :return:
    """
    notes = note_stack.notes_to_retrigger()
    for (note, octave) in notes:
        # Send the note off
        midi_message = note_off(apply_octave(note, octave))
        midi_output_sm.put(midi_message)

        # Send the note on message
        midi_message = note_on(apply_octave(note, MIDI_OCTAVE))
        midi_output_sm.put(midi_message)

        # Replace the re-triggered note in the note stack
        note_stack.replace(note, MIDI_OCTAVE)


def octave_down(_sm):
    """ IRQ handler for the octave down button """
    global MIDI_OCTAVE

    # Calculate the new octave
    new_octave = MIDI_OCTAVE - 1
    if new_octave not in MIDI_OCTAVES:
        new_octave = MIDI_OCTAVES[0]

    if new_octave != MIDI_OCTAVE:
        # Store the new octave and re-trigger any notes that require it
        MIDI_OCTAVE = new_octave
        retrigger_notes()


def octave_up(_sm):
    """ IRQ handler for the octave up button """
    global MIDI_OCTAVE

    # Calculate the new octave
    new_octave = MIDI_OCTAVE + 1
    if new_octave not in MIDI_OCTAVES:
        new_octave = MIDI_OCTAVES[len(MIDI_OCTAVES) - 1]

    if new_octave != MIDI_OCTAVE:
        # Store the new octave and re-trigger any notes that require it
        MIDI_OCTAVE = new_octave
        retrigger_notes()


# State machine to drop the notes an octave
octave_down_sm = StateMachine(1, handle_octave_down_button, freq=2000, in_base=Pin(OCTAVE_BUTTON_DOWN, Pin.IN,
                                                                                   Pin.PULL_DOWN))
octave_down_sm.irq(octave_down)

# State machine to drop the notes an octave
octave_up_sm = StateMachine(2, handle_octave_up_button, freq=2000, in_base=Pin(OCTAVE_BUTTON_UP, Pin.IN, Pin.PULL_DOWN))
octave_up_sm.irq(octave_up)

# State machine to read the value of all the buttons in a oner
note_button_sm = StateMachine(3, handle_note_buttons, freq=2000, in_base=Pin(NOTE_BUTTON_BASE, Pin.IN, Pin.PULL_DOWN))

# State machine to write out the MIDI command over UART
midi_output_sm = StateMachine(4, handle_uart_tx, freq=8 * UART_BAUD, out_base=Pin(UART_TX_PIN, Pin.OUT),
                              sideset_base=Pin(UART_TX_PIN, Pin.OUT))

# Start all the button related state machines
octave_down_sm.active(1)
octave_up_sm.active(1)
note_button_sm.active(1)
midi_output_sm.active(1)

# Simple dual state machine LED blinking...
state_machine_3 = StateMachine(5, led_off, freq=20000, set_base=Pin(25))
state_machine_3.active(1)
state_machine_4 = StateMachine(6, led_on, freq=20002, set_base=Pin(25))
state_machine_4.active(0)

while True:
    # Set the latest button state and compare it against the last state we have
    latest_button_state = note_button_sm.get()

    # Bit shift both last and current states to see what's changed, and in what direction
    for i in range(NOTE_BUTTON_NUM):
        # Get the button state from each mask
        current = button_state_from_mask(current_active_buttons, i)
        latest = button_state_from_mask(latest_button_state, i)

        # Work out if we need to send a note on or note off command
        if current ^ latest:
            # Convenience so we only do the + i in one place...
            note = BASE_MIDI_NOTE + i

            # Generate a midi message and send it
            if latest & 1:
                # Create the MIDI message and send it
                midi_message = note_on(apply_octave(note, MIDI_OCTAVE))
                midi_output_sm.put(midi_message)

                # Add the note details to the note stack
                note_stack.add(note, MIDI_OCTAVE)
            else:
                # Remove the note details to the note stack
                removed = note_stack.remove(note)

                # Create the MIDI message and send it, don't assume we're still in the same octave
                midi_message = note_off(apply_octave(removed.note, removed.octave))
                midi_output_sm.put(midi_message)

    # Store the current state of the buttons
    current_active_buttons = latest_button_state

    # Fiddle the LED if any note is on
    state_machine_4.active(1 if current_active_buttons else 0)
