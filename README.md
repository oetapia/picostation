# PicoStation

A Raspberry Pi Pico-based platform running MicroPython with two display modes: a full arcade game console using a **TFT HAT** (240×240, color), and a compact utility station using an **OLED** module (128×32, monochrome).

The firmware auto-detects which display is connected at boot and launches the appropriate interface.

---

## Hardware Options

### Option A — TFT HAT (Full Mode)

Launches the **arcade game menu** with Space Invaders, Snake, Weather, and a Volumio music player.

#### Display

| Signal | Pico Pin | GPIO |
|--------|----------|------|
| MOSI   | Pin 15   | GP11 |
| SCK    | Pin 14   | GP10 |
| CS     | Pin 12   | GP9  |
| DC     | Pin 11   | GP8  |
| RST    | Pin 16   | GP12 |
| BL     | Pin 17   | GP13 |
| GND    | Pin 38   | —    |
| 3.3V   | Pin 36   | —    |

The backlight (BL) is PWM-controlled for brightness adjustment.

#### Buttons (TFT HAT)

| Button | GPIO | Notes         |
|--------|------|---------------|
| UP     | GP2  | D-pad up      |
| DOWN   | GP18 | D-pad down    |
| LEFT   | GP16 | D-pad left    |
| RIGHT  | GP20 | D-pad right   |
| A      | GP15 | Action        |
| B      | GP17 | Action / confirm |
| X      | GP19 | Action / exit |
| Y      | GP21 | Action        |
| CTRL   | GP3  | Control       |

All buttons use internal pull-up resistors and are active-low with 100 ms debounce.

---

### Option B — OLED Module (Mini Mode)

Launches the **mini app menu** with Weather, IR Sensor, Accelerometer, LED Test, and Sound apps.

#### Display

The OLED is an SSD1306-compatible module (128×32 pixels) connected over I2C.

| Signal | Pico Pin | GPIO |
|--------|----------|------|
| SDA    | Pin 24   | GP18 |
| SCL    | Pin 25   | GP19 |
| GND    | Pin 38   | —    |
| 3.3V   | Pin 36   | —    |

- I2C frequency: 400 kHz
- I2C address: `0x3C`

#### Buttons (OLED / Mini)

| Button | GPIO | Function         |
|--------|------|------------------|
| UP     | GP21 | Scroll up / prev |
| DOWN   | GP22 | Scroll down / next |
| CTRL   | GP26 | Select / confirm |

All buttons use internal pull-up resistors and are active-low with 100 ms debounce.

---

## Display Auto-Detection

`screen.py` probes for hardware at boot in this order:

1. **OLED** — attempts an I2C scan on GP18/GP19. If a device is found at `0x3C`, the OLED driver is loaded and mini mode starts.
2. **TFT** — if OLED probing fails, the ST7789 SPI driver is loaded and the arcade menu starts.
3. **Headless** — if both fail, a no-op `NullScreen` is used (useful for testing without hardware).

```python
# screen.py
Screen = _detect()   # exported singleton — import this everywhere
```

All app and game files import the same object:

```python
from screen import Screen
```

---

## Software Setup

### Requirements

- [MicroPython](https://micropython.org/download/RPI_PICO/) flashed to the Pico (v1.22 or later recommended)
- [Thonny IDE](https://thonny.org/) or `mpremote` for uploading files

### Libraries to upload

The following third-party library must be present on the Pico:

| File | Destination | Purpose |
|------|-------------|---------|
| `lib/ssd1306.py` | `/lib/ssd1306.py` | OLED driver |

Everything else in the repository is project code that runs on MicroPython directly.

### Configuration

Copy `config.py` to the Pico and fill in your credentials:

```python
# config.py
WIFI_SSID     = 'your_network'
WIFI_PASSWORD = 'your_password'
WEATHER_API_KEY = 'your_key_from_weatherapi.com'
```

The Volumio integration expects Volumio to be reachable at `volumio.local` on the same network.

### File structure on the Pico

Upload the entire repository to the root of the Pico filesystem:

```
/
├── main.py
├── config.py
├── screen.py
├── wifi.py
├── volumio3.py
├── breadboard/
│   ├── buttons.py
│   ├── buzzer.py
│   └── leds.py
├── mini/
│   ├── weather.py
│   ├── sensor_main.py
│   ├── accel_main.py
│   ├── led_test.py
│   └── sound_app.py
├── oled_screen/
│   └── display.py
├── tft_screen/
│   └── screen_library.py
├── games/
│   ├── space_invaders.py
│   └── snake.py
├── icons_16/
├── icons_rgb565/
└── lib/
    └── ssd1306.py
```

`main.py` is the entry point — the Pico runs it automatically on boot.

---

## TFT Mode — Arcade Menu

When a TFT HAT is detected the startup animation plays, then the game menu appears:

```
  ARCADE GAMES
  ────────────
  > SPACE INVADERS   Shoot the aliens!
    MUSIC PLAYER     Volumio controls
    WEATHER          City weather
    SNAKE            Classic snake game

  UP/DOWN: Select   B: Start Game
```

| Action | Button |
|--------|--------|
| Move cursor | UP / DOWN |
| Launch selected | B |
| Exit to menu | X (inside any app) |

---

## OLED Mode — Mini App Menu

When an OLED is detected, a ghost icon and "mini" splash screen appears, followed by:

```
> WEATHER
  IR SENSOR
  ACCEL
  LED TEST
```

| Action | Button |
|--------|--------|
| Scroll | UP / DOWN (GP21 / GP22) |
| Launch | CTRL (GP26) |

---

## Additional Hardware (Optional)

| Component | Interface | Pins |
|-----------|-----------|------|
| MPU-6050 accelerometer | I2C(0) | SDA=GP0, SCL=GP1 |
| IR break-beam sensor | GPIO | GP15 |
| Buzzer | PWM | GP20 |
| Red LED | GPIO | GP13 |
| Green LED | GPIO | GP17 |

These are used by the mini apps (Accel, IR Sensor, Sound, LED Test).
