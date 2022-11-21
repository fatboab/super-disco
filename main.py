from machine import Pin
from notes import NoteStack
from rp2 import asm_pio, PIO, StateMachine
from uarray import array
from ustruct import pack
from utime import sleep_ms


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
OCTAVE_BUTTON_UP = 9
OCTAVE_BUTTON_DOWN = 10

# Note buttons that make up the keyboard
NOTE_BUTTON_BASE = 11
NOTE_BUTTON_NUM = 12

# NeoPixels for that bit of pizzazz
NEO_PIXEL_PIN = 8
NEO_PIXEL_BRIGHTNESS = 0.5
NEO_PIXEL_OCTAVE_UP = 0
NEO_PIXEL_OCTAVE_DOWN = 1
NEO_PIXEL_NOTES_START = 2
NEO_PIXELS = array("I", [0 for _ in range(NOTE_BUTTON_NUM + 2)])    # 14 buttons in total...

# Colours
OCTAVE_COLOURS = [
    (27, 158, 119),
    (217, 95, 2),
    (117, 112, 179),
    (231, 41, 138),
    (102, 166, 30)
]

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

    in_(pins, 12)
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


@asm_pio(sideset_init=PIO.OUT_LOW, out_shiftdir=PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def handle_neo_pixels():
    """
    https://github.com/raspberrypi/pico-micropython-examples/blob/master/pio/pio_ws2812.py
    """
    T1 = 2
    T2 = 5
    T3 = 3

    wrap_target()

    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]

    label("do_zero")
    nop()                   .side(0)    [T2 - 1]

    wrap()


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

    return pack("bbb", command, data1, data2)


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


def octave_down_colour():
    octave_exists = MIDI_OCTAVE - 1
    return OCTAVE_COLOURS[octave_exists + 2] if octave_exists in MIDI_OCTAVES else (0, 0, 0)


def octave_up_colour():
    octave_exists = MIDI_OCTAVE + 1
    return OCTAVE_COLOURS[octave_exists + 2] if octave_exists in MIDI_OCTAVES else (0, 0, 0)


def octave_down(_sm):
    """ IRQ handler for the octave down button """
    global MIDI_OCTAVE

    # Calculate the new octave
    new_octave = MIDI_OCTAVE - 1
    if new_octave not in MIDI_OCTAVES:
        new_octave = MIDI_OCTAVES[0]

    if new_octave != MIDI_OCTAVE:
        # Change colour
        pixels_fill_notes(OCTAVE_COLOURS[new_octave + 2])
        pixels_show()

        # Store the new octave, re-trigger any notes that require it and change the NeoPixels
        MIDI_OCTAVE = new_octave
        retrigger_notes()
        pixels_fill_octaves(octave_down_colour(), octave_up_colour())
        pixels_show()


def octave_up(_sm):
    """ IRQ handler for the octave up button """
    global MIDI_OCTAVE

    # Calculate the new octave
    new_octave = MIDI_OCTAVE + 1
    if new_octave not in MIDI_OCTAVES:
        new_octave = MIDI_OCTAVES[len(MIDI_OCTAVES) - 1]

    if new_octave != MIDI_OCTAVE:
        # Change colour
        pixels_fill_notes(OCTAVE_COLOURS[new_octave + 2])
        pixels_show()

        # Store the new octave, re-trigger any notes that require it and change the NeoPixels
        MIDI_OCTAVE = new_octave
        retrigger_notes()
        pixels_fill_octaves(octave_down_colour(), octave_up_colour())
        pixels_show()


def pixels_show():
    # Create a new array and fill it with the same colours, just less bright...
    dimmer_ar = array("I", [0 for _ in range(len(NEO_PIXELS))])
    for i, c in enumerate(NEO_PIXELS):
        r = int(((c >> 8) & 0xFF) * NEO_PIXEL_BRIGHTNESS)
        g = int(((c >> 16) & 0xFF) * NEO_PIXEL_BRIGHTNESS)
        b = int((c & 0xFF) * NEO_PIXEL_BRIGHTNESS)
        dimmer_ar[i] = (g << 16) + (r << 8) + b

    neo_pixel_sm.put(dimmer_ar, 8)
    sleep_ms(10)


def pixels_set(neo_pixel_index, color):
    NEO_PIXELS[neo_pixel_index] = (color[1] << 16) + (color[0] << 8) + color[2]


def pixels_fill_octaves(down_colour, up_colour):
    pixels_set(NEO_PIXEL_OCTAVE_DOWN, down_colour)
    pixels_set(NEO_PIXEL_OCTAVE_UP, up_colour)


def pixels_fill_notes(colour):
    for i in range(NEO_PIXEL_NOTES_START, (NOTE_BUTTON_NUM + NEO_PIXEL_NOTES_START)):
        pixels_set(i, colour)


# State machine to drop the notes an octave
octave_down_sm = StateMachine(0, handle_octave_down_button, freq=2000, in_base=Pin(OCTAVE_BUTTON_DOWN, Pin.IN,
                                                                                   Pin.PULL_DOWN))
octave_down_sm.irq(octave_down)

# State machine to drop the notes an octave
octave_up_sm = StateMachine(1, handle_octave_up_button, freq=2000, in_base=Pin(OCTAVE_BUTTON_UP, Pin.IN, Pin.PULL_DOWN))
octave_up_sm.irq(octave_up)

# State machine to read the value of all the buttons in a oner
note_button_sm = StateMachine(2, handle_note_buttons, freq=2000, in_base=Pin(NOTE_BUTTON_BASE, Pin.IN, Pin.PULL_DOWN))

# State machine to write out the MIDI command over UART
midi_output_sm = StateMachine(3, handle_uart_tx, freq=8 * UART_BAUD, out_base=Pin(UART_TX_PIN, Pin.OUT),
                              sideset_base=Pin(UART_TX_PIN, Pin.OUT))

# StateMachine for controlling all the NeoPixels
neo_pixel_sm = StateMachine(4, handle_neo_pixels, freq=8_000_000, sideset_base=Pin(NEO_PIXEL_PIN))

# Start all the button related state machines
octave_down_sm.active(1)
octave_up_sm.active(1)
note_button_sm.active(1)
midi_output_sm.active(1)
neo_pixel_sm.active(1)

# Initialise the NeoPixels...
pixels_fill_octaves(octave_down_colour(), octave_up_colour())
pixels_fill_notes(OCTAVE_COLOURS[MIDI_OCTAVE + 2])
pixels_show()

while True:
    # Set the latest button state and compare it against the last state we have
    latest_button_state = note_button_sm.get()

    # Bit shift both last and current states to see what's changed, and in what direction
    for button_index in range(NOTE_BUTTON_NUM):
        # Get the button state from each mask
        current = button_state_from_mask(current_active_buttons, button_index)
        latest = button_state_from_mask(latest_button_state, button_index)

        # Work out if we need to send a note on or note off command
        if current ^ latest:
            # Convenience so we only do the + i in one place...
            note = BASE_MIDI_NOTE + button_index

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
