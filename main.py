import pygame

from cfa835.device import CFA835Device
from cfa835.serial_interface import SerialInterface
from cfa835.gui import GUI


def main():
    device = CFA835Device()
    serial = SerialInterface(device)
    gui = GUI(device)

    print(f"CFA835 Emulator running")
    print(f"PTY device: {serial.pty_path}")
    print(f"Connect your client to: {serial.pty_path}")

    clock = pygame.time.Clock()

    try:
        while gui.running:
            serial.poll()
            gui.handle_events()
            serial.flush_reports()
            gui.render()
            clock.tick(60)
    except KeyboardInterrupt:
        pass
    finally:
        serial.close()
        gui.close()


if __name__ == "__main__":
    main()
