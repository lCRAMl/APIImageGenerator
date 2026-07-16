import ctypes
from ctypes import wintypes

FLASHW_STOP = 0
FLASHW_CAPTION = 0x00000001
FLASHW_TRAY = 0x00000002
FLASHW_ALL = FLASHW_CAPTION | FLASHW_TRAY
FLASHW_TIMERNOFG = 0x0000000C


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


def flash_taskbar(win_id: int):
    hwnd = int(win_id)

    info = FLASHWINFO(
        ctypes.sizeof(FLASHWINFO),
        hwnd,
        FLASHW_TRAY | FLASHW_TIMERNOFG,
        3,      # Anzahl Blinkvorgänge
        0
    )

    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))