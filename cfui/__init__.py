"""cfui - Python UI framework for Crystalfontz CFA835 LCD modules.

Provides a widget-based UI toolkit with spatial D-pad navigation,
page management, and hardware control (brightness, LEDs, dark mode).
Communicates over serial using the CFA835 packet protocol.
"""

from .core import App, Page
from .widgets import Text, Button, HRule, ProgressBar, Slider, Spacer, Icon
from .layout import Row, Column, Tabs
from .storage import Storage

__all__ = [
    "App", "Page",
    "Text", "Button", "HRule", "ProgressBar", "Slider", "Spacer", "Icon",
    "Row", "Column", "Tabs",
    "Storage",
]
