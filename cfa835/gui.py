import pygame

from .device import (
    CFA835Device, LCD_WIDTH, LCD_HEIGHT,
    KEY_UP_PRESS, KEY_UP_RELEASE,
    KEY_DOWN_PRESS, KEY_DOWN_RELEASE,
    KEY_LEFT_PRESS, KEY_LEFT_RELEASE,
    KEY_RIGHT_PRESS, KEY_RIGHT_RELEASE,
    KEY_ENTER_PRESS, KEY_ENTER_RELEASE,
    KEY_EXIT_PRESS, KEY_EXIT_RELEASE,
)

SCALE = 3
LCD_DISPLAY_W = LCD_WIDTH * SCALE
LCD_DISPLAY_H = LCD_HEIGHT * SCALE

PADDING = 20
LED_SIZE = 14
LED_SPACING = 24
BUTTON_W = 36
BUTTON_H = 36

BG_COLOR = (40, 40, 45)
LCD_BG = (180, 200, 160)
LCD_FG = (30, 40, 20)
BEZEL_COLOR = (60, 60, 65)
BUTTON_COLOR = (80, 80, 85)
BUTTON_HOVER = (100, 100, 105)
BUTTON_TEXT_COLOR = (200, 200, 200)

BUTTONS = [
    {"label": "\u25b2", "press": KEY_UP_PRESS, "release": KEY_UP_RELEASE},
    {"label": "\u25bc", "press": KEY_DOWN_PRESS, "release": KEY_DOWN_RELEASE},
    {"label": "\u25c0", "press": KEY_LEFT_PRESS, "release": KEY_LEFT_RELEASE},
    {"label": "\u25b6", "press": KEY_RIGHT_PRESS, "release": KEY_RIGHT_RELEASE},
    {"label": "\u2713", "press": KEY_ENTER_PRESS, "release": KEY_ENTER_RELEASE},
    {"label": "X", "press": KEY_EXIT_PRESS, "release": KEY_EXIT_RELEASE},
]

KEY_BINDINGS = {
    pygame.K_UP: 0,
    pygame.K_DOWN: 1,
    pygame.K_LEFT: 2,
    pygame.K_RIGHT: 3,
    pygame.K_RETURN: 4,
    pygame.K_ESCAPE: 5,
}


class GUI:
    def __init__(self, device: CFA835Device):
        self.device = device
        pygame.init()

        led_panel_w = LED_SIZE + PADDING * 2
        self.lcd_x = led_panel_w + PADDING
        self.lcd_y = PADDING + 10

        btn_gap = 4
        dpad_w = BUTTON_W * 3 + btn_gap * 2
        action_w = BUTTON_W * 2 + btn_gap
        btn_area_w = dpad_w + 16 + action_w
        btn_area_h = BUTTON_H * 3 + btn_gap * 2

        self.btn_area_x = self.lcd_x + LCD_DISPLAY_W + PADDING
        win_w = self.btn_area_x + btn_area_w + PADDING
        content_h = max(LCD_DISPLAY_H, btn_area_h)
        win_h = self.lcd_y + content_h + PADDING

        self.screen = pygame.display.set_mode((win_w, win_h))
        pygame.display.set_caption("CFA835 Emulator")

        self.font = pygame.font.SysFont("monospace", 15)
        self.lcd_surface = pygame.Surface((LCD_WIDTH, LCD_HEIGHT))

        self.button_rects: list[pygame.Rect] = []
        self._layout_buttons(btn_gap, btn_area_h)

        self.led_rects: list[pygame.Rect] = []
        self._layout_leds()

        self.running = True

    def _layout_buttons(self, gap: int, btn_area_h: int):
        lcd_center_y = self.lcd_y + LCD_DISPLAY_H // 2
        btn_y = lcd_center_y - btn_area_h // 2

        dpad_x = self.btn_area_x
        up_rect = pygame.Rect(dpad_x + BUTTON_W + gap, btn_y, BUTTON_W, BUTTON_H)
        down_rect = pygame.Rect(dpad_x + BUTTON_W + gap, btn_y + (BUTTON_H + gap) * 2, BUTTON_W, BUTTON_H)
        left_rect = pygame.Rect(dpad_x, btn_y + BUTTON_H + gap, BUTTON_W, BUTTON_H)
        right_rect = pygame.Rect(dpad_x + (BUTTON_W + gap) * 2, btn_y + BUTTON_H + gap, BUTTON_W, BUTTON_H)

        dpad_w = BUTTON_W * 3 + gap * 2
        action_x = dpad_x + dpad_w + 16
        ok_rect = pygame.Rect(action_x, btn_y + BUTTON_H // 2, BUTTON_W, BUTTON_H)
        x_rect = pygame.Rect(action_x + BUTTON_W + gap, btn_y + BUTTON_H // 2, BUTTON_W, BUTTON_H)

        self.button_rects = [up_rect, down_rect, left_rect, right_rect, ok_rect, x_rect]

    def _layout_leds(self):
        x = PADDING
        lcd_center_y = self.lcd_y + LCD_DISPLAY_H // 2
        total_h = 4 * LED_SIZE + 3 * (LED_SPACING - LED_SIZE)
        start_y = lcd_center_y - total_h // 2
        for i in range(4):
            y = start_y + i * LED_SPACING
            self.led_rects.append(pygame.Rect(x, y, LED_SIZE, LED_SIZE))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                for i, rect in enumerate(self.button_rects):
                    if rect.collidepoint(event.pos):
                        self.device.key_event(BUTTONS[i]["press"])
            elif event.type == pygame.MOUSEBUTTONUP:
                for i, rect in enumerate(self.button_rects):
                    if rect.collidepoint(event.pos):
                        self.device.key_event(BUTTONS[i]["release"])
            elif event.type == pygame.KEYDOWN:
                idx = KEY_BINDINGS.get(event.key)
                if idx is not None:
                    self.device.key_event(BUTTONS[idx]["press"])
            elif event.type == pygame.KEYUP:
                idx = KEY_BINDINGS.get(event.key)
                if idx is not None:
                    self.device.key_event(BUTTONS[idx]["release"])

    def render(self):
        self.screen.fill(BG_COLOR)
        self._draw_lcd()
        self._draw_leds()
        self._draw_buttons()
        pygame.display.flip()

    def _draw_lcd(self):
        brightness = self.device.display_brightness / 100.0

        for y in range(LCD_HEIGHT):
            for x in range(LCD_WIDTH):
                shade = self.device.framebuffer[y * LCD_WIDTH + x]
                pixel_on = shade > 127
                if pixel_on:
                    r = int(LCD_FG[0] * brightness + BG_COLOR[0] * (1 - brightness))
                    g = int(LCD_FG[1] * brightness + BG_COLOR[1] * (1 - brightness))
                    b = int(LCD_FG[2] * brightness + BG_COLOR[2] * (1 - brightness))
                else:
                    r = int(LCD_BG[0] * brightness + BG_COLOR[0] * (1 - brightness))
                    g = int(LCD_BG[1] * brightness + BG_COLOR[1] * (1 - brightness))
                    b = int(LCD_BG[2] * brightness + BG_COLOR[2] * (1 - brightness))
                self.lcd_surface.set_at((x, y), (r, g, b))

        bezel_rect = pygame.Rect(
            self.lcd_x - 4, self.lcd_y - 4,
            LCD_DISPLAY_W + 8, LCD_DISPLAY_H + 8,
        )
        pygame.draw.rect(self.screen, BEZEL_COLOR, bezel_rect, border_radius=3)

        scaled = pygame.transform.scale(self.lcd_surface, (LCD_DISPLAY_W, LCD_DISPLAY_H))
        self.screen.blit(scaled, (self.lcd_x, self.lcd_y))

    def _draw_leds(self):
        for i, rect in enumerate(self.led_rects):
            led = self.device.leds[i]
            r = int(led.red * 2.55)
            g = int(led.green * 2.55)
            color = (r, g, 0) if (r + g) > 0 else (30, 30, 30)
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            pygame.draw.rect(self.screen, (80, 80, 80), rect, width=1, border_radius=3)

    def _draw_buttons(self):
        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate(self.button_rects):
            hovering = rect.collidepoint(mouse_pos)
            color = BUTTON_HOVER if hovering else BUTTON_COLOR
            if BUTTONS[i]["label"] == "\u2713":
                color = (40, 100, 40) if not hovering else (50, 130, 50)
            elif BUTTONS[i]["label"] == "X":
                color = (130, 40, 40) if not hovering else (160, 50, 50)
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            label = self.font.render(BUTTONS[i]["label"], True, BUTTON_TEXT_COLOR)
            lx = rect.x + (rect.width - label.get_width()) // 2
            ly = rect.y + (rect.height - label.get_height()) // 2
            self.screen.blit(label, (lx, ly))

    def close(self):
        pygame.quit()
