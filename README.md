# super-disco
Inspired by [Look Mum No Computer](https://www.lookmumnocomputer.com/projects#/super-simple-midi-keyboard)'s
[Super Simple MIDI Keyboard project](https://youtu.be/wY1SRehZ9hM), this is my _Not So Super Simple MIDI 
Keyboard_. Rather than an Arduino, it uses a 
[Raspberry PI Pico](https://www.raspberrypi.com/products/raspberry-pi-pico/) running 
[MicroPython](https://www.micropython.org/) and 
[Adafruit NeoPixel arcade buttons](https://learn.adafruit.com/neopixel-arcade-button) rather than plain 
illuminated ones. At some point, I might even get round to sticking an OLED screen in there to add the 
ability to change settings on the fly.


## Checking MIDI messages without connecting to a MIDI enabled device
You can still check that the MIDI messages are being sent on the configured UART pin, by looping that 
back into one of the other UART RX pins. For example, import the `UART` class and configure one of the
RX pins on UART 1:

```python
from machine import Pin, UART

uart_rx = UART(1, UART_BAUD, rx=Pin(5, Pin.IN))
```

Then it's just a matter of reading anything that's sent and decoding it. For example, add this to the
bottom of the infinite `while` loop:

```python
    message = uart_rx.read(3)
    while message:
        print("Received: {} : {}".format("note_on" if message[0] == 0x90 else "note_off", message[1]))
        message = uart_rx.read(3)
```

This should output something along the lines of:

```
Received: note_on : 61
Received: note_off : 61
```

While I'm sure we could do this a better way, this should at least let you see that the messages contains
the correct note. 
