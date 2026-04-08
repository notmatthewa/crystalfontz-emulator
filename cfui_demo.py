"""Demo of the cfui framework on the CFA835 emulator."""

import sys
from cfui import App, Page, Text, Button, HRule, ProgressBar, Slider, Spacer, Row, Column, Tabs


def main():
    if len(sys.argv) < 2:
        print("Usage: python cfui_demo.py /dev/pts/X")
        sys.exit(1)

    app = App(sys.argv[1])

    # ── State ──
    brightness = 0.75
    counter = 0
    dark_mode = False

    # ── Widgets that get updated ──
    counter_label = Text(f"Count: {counter}")
    brightness_label = Text(f"{int(brightness * 100)}%", align="right")

    def on_brightness_change(val):
        brightness_label.text = f"{int(val * 100)}%"
        app.set_brightness(int(val * 100))
        app.invalidate()

    brightness_slider = Slider(value=brightness, step=0.05, height=6,
                               on_change=on_brightness_change)

    # ── Callbacks ──
    def increment():
        nonlocal counter
        counter += 1
        counter_label.text = f"Count: {counter}"
        app.invalidate()

    def reset():
        nonlocal counter
        counter = 0
        counter_label.text = f"Count: {counter}"
        app.invalidate()

    # ── Dark mode toggle ──
    mode_label = Text("Mode: Light", align="right")

    def toggle_dark_mode():
        nonlocal dark_mode
        dark_mode = not dark_mode
        print(f"Toggle dark mode: {dark_mode}")
        app.set_dark_mode(dark_mode)
        mode_label.text = f"Mode: {'Dark' if dark_mode else 'Light'}"
        app.invalidate()

    # ── Home page ──
    home = Page("home", body=Column(spacing=2, children=[
        Text("CFUI Demo", align="center", shade=0xFF),
        HRule(),
        Button("Counter", on_press=lambda: app.navigate("counter")),
        Button("Settings", on_press=lambda: app.navigate("settings")),
        Button("LEDs", on_press=lambda: app.navigate("leds")),
        Button("Tabs Demo", on_press=lambda: app.navigate("tabs")),
        Button("Quit", on_press=app.quit),
    ]))

    # ── Counter page ──
    counter_page = Page("counter", body=Column(spacing=2, children=[
        Text("Counter", align="center"),
        HRule(),
        counter_label,
        Row(spacing=4, align="center", children=[
            Button("+1", on_press=increment),
            Button("Reset", on_press=reset),
        ]),
    ]))

    # ── Settings page ──
    settings = Page("settings", body=Column(spacing=2, children=[
        Text("Settings", align="center"),
        HRule(),
        Row(spacing=2, children=[
            Text("Brightness:"),
            brightness_slider,
            brightness_label,
        ]),
        Button("Dark/Light", on_press=toggle_dark_mode),
    ]))

    # ── LEDs page ──
    led_states = [[0, 0], [0, 0], [0, 0], [0, 0]]  # [green, red] per LED
    led_label = Text("LED 0: off")
    current_led = [0]

    def update_led_label():
        i = current_led[0]
        g, r = led_states[i]
        if g and r:
            status = "yellow"
        elif g:
            status = "green"
        elif r:
            status = "red"
        else:
            status = "off"
        led_label.text = f"LED {i}: {status}"

    def prev_led():
        current_led[0] = (current_led[0] - 1) % 4
        update_led_label()
        app.invalidate()

    def next_led():
        current_led[0] = (current_led[0] + 1) % 4
        update_led_label()
        app.invalidate()

    def toggle_green():
        i = current_led[0]
        led_states[i][0] = 0 if led_states[i][0] else 100
        app.set_led(i, green=led_states[i][0], red=led_states[i][1])
        update_led_label()
        app.invalidate()

    def toggle_red():
        i = current_led[0]
        led_states[i][1] = 0 if led_states[i][1] else 100
        app.set_led(i, green=led_states[i][0], red=led_states[i][1])
        update_led_label()
        app.invalidate()

    def all_off():
        for i in range(4):
            led_states[i] = [0, 0]
            app.set_led(i, green=0, red=0)
        update_led_label()
        app.invalidate()

    leds_page = Page("leds", body=Column(spacing=2, children=[
        Text("LEDs", align="center"),
        HRule(),
        Row(spacing=2, align="center", children=[
            Button("<", on_press=prev_led),
            led_label,
            Button(">", on_press=next_led),
        ]),
        Row(spacing=4, align="center", children=[
            Button("Green", on_press=toggle_green),
            Button("Red", on_press=toggle_red),
            Button("All Off", on_press=all_off),
        ]),
    ]))

    # ── Tabs page ──
    tab1_content = Column(spacing=1, children=[
        Text("System Info"),
        Text("CFA835 Emulator"),
        Text("244x68 grayscale"),
    ])
    tab2_content = Column(spacing=1, children=[
        Text("Network: OK"),
        Text("Uptime: 42d 3h"),
        Button("Refresh", on_press=lambda: app.invalidate()),
    ])
    tabs_page = Page("tabs", body=Column(spacing=0, children=[
        Tabs(tabs={"Info": tab1_content, "Status": tab2_content}),
    ]))

    # ── Register and run ──
    app.add_page(home)
    app.add_page(counter_page)
    app.add_page(settings)
    app.add_page(leds_page)
    app.add_page(tabs_page)

    print("Running cfui demo...")
    print("Use D-pad to navigate, Enter to select, Exit to go back")
    app.run("home")


if __name__ == "__main__":
    main()
