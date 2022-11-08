"""
Inspired by Craig Barnes MIDI library - https://github.com/cjbarnes18/micropython-midi/blob/master/midi.py, this one
works on the Raspberry Pi Pico via UART. It only implements note on/off commands. Each midi message consists of 3 bytes.
The first byte is the sum of the command and the midi channel (1-16 > 0-F). The value of bytes 2 and 3 (data 1 and 2)
are dependent on the command:

command     data1           data2                  Description
---------   -------------   --------------------   -----------
0x80-0x8F   Key # (0-127)   Off Velocity (0-127)   Note Off
0x90-0x90   Key # (0-127)   On Velocity (0-127)    Note On

http://www.midi.org/techspecs/midimessages.php
"""

import ustruct


class Controller:
    """
    Usage
    =====
    The following example creates a controller on midi channel one using the RPi Pico UART. Then it sends a note on
    message followed by a note off message.

        >>> from machine import Pin, UART
        >>> import utime
        >>> controller = Controller(UART(0, baudrate=31250, tx=Pin(0)), 1)
        >>> controller.note_on(65)
        >>> utime.sleep(0.1)
        >>> controller.note_off(65)
    """

    COMMANDS = (
        0x80,  # Note Off
        0x90,  # Note On
    )

    def __init__(self, uart, channel=1):
        try:
            assert 1 <= channel <= 16
        except AssertionError:
            raise ValueError('channel should be an integer between 1 and 16')

        self.uart = uart
        self.channel = channel

    def __repr__(self):
        return '<Controller: uart: {uart} channel: {channel}>'.format(
            uart=self.uart,
            channel=self.channel
        )

    def send_message(self, command, data1, data2=0):
        """Send a midi message to the serial device."""
        if command not in self.COMMANDS:
            raise ValueError('Invalid Command: {}'.format(command))

        command += self.channel - 1

        self.uart.write(ustruct.pack("bbb", command, data1, data2))

    def note_off(self, note, velocity=0):
        """Send a 'Note Off'  message"""
        self.send_message(0x80, note, velocity)

    def note_on(self, note, velocity=127):
        """Send a 'Note On' message"""
        self.send_message(0x90, note, velocity)
