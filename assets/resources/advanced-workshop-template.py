'''
for frambuf docs: https://docs.micropython.org/en/latest/library/framebuf.html
command bytes   : https://github.com/tinygo-org/drivers/blob/dev/st7789/registers.go
'''
from machine import Pin, SPI
import time
import math
import random
import framebuf

# hardware setup
# these should be correct, unless there is a special note on ur given keychain (indicating we made a mistake when putting it together oops)
W, H = 240, 240
spi = SPI(1, baudrate=80000000, polarity=0, phase=0,
          sck=Pin(9), mosi=Pin(6), miso=Pin(5))
dc = Pin(8, Pin.OUT)
cs = Pin(7, Pin.OUT, value=1)
rst = Pin(10, Pin.OUT)
button = Pin(0, Pin.IN, Pin.PULL_UP)


def _command(code, data=None):
    """send a command byte to the display, optionally followed by data bytes (CS low = select, DC=0 = command, DC=1 = data, CS high = deselect)"""
    cs.value(0)
    dc.value(0)
    spi.write(bytes([code]))
    if data is not None:
        dc.value(1)
        spi.write(data)
    cs.value(1)


def _window(x, y, width, height):
    """
    select the rectangle of screen pixels that will be updated,
    _window sends the CASET (0x2A) and RASET (0x2B) commands with 16-bit big-endian start/end coordinates to define an inclusive pixel rectangle [x, x+w-1] × [y, y+h-1] that subsequent pixel writes will fill
    """
    _command(0x2A, bytes((x >> 8, x & 255,
                           (x + width - 1) >> 8, (x + width - 1) & 255)))
    _command(0x2B, bytes((y >> 8, y & 255,
                           (y + height - 1) >> 8, (y + height - 1) & 255)))


def _send_pixels(data):
    """write RGB565 pixel bytes to the selected display window."""
    cs.value(0)
    dc.value(0)
    spi.write(b'\x2C') # RAMWR is "Memory Write", the command that tells the controller: "the next bytes i send are pixel data; write them into the active window"
    dc.value(1)
    spi.write(data)
    cs.value(1)


def init_screen():
    """reset and turn on the display, call once before drawing"""
    rst.value(0)
    time.sleep_ms(100)
    rst.value(1)
    time.sleep_ms(150)
    _command(0x01)       # software reset
    time.sleep_ms(150)
    _command(0x11)       # wake from sleep
    time.sleep_ms(150)
    _command(0x3A, b'\x55')  # 16-bit RGB565 colour mode
    _command(0x36, b'\x00')
    _command(0x21)    
    _command(0x29)       # display on
    time.sleep_ms(100)


def rgb(r, g, b):
    """
    converts red, green, blue (each 0–255) into a screen colour that can be sent
    google 'colour picker', pick your colours, and copy the hex values here

    eg. PINK = rgb(255, 154, 154)
    """
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _colour_bytes(colour):
    return bytes((colour >> 8, colour & 255))


def fill_screen(colour):
    """
    spaint the entire screen a single colour
    eg. fill_screen(rgb(0, 0, 0))  shows a black background
    """
    _window(0, 0, W, H)
    row = _colour_bytes(colour) * W
    cs.value(0)
    dc.value(0)
    spi.write(b'\x2C')
    dc.value(1)
    for _ in range(H):
        spi.write(row)
    cs.value(1)


def draw_rect(x, y, width, height, colour):
    """
    draw a solid rectangle, with coordinates (x, y) as its top-left corner
    eg. draw_rect(20, 30, 50, 15, rgb(255, 0, 0))
    """
    x2 = min(W, x + width)
    y2 = min(H, y + height)
    x = max(0, x)
    y = max(0, y)
    if x >= x2 or y >= y2:
        return
    width, height = x2 - x, y2 - y
    _window(x, y, width, height)
    row = _colour_bytes(colour) * width
    cs.value(0)
    dc.value(0)
    spi.write(b'\x2C')
    dc.value(1)
    for _ in range(height):
        spi.write(row)
    cs.value(1)


def draw_pixel(x, y, colour):
    """colour 1 specific pixel at coordinate (x, y)"""
    draw_rect(x, y, 1, 1, colour)


def draw_text(message, x, y, colour, scale=2, background=None):
    """
    display text using the built-in 8x8 pixel font

    scale=1 gives 8px-high letters; scale=2 gives 16px-high letters, and so on
    background sets the colour behind the letters (defaults to BG).
    eg. draw_text('hello', 10, 200, rgb(255, 255, 255))
    """
    if background is None:
        background = BG
    width = len(message) * 8
    if width == 0:
        return
    raw = bytearray((width * 8 + 7) // 8)
    fb = framebuf.FrameBuffer(raw, width, 8, framebuf.MONO_HLSB)
    fb.fill(0)
    fb.text(message, 0, 0, 1)
    fg, bg = _colour_bytes(colour), _colour_bytes(background)
    # Draw each scaled row. No large framebuffer is needed.
    for py in range(8):
        line = bytearray()
        for px in range(width):
            line.extend((fg if fb.pixel(px, py) else bg) * scale)
        for sy in range(scale):
            yy = y + py * scale + sy
            if 0 <= yy < H and 0 <= x and x + width * scale <= W:
                _window(x, yy, width * scale, 1)
                _send_pixels(line)


def button_pressed():
    """
    return True while the GPIO0 button is held down
    the button is active-low: the pin , ie. reads as '0' when pressed
    """
    return button.value() == 0


# configs
BG = rgb(0x34, 0x34, 0x3C)
EYE_TOP = (255, 154, 154)
EYE_BOTTOM = (255, 197, 141) 
EYE_W, EYE_H = 68, 72
CORNER_RADIUS = 17
LEFT_X, RIGHT_X, EYE_Y = 47, 130, 84
MAX_X, MAX_Y = 12, 7


RX = LEFT_X - MAX_X
RY = EYE_Y - MAX_Y
RW = RIGHT_X + EYE_W + MAX_X - RX
RH = EYE_H + 2 * MAX_Y
BUFFER = bytearray(RW * RH * 2)
BG_ROW = _colour_bytes(BG) * RW

# precompute the vertical colour gradient once to speed up animation.
GRADIENT = []
for y in range(EYE_H):
    t = y / (EYE_H - 1)
    GRADIENT.append(_colour_bytes(rgb(
        int(EYE_TOP[0] + (EYE_BOTTOM[0] - EYE_TOP[0]) * t),
        int(EYE_TOP[1] + (EYE_BOTTOM[1] - EYE_TOP[1]) * t),
        int(EYE_TOP[2] + (EYE_BOTTOM[2] - EYE_TOP[2]) * t)
    )))


def _corner_inset(y, height):
    """returns how many pixels to trim from each side for rounded corners"""
    radius = min(CORNER_RADIUS, height // 2)
    if radius <= 0:
        return 0
    if y < radius:
        dy = radius - y - 1
    elif y >= height - radius:
        dy = y - (height - radius)
    else:
        return 0
    return radius - int(math.sqrt(max(0, radius * radius - dy * dy)))


def draw_eyes(x=0, y=0, openness=1.0):
    """
    draw both eyes in one frame

    x: horizontal gaze offset, from -MAX_X to +MAX_X
    y: vertical gaze offset, from -MAX_Y to +MAX_Y
    openness: 1.0 = open; 0.03 = almost fully closed

    eg.
        draw_eyes()                 # Look straight ahead
        draw_eyes(10, -5)           # Look right and up
        draw_eyes(0, 0, 0.1)        # Almost closed / blinking
    """
    x = max(-MAX_X, min(MAX_X, int(x)))
    y = max(-MAX_Y, min(MAX_Y, int(y)))
    openness = max(0.03, min(1.0, openness))
    height = max(2, int(EYE_H * openness))
    top = (EYE_H - height) // 2
    eye_y = EYE_Y + y - RY

    for row in range(RH):
        offset = row * RW * 2
        BUFFER[offset:offset + RW * 2] = BG_ROW
        local_y = row - eye_y - top
        if not 0 <= local_y < height:
            continue
        inset = _corner_inset(local_y, height)
        width = EYE_W - 2 * inset
        if width <= 0:
            continue
        gradient_y = max(0, min(EYE_H - 1, row - eye_y))
        pixels = GRADIENT[gradient_y] * width
        for eye_x in (LEFT_X, RIGHT_X):
            start = offset + (eye_x + x - RX + inset) * 2
            BUFFER[start:start + len(pixels)] = pixels

    _window(RX, RY, RW, RH)
    _send_pixels(BUFFER)


def ease(t):
    """
    Smooth a value from 0 to 1 for more natural animation.

    Linear movement changes at a constant speed. This easing curve
    starts slowly, speeds up in the middle, then slows down again.

    BONUS TASK: CUSTOMISE THIS!!!
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


current_x = 0
current_y = 0


# FUNCTOINS TODO !!!

def look_at(x, y, steps=4, delay_ms=20):
    """TODO: Animate the eyes from their current position to (x, y)

    x, y: target offsets from the centre (not absolute coordinates)
    steps: how many intermediate frames to draw.
    delay_ms: time between frames in milliseconds.

    Useful tools:
      draw_eyes(x, y)      draws a frame at a given offset
      ease(t)              smooths progress from 0.0 to 1.0
      time.sleep_ms(20)    pauses for 20 milliseconds

    Hint: interpolate between the starting and target positions
    Remember to update current_x and current_y when finished
    """
    global current_x, current_y
    # TODO: write your movement animation here :D
    pass


def blink(frames=5, delay_ms=15):
    """TODO: Animate a blink by closing and reopening the eyes

    draw_eyes(current_x, current_y, openness) draws a frame
    openness=1.0 means fully open; openness=0.03 is almost closed

    Hint: use one loop to close the eyes, then another to open them
    """
    # TODO: write your blinking animation here :D
    pass


# MAIN!!!
init_screen()       # turn on screen
fill_screen(BG)     # clear bg
draw_eyes()         # show starting eyes

# TODO 1: Make the eyes look left, right, and back to centre
# TODO 2: Implement blink() and look_at() above
# TODO 3: Use a while True loop for random movement and blinking
# TODO 4: Use button_pressed() to trigger your own interaction


