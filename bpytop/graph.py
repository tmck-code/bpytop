#!/usr/bin/env python3
# pylint: disable=not-callable, no-member, unsubscriptable-object
# indent = tab
# tab-size = 4

# Copyright 2021 Aristocratos (jakob@qvantnet.com)

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import os, sys, io, threading, signal, re, subprocess, logging, logging.handlers, argparse
import urllib.request
from time import time, sleep, strftime, tzset
from datetime import timedelta
from _thread import interrupt_main
from collections import defaultdict
from select import select
from distutils.util import strtobool
from math import ceil, floor
from random import randint
from shutil import which
from typing import List, Dict, Tuple, Union, Any, Iterable

from util.draw import Draw
from util.term import Term
from ui.menu import Menu, Banner
from util import fmt
from util.symbol import Symbol
from collectors.cpu import CpuCollector
from collectors.mem import MemCollector
from collectors.proc import ProcCollector
from collectors.net import NetCollector
from collectors.collector import Collector

from util.timer import TimeIt
from util.init import Init
from util import platform

import_errors: List[str] = []
try:
    import fcntl, termios, tty, pwd
except Exception as e:
    import_errors.append(f"{e}")

try:
    import psutil  # type: ignore
except Exception as e:
    import_errors.append(f"{e}")

if import_errors:
    raise Exception(
        f"Caught errors when trying to import required packages: {import_errors}"
    )

# ? Variables ------------------------------------------------------------------------------------->

VERSION: str = "1.0.67"

BANNER_SRC: List[Tuple[str, str, str]] = [
    ("#ffa50a", "#0fd7ff", "██████╗ ██████╗ ██╗   ██╗████████╗ ██████╗ ██████╗"),
    ("#f09800", "#00bfe6", "██╔══██╗██╔══██╗╚██╗ ██╔╝╚══██╔══╝██╔═══██╗██╔══██╗"),
    ("#db8b00", "#00a6c7", "██████╔╝██████╔╝ ╚████╔╝    ██║   ██║   ██║██████╔╝"),
    ("#c27b00", "#008ca8", "██╔══██╗██╔═══╝   ╚██╔╝     ██║   ██║   ██║██╔═══╝ "),
    ("#a86b00", "#006e85", "██████╔╝██║        ██║      ██║   ╚██████╔╝██║"),
    ("#000000", "#000000", "╚═════╝ ╚═╝        ╚═╝      ╚═╝    ╚═════╝ ╚═╝"),
]

THREAD_ERROR: int = 0
stdargs = None


def parse_args():
    "Argument parser"
    args = argparse.ArgumentParser()
    args.add_argument(
        "-b",
        "--boxes",
        action="store",
        dest="boxes",
        help='which boxes to show at start, example: -b "cpu mem net proc"',
    )
    args.add_argument(
        "-lc",
        "--low-color",
        action="store_true",
        help="disable truecolor, converts 24-bit colors to 256-color",
    )
    args.add_argument(
        "-v", "--version", action="store_true", help="show version info and exit"
    )
    args.add_argument(
        "--debug",
        action="store_true",
        help="start with loglevel set to DEBUG overriding value set in config",
    )
    stdargs = args.parse_args()

    if stdargs.version:
        print(
            f"bpytop version: {VERSION}\n"
            f'psutil version: {".".join(str(x) for x in psutil.version_info)}'
        )
        raise SystemExit(0)
    return stdargs


from util import platform

if __name__ == "__main__":
    SELF_START = time()

    SYSTEM: str = platform.detect()

stdargs = parse_args()
ARG_BOXES: str = stdargs.boxes
LOW_COLOR: bool = stdargs.low_color
DEBUG: bool = stdargs.debug

CONFIG_DIR: str = f'{os.path.expanduser("~")}/.config/bpytop'
if not os.path.isdir(CONFIG_DIR):
    try:
        os.makedirs(CONFIG_DIR)
        os.mkdir(f"{CONFIG_DIR}/themes")
    except PermissionError:
        print(f'ERROR!\nNo permission to write to "{CONFIG_DIR}" directory!')
        raise SystemExit(1)
CONFIG_FILE: str = f"{CONFIG_DIR}/bpytop.conf"
THEME_DIR: str = ""

if os.path.isdir(f"{os.path.dirname(__file__)}/bpytop-themes"):
    THEME_DIR = f"{os.path.dirname(__file__)}/bpytop-themes"
elif os.path.isdir(f"{os.path.dirname(__file__)}/themes"):
    THEME_DIR = f"{os.path.dirname(__file__)}/themes"
else:
    for td in ["/usr/local/", "/usr/", "/snap/bpytop/current/usr/"]:
        if os.path.isdir(f"{td}share/bpytop/themes"):
            THEME_DIR = f"{td}share/bpytop/themes"
            break
USER_THEME_DIR: str = f"{CONFIG_DIR}/themes"

CORES: int = psutil.cpu_count(logical=False) or 1
THREADS: int = psutil.cpu_count(logical=True) or 1

# from ui import menu

MENUS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "options": {
        "normal": ("┌─┐┌─┐┌┬┐┬┌─┐┌┐┌┌─┐", "│ │├─┘ │ ││ ││││└─┐", "└─┘┴   ┴ ┴└─┘┘└┘└─┘"),
        "selected": (
            "╔═╗╔═╗╔╦╗╦╔═╗╔╗╔╔═╗",
            "║ ║╠═╝ ║ ║║ ║║║║╚═╗",
            "╚═╝╩   ╩ ╩╚═╝╝╚╝╚═╝",
        ),
    },
    "help": {
        "normal": ("┬ ┬┌─┐┬  ┌─┐", "├─┤├┤ │  ├─┘", "┴ ┴└─┘┴─┘┴  "),
        "selected": ("╦ ╦╔═╗╦  ╔═╗", "╠═╣║╣ ║  ╠═╝", "╩ ╩╚═╝╩═╝╩  "),
    },
    "quit": {
        "normal": ("┌─┐ ┬ ┬ ┬┌┬┐", "│─┼┐│ │ │ │ ", "└─┘└└─┘ ┴ ┴ "),
        "selected": ("╔═╗ ╦ ╦ ╦╔╦╗ ", "║═╬╗║ ║ ║ ║  ", "╚═╝╚╚═╝ ╩ ╩  "),
    },
}

MENU_COLORS: Dict[str, Tuple[str, ...]] = {
    "normal": ("#0fd7ff", "#00bfe6", "#00a6c7", "#008ca8"),
    "selected": ("#ffa50a", "#f09800", "#db8b00", "#c27b00"),
}

# ? Units for floating_humanizer function
UNITS: Dict[str, Tuple[str, ...]] = {
    "bit": (
        "bit",
        "Kib",
        "Mib",
        "Gib",
        "Tib",
        "Pib",
        "Eib",
        "Zib",
        "Yib",
        "Bib",
        "GEb",
    ),
    "byte": (
        "Byte",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
        "PiB",
        "EiB",
        "ZiB",
        "YiB",
        "BiB",
        "GEB",
    ),
}

SUBSCRIPT: Tuple[str, ...] = ("₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉")
SUPERSCRIPT: Tuple[str, ...] = ("⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹")

# ? Setup error logger ---------------------------------------------------------------->

try:
    errlog = logging.getLogger("ErrorLogger")
    errlog.setLevel(logging.DEBUG)
    eh = logging.handlers.RotatingFileHandler(
        f"{CONFIG_DIR}/error.log", maxBytes=1048576, backupCount=4
    )
    eh.setLevel(logging.DEBUG)
    eh.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s: %(message)s", datefmt="%d/%m/%y (%X)"
        )
    )
    errlog.addHandler(eh)
except PermissionError:
    print(f'ERROR!\nNo permission to write to "{CONFIG_DIR}" directory!')
    raise SystemExit(1)

# ? Set up config class and load config ----------------------------------------------------------->


from config import Config

try:
    CONFIG: Config = Config(CONFIG_FILE, VERSION)
    if DEBUG:
        errlog.setLevel(logging.DEBUG)
    else:
        errlog.setLevel(getattr(logging, CONFIG.log_level))
        DEBUG = CONFIG.log_level == "DEBUG"
    errlog.info(
        f"New instance of bpytop version {VERSION} started with pid {os.getpid()}"
    )
    errlog.info(f'Loglevel set to {"DEBUG" if DEBUG else CONFIG.log_level}')
    errlog.debug(
        f'Using psutil version {".".join(str(x) for x in psutil.version_info)}'
    )
    errlog.debug(f'CMD: {" ".join(sys.argv)}')
    if CONFIG.info:
        for info in CONFIG.info:
            errlog.info(info)
        CONFIG.info = []
    if CONFIG.warnings:
        for warning in CONFIG.warnings:
            errlog.warning(warning)
        CONFIG.warnings = []
except Exception as e:
    errlog.exception(f"{e}")
    raise SystemExit(1)

if ARG_BOXES:
    _new_boxes: List = []
    for _box in ARG_BOXES.split():
        if _box in ["cpu", "mem", "net", "proc"]:
            _new_boxes.append(_box)
    CONFIG.shown_boxes = " ".join(_new_boxes)
    del _box, _new_boxes

if SYSTEM == "Linux" and not os.path.isdir("/sys/class/power_supply"):
    CONFIG.show_battery = False

if psutil.version_info[0] < 5 or (
    psutil.version_info[0] == 5 and psutil.version_info[1] < 7
):
    warn = f'psutil version {".".join(str(x) for x in psutil.version_info)} detected, version 5.7.0 or later required for full functionality!'
    print("WARNING!", warn)
    errlog.warning(warn)


# ? Classes --------------------------------------------------------------------------------------->


class Fx:
    """Text effects
    * trans(string: str): Replace whitespace with escape move right to not overwrite background behind whitespace.
    * uncolor(string: str) : Removes all 24-bit color and returns string ."""

    start = "\033["  # * Escape sequence start
    sep = ";"  # * Escape sequence separator
    end = "m"  # * Escape sequence end
    reset = rs = "\033[0m"  # * Reset foreground/background color and text effects
    bold = b = "\033[1m"  # * Bold on
    unbold = ub = "\033[22m"  # * Bold off
    dark = d = "\033[2m"  # * Dark on
    undark = ud = "\033[22m"  # * Dark off
    italic = i = "\033[3m"  # * Italic on
    unitalic = ui = "\033[23m"  # * Italic off
    underline = u = "\033[4m"  # * Underline on
    ununderline = uu = "\033[24m"  # * Underline off
    blink = bl = "\033[5m"  # * Blink on
    unblink = ubl = "\033[25m"  # * Blink off
    strike = s = "\033[9m"  # * Strike / crossed-out on
    unstrike = us = "\033[29m"  # * Strike / crossed-out off

    # * Precompiled regex for finding a 24-bit color escape sequence in a string
    color_re = re.compile(r"\033\[\d+;\d?;?\d*;?\d*;?\d*m")

    @staticmethod
    def trans(string: str):
        return string.replace(" ", "\033[1C")

    @classmethod
    def uncolor(cls, string: str) -> str:
        return f'{cls.color_re.sub("", string)}'


class Raw(object):
    """Set raw input mode for device"""

    def __init__(self, stream):
        self.stream = stream
        self.fd = self.stream.fileno()

    def __enter__(self):
        self.original_stty = termios.tcgetattr(self.stream)
        tty.setcbreak(self.stream)

    def __exit__(self, type, value, traceback):
        termios.tcsetattr(self.stream, termios.TCSANOW, self.original_stty)


class Nonblocking(object):
    """Set nonblocking mode for device"""

    def __init__(self, stream):
        self.stream = stream
        self.fd = self.stream.fileno()

    def __enter__(self):
        self.orig_fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)

    def __exit__(self, *args):
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_fl)


class Mv:
    """Class with collection of cursor movement functions: .t[o](line, column) | .r[ight](columns) | .l[eft](columns) | .u[p](lines) | .d[own](lines) | .save() | .restore()"""

    @staticmethod
    def to(line: int, col: int) -> str:
        return f"\033[{line};{col}f"  # * Move cursor to line, column

    @staticmethod
    def right(x: int) -> str:  # * Move cursor right x columns
        return f"\033[{x}C"

    @staticmethod
    def left(x: int) -> str:  # * Move cursor left x columns
        return f"\033[{x}D"

    @staticmethod
    def up(x: int) -> str:  # * Move cursor up x lines
        return f"\033[{x}A"

    @staticmethod
    def down(x: int) -> str:  # * Move cursor down x lines
        return f"\033[{x}B"

    save: str = "\033[s"  # * Save cursor position
    restore: str = "\033[u"  # * Restore saved cursor postion
    t = to
    r = right
    l = left
    u = up
    d = down


class Key:
    """Handles the threaded input reader for keypresses and mouse events"""

    list: List[str] = []
    mouse: Dict[str, List[List[int]]] = {}
    mouse_pos: Tuple[int, int] = (0, 0)
    escape: Dict[Union[str, Tuple[str, str]], str] = {
        "\n": "enter",
        ("\x7f", "\x08"): "backspace",
        ("[A", "OA"): "up",
        ("[B", "OB"): "down",
        ("[D", "OD"): "left",
        ("[C", "OC"): "right",
        "[2~": "insert",
        "[3~": "delete",
        "[H": "home",
        "[F": "end",
        "[5~": "page_up",
        "[6~": "page_down",
        "\t": "tab",
        "[Z": "shift_tab",
        "OP": "f1",
        "OQ": "f2",
        "OR": "f3",
        "OS": "f4",
        "[15": "f5",
        "[17": "f6",
        "[18": "f7",
        "[19": "f8",
        "[20": "f9",
        "[21": "f10",
        "[23": "f11",
        "[24": "f12",
    }
    new = threading.Event()
    idle = threading.Event()
    mouse_move = threading.Event()
    mouse_report: bool = False
    idle.set()
    stopping: bool = False
    started: bool = False
    reader: threading.Thread

    @classmethod
    def start(cls):
        cls.stopping = False
        cls.reader = threading.Thread(target=cls._get_key)
        cls.reader.start()
        cls.started = True

    @classmethod
    def stop(cls):
        if cls.started and cls.reader.is_alive():
            cls.stopping = True
            try:
                cls.reader.join()
            except:
                pass

    @classmethod
    def last(cls) -> str:
        if cls.list:
            return cls.list.pop()
        else:
            return ""

    @classmethod
    def get(cls) -> str:
        if cls.list:
            return cls.list.pop(0)
        else:
            return ""

    @classmethod
    def get_mouse(cls) -> Tuple[int, int]:
        if cls.new.is_set():
            cls.new.clear()
        return cls.mouse_pos

    @classmethod
    def mouse_moved(cls) -> bool:
        if cls.mouse_move.is_set():
            cls.mouse_move.clear()
            return True
        else:
            return False

    @classmethod
    def has_key(cls) -> bool:
        return bool(cls.list)

    @classmethod
    def clear(cls):
        cls.list = []

    @classmethod
    def input_wait(cls, sec: float = 0.0, mouse: bool = False) -> bool:
        """Returns True if key is detected else waits out timer and returns False"""
        if cls.list:
            return True
        if mouse:
            Draw.now(Term.mouse_direct_on)
        cls.new.wait(sec if sec > 0 else 0.0)
        if mouse:
            Draw.now(Term.mouse_direct_off, Term.mouse_on)

        if cls.new.is_set():
            cls.new.clear()
            return True
        else:
            return False

    @classmethod
    def break_wait(cls):
        cls.list.append("_null")
        cls.new.set()
        sleep(0.01)
        cls.new.clear()

    @classmethod
    def _get_key(cls):
        """Get a key or escape sequence from stdin, convert to readable format and save to keys list. Meant to be run in it's own thread."""
        input_key: str = ""
        clean_key: str = ""
        try:
            while not cls.stopping:
                with Raw(sys.stdin):
                    if not select([sys.stdin], [], [], 0.1)[
                        0
                    ]:  # * Wait 100ms for input on stdin then restart loop to check for stop flag
                        continue
                    input_key += sys.stdin.read(
                        1
                    )  # * Read 1 key safely with blocking on
                    if (
                        input_key == "\033"
                    ):  # * If first character is a escape sequence keep reading
                        cls.idle.clear()  # * Report IO block in progress to prevent Draw functions from getting a IO Block error
                        Draw.idle.wait()  # * Wait for Draw function to finish if busy
                        with Nonblocking(
                            sys.stdin
                        ):  # * Set non blocking to prevent read stall
                            input_key += sys.stdin.read(20)
                            if input_key.startswith("\033[<"):
                                _ = sys.stdin.read(1000)
                        cls.idle.set()  # * Report IO blocking done
                    # errlog.debug(f'{repr(input_key)}')
                    if input_key == "\033":
                        clean_key = (
                            "escape"  # * Key is "escape" key if only containing \033
                        )
                    elif input_key.startswith(
                        ("\033[<0;", "\033[<35;", "\033[<64;", "\033[<65;")
                    ):  # * Detected mouse event
                        try:
                            cls.mouse_pos = (
                                int(input_key.split(";")[1]),
                                int(input_key.split(";")[2].rstrip("mM")),
                            )
                        except:
                            pass
                        else:
                            if input_key.startswith(
                                "\033[<35;"
                            ):  # * Detected mouse move in mouse direct mode
                                cls.mouse_move.set()
                                cls.new.set()
                            elif input_key.startswith(
                                "\033[<64;"
                            ):  # * Detected mouse scroll up
                                clean_key = "mouse_scroll_up"
                            elif input_key.startswith(
                                "\033[<65;"
                            ):  # * Detected mouse scroll down
                                clean_key = "mouse_scroll_down"
                            elif input_key.startswith(
                                "\033[<0;"
                            ) and input_key.endswith(
                                "m"
                            ):  # * Detected mouse click release
                                if Menu.active:
                                    clean_key = "mouse_click"
                                else:
                                    for (
                                        key_name,
                                        positions,
                                    ) in (
                                        cls.mouse.items()
                                    ):  # * Check if mouse position is clickable
                                        if list(cls.mouse_pos) in positions:
                                            clean_key = key_name
                                            break
                                    else:
                                        clean_key = "mouse_click"
                    elif input_key == "\\":
                        clean_key = "\\"  # * Clean up "\" to not return escaped
                    else:
                        for (
                            code
                        ) in (
                            cls.escape.keys()
                        ):  # * Go trough dict of escape codes to get the cleaned key name
                            if input_key.lstrip("\033").startswith(code):
                                clean_key = cls.escape[code]
                                break
                        else:  # * If not found in escape dict and length of key is 1, assume regular character
                            if len(input_key) == 1:
                                clean_key = input_key
                    if clean_key:
                        cls.list.append(
                            clean_key
                        )  # * Store up to 10 keys in input queue for later processing
                        if len(cls.list) > 10:
                            del cls.list[0]
                        clean_key = ""
                        cls.new.set()  # * Set threading event to interrupt main thread sleep
                    input_key = ""

        except Exception as e:
            errlog.exception(f"Input thread failed with exception: {e}")
            cls.idle.set()
            cls.list.clear()
            clean_quit(1, thread=True)


from util.color import Color


class Colors:
    """Standard colors for menus and dialogs"""

    default = Color("#cc", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    white = Color("#ff", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    red = Color("#bf3636", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    green = Color("#68bf36", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    blue = Color("#0fd7ff", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    yellow = Color("#db8b00", true_color=CONFIG.truecolor, low_color=LOW_COLOR)
    black_bg = Color(
        "#00", depth="bg", true_color=CONFIG.truecolor, low_color=LOW_COLOR
    )
    null = Color("", true_color=CONFIG.truecolor, low_color=LOW_COLOR)


class Theme:
    """__init__ accepts a dict containing { "color_element" : "color" }"""

    themes: Dict[str, str] = {}
    cached: Dict[str, Dict[str, str]] = {}
    current: str = ""

    # FIXME: This looks kinda crazy
    main_bg = (
        main_fg
    ) = (
        title
    ) = (
        hi_fg
    ) = (
        selected_bg
    ) = (
        selected_fg
    ) = (
        inactive_fg
    ) = (
        proc_misc
    ) = (
        cpu_box
    ) = (
        mem_box
    ) = (
        net_box
    ) = (
        proc_box
    ) = (
        div_line
    ) = (
        temp_start
    ) = (
        temp_mid
    ) = (
        temp_end
    ) = (
        cpu_start
    ) = (
        cpu_mid
    ) = (
        cpu_end
    ) = (
        free_start
    ) = (
        free_mid
    ) = (
        free_end
    ) = (
        cached_start
    ) = (
        cached_mid
    ) = (
        cached_end
    ) = (
        available_start
    ) = (
        available_mid
    ) = (
        available_end
    ) = (
        used_start
    ) = (
        used_mid
    ) = (
        used_end
    ) = (
        download_start
    ) = (
        download_mid
    ) = (
        download_end
    ) = (
        upload_start
    ) = (
        upload_mid
    ) = (
        upload_end
    ) = (
        graph_text
    ) = meter_bg = process_start = process_mid = process_end = Colors.default

    gradient: Dict[str, List[str]] = {
        "temp": [],
        "cpu": [],
        "free": [],
        "cached": [],
        "available": [],
        "used": [],
        "download": [],
        "upload": [],
        "proc": [],
        "proc_color": [],
        "process": [],
    }

    def __init__(self, theme: str):
        self.refresh()
        self._load_theme(theme)

    def __call__(self, theme: str):
        for k in self.gradient.keys():
            self.gradient[k] = []
        self._load_theme(theme)

    def _load_theme(self, theme: str):
        tdict: Dict[str, str]
        if theme in self.cached:
            tdict = self.cached[theme]
        elif theme in self.themes:
            tdict = self._load_file(self.themes[theme])
            self.cached[theme] = tdict
        else:
            raise Exception(f'No theme named "{theme}" found!')
        self.current = theme
        # if CONFIG.color_theme != theme: CONFIG.color_theme = theme
        if not "graph_text" in tdict and "inactive_fg" in tdict:
            tdict["graph_text"] = tdict["inactive_fg"]
        if not "meter_bg" in tdict and "inactive_fg" in tdict:
            tdict["meter_bg"] = tdict["inactive_fg"]
        if not "process_start" in tdict and "cpu_start" in tdict:
            tdict["process_start"] = tdict["cpu_start"]
            tdict["process_mid"] = tdict.get("cpu_mid", "")
            tdict["process_end"] = tdict.get("cpu_end", "")

        # * Get key names from DEFAULT_THEME dict to not leave any color unset if missing from theme dict
        for item, value in tdict.items():
            default = item in ["main_fg", "main_bg"]
            depth = "bg" if item in ["main_bg", "selected_bg"] else "fg"
            if item in tdict:
                setattr(self, item, Color(tdict[item], depth=depth, default=default))
            else:
                setattr(self, item, Color(value, depth=depth, default=default))

        # * Create color gradients from one, two or three colors, 101 values indexed 0-100
        self.proc_start, self.proc_mid, self.proc_end = (
            self.main_fg,
            Colors.null,
            self.inactive_fg,
        )
        self.proc_color_start, self.proc_color_mid, self.proc_color_end = (
            self.inactive_fg,
            Colors.null,
            self.process_start,
        )

        rgb: Dict[str, Tuple[int, int, int]]
        colors: List[List[int]] = []
        for name in self.gradient:
            rgb = {
                "start": getattr(self, f"{name}_start").dec,
                "mid": getattr(self, f"{name}_mid").dec,
                "end": getattr(self, f"{name}_end").dec,
            }
            colors = [list(getattr(self, f"{name}_start"))]
            if rgb["end"][0] >= 0:
                r = 50 if rgb["mid"][0] >= 0 else 100
                for first, second in ["start", "mid" if r == 50 else "end"], [
                    "mid",
                    "end",
                ]:
                    for i in range(r):
                        colors += [
                            [
                                rgb[first][n]
                                + i * (rgb[second][n] - rgb[first][n]) // r
                                for n in range(3)
                            ]
                        ]
                    if r == 100:
                        break
                self.gradient[name] += [Color.fg(*color) for color in colors]

            else:
                c = Color.fg(*rgb["start"])
                self.gradient[name] += [c] * 101
        # * Set terminal colors
        Term.fg = f"{self.main_fg}"
        Term.bg = f"{self.main_bg}" if CONFIG.theme_background else "\033[49m"
        Draw.now(self.main_fg, self.main_bg)

    @classmethod
    def refresh(cls):
        """Sets themes dict with names and paths to all found themes"""
        cls.themes = {"default": "bpytop-themes/default_black.theme"}
        try:
            for d in (THEME_DIR, USER_THEME_DIR):
                if not d:
                    continue
                for f in os.listdir(d):
                    if f.endswith(".theme"):
                        cls.themes[
                            f'{"" if d == THEME_DIR else "+"}{f[:-6]}'
                        ] = f"{d}/{f}"
        except Exception as e:
            errlog.exception(str(e))

    @staticmethod
    def _load_file(path: str) -> Dict[str, str]:
        """Load a bashtop formatted theme file and return a dict"""
        new_theme: Dict[str, str] = {}
        try:
            with open(path, "r") as f:
                for line in f:
                    if not line.startswith("theme["):
                        continue
                    key = line[6 : line.find("]")]
                    s = line.find('"')
                    value = line[s + 1 : line.find('"', s + 1)]
                    new_theme[key] = value
        except Exception as e:
            errlog.exception(str(e))

        return new_theme


class Graph:
    """Class for creating and adding to graphs
    * __str__ : returns graph as a string
    * add(value: int) : adds a value to graph and returns it as a string
    * __call__ : same as add
    """

    out: str
    width: int
    height: int
    graphs: Dict[bool, List[str]]
    colors: List[str]
    invert: bool
    max_value: int
    color_max_value: int
    offset: int
    no_zero: bool
    round_up_low: bool
    current: bool
    last: int
    lowest: int = 0
    symbol: Dict[float, str]

    def __init__(
        self,
        width: int,
        height: int,
        color: Union[List[str], Color, None],
        data: List[int],
        invert: bool = False,
        max_value: int = 0,
        offset: int = 0,
        color_max_value: Union[int, None] = None,
        no_zero: bool = False,
        round_up_low: bool = False,
    ):
        self.graphs: Dict[bool, List[str]] = {False: [], True: []}
        self.current: bool = True
        self.width = width
        self.height = height
        self.invert = invert
        self.offset = offset
        self.round_up_low = round_up_low
        self.no_zero = no_zero or round_up_low
        if not data:
            data = [0]
        if max_value:
            self.lowest = 1 if self.round_up_low else 0
            self.max_value = max_value
            data = [
                fmt.min_max(
                    (v + offset) * 100 // (max_value + offset),
                    fmt.min_max(v + offset, 0, self.lowest),
                    100,
                )
                for v in data
            ]  # * Convert values to percentage values of max_value with max_value as ceiling
        else:
            self.max_value = 0
        if color_max_value:
            self.color_max_value = color_max_value
        else:
            self.color_max_value = self.max_value
        if self.color_max_value and self.max_value:
            color_scale = int(100.0 * self.max_value / self.color_max_value)
        else:
            color_scale = 100
        self.colors: List[str] = []
        if isinstance(color, list) and height > 1:
            for i in range(1, height + 1):
                self.colors.insert(
                    0, color[min(100, i * color_scale // height)]
                )  # * Calculate colors of graph
            if invert:
                self.colors.reverse()
        elif isinstance(color, Color) and height > 1:
            self.colors = [f"{color}" for _ in range(height)]
        else:
            if isinstance(color, list):
                self.colors = color
            elif isinstance(color, Color):
                self.colors = [f"{color}" for _ in range(101)]
        if self.height == 1:
            self.symbol = Symbol.graph_down_small if invert else Symbol.graph_up_small
        else:
            self.symbol = Symbol.graph_down if invert else Symbol.graph_up
        value_width: int = ceil(len(data) / 2)
        filler: str = ""
        if (
            value_width > width
        ):  # * If the size of given data set is bigger then width of graph, shrink data set
            data = data[-(width * 2) :]
            value_width = ceil(len(data) / 2)
        elif (
            value_width < width
        ):  # * If the size of given data set is smaller then width of graph, fill graph with whitespace
            filler = self.symbol[0.0] * (width - value_width)
        if len(data) % 2:
            data.insert(0, 0)
        for _ in range(height):
            for b in [True, False]:
                self.graphs[b].append(filler)
        self._create(data, new=True)

    def _create(self, data: List[int], new: bool = False):
        h_high: int
        h_low: int
        value: Dict[str, int] = {"left": 0, "right": 0}
        val: int
        side: str

        # * Create the graph
        for h in range(self.height):
            h_high = (
                round(100 * (self.height - h) / self.height) if self.height > 1 else 100
            )
            h_low = (
                round(100 * (self.height - (h + 1)) / self.height)
                if self.height > 1
                else 0
            )
            for v in range(len(data)):
                if new:
                    self.current = bool(v % 2)  # * Switch between True and False graphs
                if new and v == 0:
                    self.last = 0
                for val, side in [self.last, "left"], [data[v], "right"]:  # type: ignore
                    if val >= h_high:
                        value[side] = 4
                    elif val <= h_low:
                        value[side] = 0
                    else:
                        if self.height == 1:
                            value[side] = round(val * 4 / 100 + 0.5)
                        else:
                            value[side] = round(
                                (val - h_low) * 4 / (h_high - h_low) + 0.1
                            )
                    if (
                        self.no_zero
                        and not (new and v == 0 and side == "left")
                        and h == self.height - 1
                        and value[side] < 1
                        and not (self.round_up_low and val == 0)
                    ):
                        value[side] = 1
                if new:
                    self.last = data[v]
                self.graphs[self.current][h] += self.symbol[
                    float(value["left"] + value["right"] / 10)
                ]
        if data:
            self.last = data[-1]
        self.out = ""

        if self.height == 1:
            self.out += f'{"" if not self.colors else (THEME.inactive_fg if self.last < 5 else self.colors[self.last])}{self.graphs[self.current][0]}'
        elif self.height > 1:
            for h in range(self.height):
                if h > 0:
                    self.out += f"{Mv.d(1)}{Mv.l(self.width)}"
                self.out += f'{"" if not self.colors else self.colors[h]}{self.graphs[self.current][h if not self.invert else (self.height - 1) - h]}'
        if self.colors:
            self.out += f"{Term.fg}"

    def __call__(self, value: Union[int, None] = None) -> str:
        if not isinstance(value, int):
            return self.out
        self.current = not self.current
        if self.height == 1:
            if self.graphs[self.current][0].startswith(self.symbol[0.0]):
                self.graphs[self.current][0] = self.graphs[self.current][0].replace(
                    self.symbol[0.0], "", 1
                )
            else:
                self.graphs[self.current][0] = self.graphs[self.current][0][1:]
        else:
            for n in range(self.height):
                self.graphs[self.current][n] = self.graphs[self.current][n][1:]
        if self.max_value:
            value = fmt.min_max(
                (value + self.offset) * 100 // (self.max_value + self.offset),
                fmt.min_max(value + self.offset, 0, self.lowest),
                100,
            )
        self._create([value])
        return self.out

    def add(self, value: Union[int, None] = None) -> str:
        return self.__call__(value)

    def __str__(self):
        return self.out

    def __repr__(self):
        return repr(self.out)


class Graphs:
    """Holds all graphs and lists of graphs for dynamically created graphs"""

    cpu: Dict[str, Graph] = {}
    cores: List[Graph] = [NotImplemented] * THREADS
    temps: List[Graph] = [NotImplemented] * (THREADS + 1)
    net: Dict[str, Graph] = {}
    detailed_cpu: Graph = NotImplemented
    detailed_mem: Graph = NotImplemented
    pid_cpu: Dict[int, Graph] = {}
    disk_io: Dict[str, Dict[str, Graph]] = {}


class Meter:
    """Creates a percentage meter
    __init__(value, width, theme, gradient_name) to create new meter
    __call__(value) to set value and return meter as a string
    __str__ returns last set meter as a string
    """

    out: str
    color_gradient: List[str]
    color_inactive: Color
    gradient_name: str
    width: int
    invert: bool
    saved: Dict[int, str]

    def __init__(
        self, value: int, width: int, gradient_name: str, invert: bool = False
    ):
        self.gradient_name = gradient_name
        self.color_gradient = THEME.gradient[gradient_name]
        self.color_inactive = THEME.meter_bg
        self.width = width
        self.saved = {}
        self.invert = invert
        self.out = self._create(value)

    def __call__(self, value: Union[int, None]) -> str:
        if not isinstance(value, int):
            return self.out
        if value > 100:
            value = 100
        elif value < 0:
            value = 100
        if value in self.saved:
            self.out = self.saved[value]
        else:
            self.out = self._create(value)
        return self.out

    def __str__(self) -> str:
        return self.out

    def __repr__(self):
        return repr(self.out)

    def _create(self, value: int) -> str:
        if value > 100:
            value = 100
        elif value < 0:
            value = 100
        out: str = ""
        for i in range(1, self.width + 1):
            if value >= round(i * 100 / self.width):
                out += f"{self.color_gradient[round(i * 100 / self.width) if not self.invert else round(100 - (i * 100 / self.width))]}{Symbol.meter}"
            else:
                out += self.color_inactive(Symbol.meter * (self.width + 1 - i))
                break
        else:
            out += f"{Term.fg}"
        if not value in self.saved:
            self.saved[value] = out
        return out


class Meters:
    cpu: Meter
    battery: Meter
    mem: Dict[str, Union[Meter, Graph]] = {}
    swap: Dict[str, Union[Meter, Graph]] = {}
    disks_used: Dict[str, Meter] = {}
    disks_free: Dict[str, Meter] = {}


class Box:
    """Box class with all needed attributes for create_box() function"""

    name: str
    num: int = 0
    boxes: List = []
    view_modes: Dict[str, List] = {
        "full": ["cpu", "mem", "net", "proc"],
        "stat": ["cpu", "mem", "net"],
        "proc": ["cpu", "proc"],
    }
    view_mode: str
    for view_mode in view_modes:
        if sorted(CONFIG.shown_boxes.split(), key=str.lower) == view_modes[view_mode]:
            break
    else:
        view_mode = "user"
        view_modes["user"] = CONFIG.shown_boxes.split()
    height_p: int
    width_p: int
    x: int
    y: int
    width: int
    height: int
    out: str
    bg: str
    _b_cpu_h: int
    _b_mem_h: int
    redraw_all: bool
    buffers: List[str] = []
    c_counter: int = 0
    clock_on: bool = False
    clock: str = ""
    clock_len: int = 0
    resized: bool = False
    clock_custom_format: Dict[str, Any] = {
        "/host": os.uname()[1],
        "/user": os.environ.get("USER") or pwd.getpwuid(os.getuid())[0],
        "/uptime": "",
    }
    if clock_custom_format["/host"].endswith(".local"):
        clock_custom_format["/host"] = clock_custom_format["/host"].replace(
            ".local", ""
        )

    @classmethod
    def calc_sizes(cls):
        """Calculate sizes of boxes"""
        cls.boxes = CONFIG.shown_boxes.split()
        for sub in cls.__subclasses__():
            sub._calc_size()  # type: ignore
            sub.resized = True  # type: ignore

    @classmethod
    def draw_update_ms(cls, now: bool = True):
        if not "cpu" in cls.boxes:
            return
        update_string: str = f"{CONFIG.update_ms}ms"
        xpos: int = CpuBox.x + CpuBox.width - len(update_string) - 15
        if not "+" in Key.mouse:
            Key.mouse["+"] = [[xpos + 7 + i, CpuBox.y] for i in range(3)]
            Key.mouse["-"] = [
                [CpuBox.x + CpuBox.width - 4 + i, CpuBox.y] for i in range(3)
            ]
        Draw.buffer(
            "update_ms!" if now and not Menu.active else "update_ms",
            f'{Mv.to(CpuBox.y, xpos)}{THEME.cpu_box(Symbol.h_line * 7, Symbol.title_left)}{Fx.b}{THEME.hi_fg("+")} ',
            f'{THEME.title(update_string)} {THEME.hi_fg("-")}{Fx.ub}{THEME.cpu_box(Symbol.title_right)}',
            only_save=Menu.active,
            once=True,
        )
        if now and not Menu.active:
            Draw.clear("update_ms")
            if (
                CONFIG.show_battery
                and hasattr(psutil, "sensors_battery")
                and psutil.sensors_battery()
            ):
                Draw.out("battery")

    @classmethod
    def draw_clock(cls, force: bool = False):
        if not "cpu" in cls.boxes or not cls.clock_on:
            return
        cls.c_counter += 1
        if cls.c_counter > 3600 / (Config.update_ms / 1000):
            tzset()
            cls.c_counter = 0
        out: str = ""
        if force:
            pass
        elif Term.resized or strftime(CONFIG.draw_clock) == cls.clock:
            return
        clock_string = cls.clock = strftime(CONFIG.draw_clock)
        for custom in cls.clock_custom_format:
            if custom in clock_string:
                if custom == "/uptime":
                    cls.clock_custom_format["/uptime"] = CpuCollector.uptime
                clock_string = clock_string.replace(
                    custom, cls.clock_custom_format[custom]
                )
        clock_len = len(clock_string[: (CpuBox.width - 56)])
        if cls.clock_len != clock_len and not CpuBox.resized:
            out = f"{Mv.to(CpuBox.y, ((CpuBox.width)//2)-(cls.clock_len//2))}{Fx.ub}{THEME.cpu_box}{Symbol.h_line * cls.clock_len}"
        cls.clock_len = clock_len
        now: bool = False if Menu.active else not force
        out += (
            f"{Mv.to(CpuBox.y, ((CpuBox.width)//2)-(clock_len//2))}{Fx.ub}{THEME.cpu_box}"
            f"{Symbol.title_left}{Fx.b}{THEME.title(clock_string[:clock_len])}{Fx.ub}{THEME.cpu_box}{Symbol.title_right}{Term.fg}"
        )
        Draw.buffer("clock", out, z=1, now=now, once=not force, only_save=Menu.active)
        if now and not Menu.active:
            if (
                CONFIG.show_battery
                and hasattr(psutil, "sensors_battery")
                and psutil.sensors_battery()
            ):
                Draw.out("battery")

    @classmethod
    def empty_bg(cls) -> str:
        return (
            f"{Term.clear}"
            + (
                f"{Banner.draw(Term.height // 2 - 10, center=True)}"
                f"{Mv.d(1)}{Mv.l(46)}{Colors.black_bg}{Colors.default}{Fx.b}[esc] Menu"
                f"{Mv.r(25)}{Fx.i}Version: {VERSION}{Fx.ui}"
                if Term.height > 22
                else ""
            )
            + f"{Mv.d(1)}{Mv.l(34)}{Fx.b}All boxes hidden!"
            f"{Mv.d(1)}{Mv.l(17)}{Fx.b}[1] {Fx.ub}Toggle CPU box"
            f"{Mv.d(1)}{Mv.l(18)}{Fx.b}[2] {Fx.ub}Toggle MEM box"
            f"{Mv.d(1)}{Mv.l(18)}{Fx.b}[3] {Fx.ub}Toggle NET box"
            f"{Mv.d(1)}{Mv.l(18)}{Fx.b}[4] {Fx.ub}Toggle PROC box"
            f"{Mv.d(1)}{Mv.l(19)}{Fx.b}[m] {Fx.ub}Cycle presets"
            f"{Mv.d(1)}{Mv.l(17)}{Fx.b}[q] Quit {Fx.ub}{Term.bg}{Term.fg}"
        )

    @classmethod
    def draw_bg(cls, now: bool = True):
        """Draw all boxes outlines and titles"""
        out: str = ""
        if not cls.boxes:
            out = cls.empty_bg()
        else:
            out = "".join(sub._draw_bg() for sub in cls.__subclasses__())  # type: ignore
        Draw.buffer("bg", out, now=now, z=1000, only_save=Menu.active, once=True)
        cls.draw_update_ms(now=now)
        if CONFIG.draw_clock:
            cls.draw_clock(force=True)


class SubBox:
    box_x: int = 0
    box_y: int = 0
    box_width: int = 0
    box_height: int = 0
    box_columns: int = 0
    column_size: int = 0


class CpuBox(Box, SubBox):
    name = "cpu"
    num = 1
    x = 1
    y = 1
    height_p = 32
    width_p = 100
    min_w: int = 60
    min_h: int = 8
    resized: bool = True
    redraw: bool = False
    buffer: str = "cpu"
    battery_percent: int = 1000
    battery_secs: int = 0
    battery_status: str = "Unknown"
    old_battery_pos = 0
    old_battery_len = 0
    battery_path: Union[str, None] = ""
    battery_clear: bool = False
    battery_symbols: Dict[str, str] = {
        "Charging": "▲",
        "Discharging": "▼",
        "Full": "■",
        "Not charging": "■",
    }
    clock_block: bool = True
    Box.buffers.append(buffer)

    @classmethod
    def _calc_size(cls):
        if not "cpu" in cls.boxes:
            Box._b_cpu_h = 0
            cls.width = Term.width
            return
        cpu = CpuCollector
        height_p: int
        if cls.boxes == ["cpu"]:
            height_p = 100
        else:
            height_p = cls.height_p
        cls.width = round(Term.width * cls.width_p / 100)
        cls.height = round(Term.height * height_p / 100)
        if cls.height < 8:
            cls.height = 8
        Box._b_cpu_h = cls.height
        # THREADS = 64
        cls.box_columns = ceil((THREADS + 1) / (cls.height - 5))
        if cls.box_columns * (20 + 13 if cpu.got_sensors else 21) < cls.width - (
            cls.width // 3
        ):
            cls.column_size = 2
            cls.box_width = (20 + 13 if cpu.got_sensors else 21) * cls.box_columns - (
                (cls.box_columns - 1) * 1
            )
        elif cls.box_columns * (15 + 6 if cpu.got_sensors else 15) < cls.width - (
            cls.width // 3
        ):
            cls.column_size = 1
            cls.box_width = (15 + 6 if cpu.got_sensors else 15) * cls.box_columns - (
                (cls.box_columns - 1) * 1
            )
        elif cls.box_columns * (8 + 6 if cpu.got_sensors else 8) < cls.width - (
            cls.width // 3
        ):
            cls.column_size = 0
        else:
            cls.box_columns = (cls.width - cls.width // 3) // (
                8 + 6 if cpu.got_sensors else 8
            )
            cls.column_size = 0

        if cls.column_size == 0:
            cls.box_width = (8 + 6 if cpu.got_sensors else 8) * cls.box_columns + 1

        cls.box_height = ceil(THREADS / cls.box_columns) + 4

        if cls.box_height > cls.height - 2:
            cls.box_height = cls.height - 2
        cls.box_x = (cls.width - 1) - cls.box_width
        cls.box_y = cls.y + ceil((cls.height - 2) / 2) - ceil(cls.box_height / 2) + 1

    @classmethod
    def _draw_bg(cls) -> str:
        if not "cpu" in cls.boxes:
            return ""
        if not "M" in Key.mouse:
            Key.mouse["M"] = [[cls.x + 10 + i, cls.y] for i in range(6)]
        return (
            f"{create_box(box=cls, line_color=THEME.cpu_box)}"
            f'{Mv.to(cls.y, cls.x + 10)}{THEME.cpu_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg("M")}{THEME.title("enu")}{Fx.ub}{THEME.cpu_box(Symbol.title_right)}'
            f"{create_box(x=cls.box_x, y=cls.box_y, width=cls.box_width, height=cls.box_height, line_color=THEME.div_line, fill=False, title=CPU_NAME[:cls.box_width - 14] if not CONFIG.custom_cpu_name else CONFIG.custom_cpu_name[:cls.box_width - 14])}"
        )

    @classmethod
    def battery_activity(cls) -> bool:
        if not hasattr(psutil, "sensors_battery") or psutil.sensors_battery() == None:
            if cls.battery_percent != 1000:
                cls.battery_clear = True
            return False

        if cls.battery_path == "":
            cls.battery_path = None
            if os.path.isdir("/sys/class/power_supply"):
                for directory in sorted(os.listdir("/sys/class/power_supply")):
                    if directory.startswith("BAT") or "battery" in directory.lower():
                        cls.battery_path = f"/sys/class/power_supply/{directory}/"
                        break

        return_true: bool = False
        percent: int = ceil(getattr(psutil.sensors_battery(), "percent", 0))
        if percent != cls.battery_percent:
            cls.battery_percent = percent
            return_true = True

        seconds: int = getattr(psutil.sensors_battery(), "secsleft", 0)
        if seconds != cls.battery_secs:
            cls.battery_secs = seconds
            return_true = True

        status: str = "not_set"
        if cls.battery_path:
            status = readfile(cls.battery_path + "status", default="not_set")
        if (
            status == "not_set"
            and getattr(psutil.sensors_battery(), "power_plugged", None) == True
        ):
            status = "Charging" if cls.battery_percent < 100 else "Full"
        elif (
            status == "not_set"
            and getattr(psutil.sensors_battery(), "power_plugged", None) == False
        ):
            status = "Discharging"
        elif status == "not_set":
            status = "Unknown"
        if status != cls.battery_status:
            cls.battery_status = status
            return_true = True

        return return_true or cls.resized or cls.redraw or Menu.active

    @classmethod
    def _draw_fg(cls):
        if not "cpu" in cls.boxes:
            return
        cpu = CpuCollector
        if cpu.redraw:
            cls.redraw = True
        out: str = ""
        out_misc: str = ""
        lavg: str = ""
        x, y, w, h = cls.x + 1, cls.y + 1, cls.width - 2, cls.height - 2
        bx, by, bw, bh = (
            cls.box_x + 1,
            cls.box_y + 1,
            cls.box_width - 2,
            cls.box_height - 2,
        )
        hh: int = ceil(h / 2)
        hh2: int = h - hh
        mid_line: bool = False
        temp: int = 0
        unit: str = ""
        if (
            not CONFIG.cpu_single_graph
            and CONFIG.cpu_graph_upper != CONFIG.cpu_graph_lower
        ):
            mid_line = True
            if h % 2:
                hh = floor(h / 2)
            else:
                hh2 -= 1

        hide_cores: bool = (
            cpu.cpu_temp_only or not CONFIG.show_coretemp
        ) and cpu.got_sensors
        ct_width: int = (max(6, 6 * cls.column_size)) * hide_cores

        if cls.resized or cls.redraw:
            if not "m" in Key.mouse:
                Key.mouse["m"] = [[cls.x + 16 + i, cls.y] for i in range(12)]
            out_misc += f'{Mv.to(cls.y, cls.x + 16)}{THEME.cpu_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg("m")}{THEME.title}ode:{Box.view_mode}{Fx.ub}{THEME.cpu_box(Symbol.title_right)}'
            Graphs.cpu["up"] = Graph(
                w - bw - 3,
                (h if CONFIG.cpu_single_graph else hh),
                THEME.gradient["cpu"],
                cpu.cpu_upper,
                round_up_low=True,
            )
            if not CONFIG.cpu_single_graph:
                Graphs.cpu["down"] = Graph(
                    w - bw - 3,
                    hh2,
                    THEME.gradient["cpu"],
                    cpu.cpu_lower,
                    invert=CONFIG.cpu_invert_lower,
                    round_up_low=True,
                )
            Meters.cpu = Meter(
                cpu.cpu_usage[0][-1], bw - (21 if cpu.got_sensors else 9), "cpu"
            )
            if cls.column_size > 0 or ct_width > 0:
                for n in range(THREADS):
                    Graphs.cores[n] = Graph(
                        5 * cls.column_size + ct_width, 1, None, cpu.cpu_usage[n + 1]
                    )
            if cpu.got_sensors:
                Graphs.temps[0] = Graph(
                    5, 1, None, cpu.cpu_temp[0], max_value=cpu.cpu_temp_crit, offset=-23
                )
                if cls.column_size > 1:
                    for n in range(1, THREADS + 1):
                        if not cpu.cpu_temp[n]:
                            continue
                        Graphs.temps[n] = Graph(
                            5,
                            1,
                            None,
                            cpu.cpu_temp[n],
                            max_value=cpu.cpu_temp_crit,
                            offset=-23,
                        )
            Draw.buffer("cpu_misc", out_misc, only_save=True)

        if CONFIG.show_battery and cls.battery_activity():
            bat_out: str = ""
            if cls.battery_secs > 0:
                battery_time: str = f" {cls.battery_secs // 3600:02}:{(cls.battery_secs % 3600) // 60:02}"
            else:
                battery_time = ""
            if not hasattr(Meters, "battery") or cls.resized:
                Meters.battery = Meter(cls.battery_percent, 10, "cpu", invert=True)
            battery_symbol: str = cls.battery_symbols.get(cls.battery_status, "○")
            battery_len: int = (
                len(f"{CONFIG.update_ms}")
                + (11 if cls.width >= 100 else 0)
                + len(battery_time)
                + len(f"{cls.battery_percent}")
            )
            battery_pos = cls.width - battery_len - 17
            if (
                (
                    battery_pos != cls.old_battery_pos
                    or battery_len != cls.old_battery_len
                )
                and cls.old_battery_pos > 0
                and not cls.resized
            ):
                bat_out += f"{Mv.to(y-1, cls.old_battery_pos)}{THEME.cpu_box(Symbol.h_line*(cls.old_battery_len+4))}"
            cls.old_battery_pos, cls.old_battery_len = battery_pos, battery_len
            bat_out += (
                f"{Mv.to(y-1, battery_pos)}{THEME.cpu_box(Symbol.title_left)}{Fx.b}{THEME.title}BAT{battery_symbol} {cls.battery_percent}%"
                + (
                    ""
                    if cls.width < 100
                    else f" {Fx.ub}{Meters.battery(cls.battery_percent)}{Fx.b}"
                )
                + f"{THEME.title}{battery_time}{Fx.ub}{THEME.cpu_box(Symbol.title_right)}"
            )
            Draw.buffer("battery", f"{bat_out}{Term.fg}", only_save=Menu.active)
        elif cls.battery_clear:
            out += f"{Mv.to(y-1, cls.old_battery_pos)}{THEME.cpu_box(Symbol.h_line*(cls.old_battery_len+4))}"
            cls.battery_clear = False
            cls.battery_percent = 1000
            cls.battery_secs = 0
            cls.battery_status = "Unknown"
            cls.old_battery_pos = 0
            cls.old_battery_len = 0
            cls.battery_path = ""
            Draw.clear("battery", saved=True)

        cx = cy = cc = 0
        ccw = (bw + 1) // cls.box_columns
        if cpu.cpu_freq:
            freq: str = (
                f"{cpu.cpu_freq} Mhz"
                if cpu.cpu_freq < 1000
                else f"{float(cpu.cpu_freq / 1000):.1f} GHz"
            )
            out += f"{Mv.to(by - 1, bx + bw - 9)}{THEME.div_line(Symbol.title_left)}{Fx.b}{THEME.title(freq)}{Fx.ub}{THEME.div_line(Symbol.title_right)}"
        out += f'{Mv.to(y, x)}{Graphs.cpu["up"](None if cls.resized else cpu.cpu_upper[-1])}'
        if mid_line:
            out += (
                f"{Mv.to(y+hh, x-1)}{THEME.cpu_box(Symbol.title_right)}{THEME.div_line}{Symbol.h_line * (w - bw - 3)}{THEME.div_line(Symbol.title_left)}"
                f"{Mv.to(y+hh, x+((w-bw)//2)-((len(CONFIG.cpu_graph_upper)+len(CONFIG.cpu_graph_lower))//2)-4)}{THEME.main_fg}{CONFIG.cpu_graph_upper}{Mv.r(1)}▲▼{Mv.r(1)}{CONFIG.cpu_graph_lower}"
            )
        if not CONFIG.cpu_single_graph and Graphs.cpu.get("down"):
            out += f'{Mv.to(y + hh + (1 * mid_line), x)}{Graphs.cpu["down"](None if cls.resized else cpu.cpu_lower[-1])}'
        out += (
            f'{THEME.main_fg}{Mv.to(by + cy, bx + cx)}{Fx.b}{"CPU "}{Fx.ub}{Meters.cpu(cpu.cpu_usage[0][-1])}'
            f'{THEME.gradient["cpu"][cpu.cpu_usage[0][-1]]}{cpu.cpu_usage[0][-1]:>4}{THEME.main_fg}%'
        )
        if cpu.got_sensors:
            try:
                temp, unit = temperature(cpu.cpu_temp[0][-1], CONFIG.temp_scale)
                out += (
                    f'{THEME.inactive_fg} ⡀⡀⡀⡀⡀{Mv.l(5)}{THEME.gradient["temp"][fmt.min_max(cpu.cpu_temp[0][-1], 0, cpu.cpu_temp_crit) * 100 // cpu.cpu_temp_crit]}{Graphs.temps[0](None if cls.resized else cpu.cpu_temp[0][-1])}'
                    f"{temp:>4}{THEME.main_fg}{unit}"
                )
            except:
                cpu.got_sensors = False

        cy += 1
        for n in range(1, THREADS + 1):
            out += f'{THEME.main_fg}{Mv.to(by + cy, bx + cx)}{Fx.b + "C" + Fx.ub if THREADS < 100 else ""}{str(n):<{2 if cls.column_size == 0 else 3}}'
            if cls.column_size > 0 or ct_width > 0:
                out += f'{THEME.inactive_fg}{"⡀" * (5 * cls.column_size + ct_width)}{Mv.l(5 * cls.column_size + ct_width)}{THEME.gradient["cpu"][cpu.cpu_usage[n][-1]]}{Graphs.cores[n-1](None if cls.resized else cpu.cpu_usage[n][-1])}'
            else:
                out += f'{THEME.gradient["cpu"][cpu.cpu_usage[n][-1]]}'
            out += f"{cpu.cpu_usage[n][-1]:>{3 if cls.column_size < 2 else 4}}{THEME.main_fg}%"
            if cpu.got_sensors and cpu.cpu_temp[n] and not hide_cores:
                try:
                    temp, unit = temperature(cpu.cpu_temp[n][-1], CONFIG.temp_scale)
                    if cls.column_size > 1:
                        out += f'{THEME.inactive_fg} ⡀⡀⡀⡀⡀{Mv.l(5)}{THEME.gradient["temp"][fmt.min_max(cpu.cpu_temp[n][-1], 0, cpu.cpu_temp_crit) * 100 // cpu.cpu_temp_crit]}{Graphs.temps[n](None if cls.resized else cpu.cpu_temp[n][-1])}'
                    else:
                        out += f'{THEME.gradient["temp"][fmt.min_max(temp, 0, cpu.cpu_temp_crit) * 100 // cpu.cpu_temp_crit]}'
                    out += f"{temp:>4}{THEME.main_fg}{unit}"
                except:
                    cpu.got_sensors = False
            elif cpu.got_sensors and not hide_cores:
                out += f"{Mv.r(max(6, 6 * cls.column_size))}"
            out += f"{THEME.div_line(Symbol.v_line)}"
            cy += 1
            if cy > ceil(THREADS / cls.box_columns) and n != THREADS:
                cc += 1
                cy = 1
                cx = ccw * cc
                if cc == cls.box_columns:
                    break

        if cy < bh - 1:
            cy = bh - 1

        if cy < bh and cc < cls.box_columns:
            if cls.column_size == 2 and cpu.got_sensors:
                lavg = f' Load AVG:  {"   ".join(str(l) for l in cpu.load_avg):^19.19}'
            elif cls.column_size == 2 or (cls.column_size == 1 and cpu.got_sensors):
                lavg = f'LAV: {" ".join(str(l) for l in cpu.load_avg):^14.14}'
            elif cls.column_size == 1 or (cls.column_size == 0 and cpu.got_sensors):
                lavg = f'L {" ".join(str(round(l, 1)) for l in cpu.load_avg):^11.11}'
            else:
                lavg = f'{" ".join(str(round(l, 1)) for l in cpu.load_avg[:2]):^7.7}'
            out += f"{Mv.to(by + cy, bx + cx)}{THEME.main_fg}{lavg}{THEME.div_line(Symbol.v_line)}"

        if CONFIG.show_uptime:
            out += f'{Mv.to(y + (0 if not CONFIG.cpu_invert_lower or CONFIG.cpu_single_graph else h - 1), x + 1)}{THEME.graph_text}{Fx.trans("up " + cpu.uptime)}'

        Draw.buffer(cls.buffer, f"{out_misc}{out}{Term.fg}", only_save=Menu.active)
        cls.resized = cls.redraw = cls.clock_block = False


class MemBox(Box):
    name = "mem"
    num = 2
    height_p = 38
    width_p = 45
    min_w: int = 36
    min_h: int = 10
    x = 1
    y = 1
    mem_meter: int = 0
    mem_size: int = 0
    disk_meter: int = 0
    divider: int = 0
    mem_width: int = 0
    disks_width: int = 0
    disks_io_h: int = 0
    disks_io_order: List[str] = []
    graph_speeds: Dict[str, int] = {}
    graph_height: int
    resized: bool = True
    redraw: bool = False
    buffer: str = "mem"
    swap_on: bool = CONFIG.show_swap
    Box.buffers.append(buffer)
    mem_names: List[str] = ["used", "available", "cached", "free"]
    swap_names: List[str] = ["used", "free"]

    @classmethod
    def _calc_size(cls):
        if not "mem" in cls.boxes:
            Box._b_mem_h = 0
            cls.width = Term.width
            return
        width_p: int
        height_p: int
        if not "proc" in cls.boxes:
            width_p = 100
        else:
            width_p = cls.width_p

        if not "cpu" in cls.boxes:
            height_p = 60 if "net" in cls.boxes else 98
        elif not "net" in cls.boxes:
            height_p = 98 - CpuBox.height_p
        else:
            height_p = cls.height_p

        cls.width = round(Term.width * width_p / 100)
        cls.height = round(Term.height * height_p / 100) + 1
        if cls.height + Box._b_cpu_h > Term.height:
            cls.height = Term.height - Box._b_cpu_h
        Box._b_mem_h = cls.height
        cls.y = Box._b_cpu_h + 1
        if CONFIG.show_disks:
            cls.mem_width = ceil((cls.width - 3) / 2)
            cls.disks_width = cls.width - cls.mem_width - 3
            if cls.mem_width + cls.disks_width < cls.width - 2:
                cls.mem_width += 1
            cls.divider = cls.x + cls.mem_width
        else:
            cls.mem_width = cls.width - 1

        item_height: int = 6 if cls.swap_on and not CONFIG.swap_disk else 4
        if (
            cls.height - (3 if cls.swap_on and not CONFIG.swap_disk else 2)
            > 2 * item_height
        ):
            cls.mem_size = 3
        elif cls.mem_width > 25:
            cls.mem_size = 2
        else:
            cls.mem_size = 1

        cls.mem_meter = (
            cls.width
            - (cls.disks_width if CONFIG.show_disks else 0)
            - (9 if cls.mem_size > 2 else 20)
        )
        if cls.mem_size == 1:
            cls.mem_meter += 6
        if cls.mem_meter < 1:
            cls.mem_meter = 0

        if CONFIG.mem_graphs:
            cls.graph_height = round(
                (
                    (cls.height - (2 if cls.swap_on and not CONFIG.swap_disk else 1))
                    - (2 if cls.mem_size == 3 else 1) * item_height
                )
                / item_height
            )
            if cls.graph_height == 0:
                cls.graph_height = 1
            if cls.graph_height > 1:
                cls.mem_meter += 6
        else:
            cls.graph_height = 0

        if CONFIG.show_disks:
            cls.disk_meter = cls.width - cls.mem_width - 23
            if cls.disks_width < 25:
                cls.disk_meter += 10
            if cls.disk_meter < 1:
                cls.disk_meter = 0

    @classmethod
    def _draw_bg(cls) -> str:
        if not "mem" in cls.boxes:
            return ""
        out: str = ""
        out += f"{create_box(box=cls, line_color=THEME.mem_box)}"
        if CONFIG.show_disks:
            out += (
                f'{Mv.to(cls.y, cls.divider + 2)}{THEME.mem_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg("d")}{THEME.title("isks")}{Fx.ub}{THEME.mem_box(Symbol.title_right)}'
                f"{Mv.to(cls.y, cls.divider)}{THEME.mem_box(Symbol.div_up)}"
                f"{Mv.to(cls.y + cls.height - 1, cls.divider)}{THEME.mem_box(Symbol.div_down)}{THEME.div_line}"
                f'{"".join(f"{Mv.to(cls.y + i, cls.divider)}{Symbol.v_line}" for i in range(1, cls.height - 1))}'
            )
            Key.mouse["d"] = [[cls.divider + 3 + i, cls.y] for i in range(5)]
        else:
            out += f'{Mv.to(cls.y, cls.x + cls.width - 9)}{THEME.mem_box(Symbol.title_left)}{THEME.hi_fg("d")}{THEME.title("isks")}{THEME.mem_box(Symbol.title_right)}'
            Key.mouse["d"] = [[cls.x + cls.width - 8 + i, cls.y] for i in range(5)]
        return out

    @classmethod
    def _draw_fg(cls):
        if not "mem" in cls.boxes:
            return
        mem = MemCollector
        if mem.redraw:
            cls.redraw = True
        out: str = ""
        out_misc: str = ""
        gbg: str = ""
        gmv: str = ""
        gli: str = ""
        x, y, w, h = cls.x + 1, cls.y + 1, cls.width - 2, cls.height - 2
        if cls.resized or cls.redraw:
            cls.redraw = True
            cls._calc_size()
            out_misc += cls._draw_bg()
            Meters.mem = {}
            Meters.swap = {}
            Meters.disks_used = {}
            Meters.disks_free = {}
            if cls.mem_meter > 0:
                for name in cls.mem_names:
                    if CONFIG.mem_graphs:
                        Meters.mem[name] = Graph(
                            cls.mem_meter,
                            cls.graph_height,
                            THEME.gradient[name],
                            mem.vlist[name],
                        )
                    else:
                        Meters.mem[name] = Meter(mem.percent[name], cls.mem_meter, name)
                if cls.swap_on:
                    for name in cls.swap_names:
                        if CONFIG.swap_disk and CONFIG.show_disks:
                            break
                        elif CONFIG.mem_graphs and not CONFIG.swap_disk:
                            Meters.swap[name] = Graph(
                                cls.mem_meter,
                                cls.graph_height,
                                THEME.gradient[name],
                                mem.swap_vlist[name],
                            )
                        else:
                            Meters.swap[name] = Meter(
                                mem.swap_percent[name], cls.mem_meter, name
                            )

            if CONFIG.show_disks and mem.disks:
                if CONFIG.show_io_stat or CONFIG.io_mode:
                    d_graph: List[str] = []
                    d_no_graph: List[str] = []
                    l_vals: List[Tuple[str, int, str, bool]] = []
                    if CONFIG.io_mode:
                        cls.disks_io_h = (cls.height - 2 - len(mem.disks)) // max(
                            1, len(mem.disks_io_dict)
                        )
                        if cls.disks_io_h < 2:
                            cls.disks_io_h = 1 if CONFIG.io_graph_combined else 2
                    else:
                        cls.disks_io_h = 1

                    if CONFIG.io_graph_speeds and not cls.graph_speeds:
                        try:
                            cls.graph_speeds = {
                                spds.split(":")[0]: int(spds.split(":")[1])
                                for spds in list(
                                    i.strip() for i in CONFIG.io_graph_speeds.split(",")
                                )
                            }
                        except (KeyError, ValueError):
                            errlog.error(
                                "Wrong formatting in io_graph_speeds variable. Using defaults."
                            )
                    for name in mem.disks.keys():
                        if name in mem.disks_io_dict:
                            d_graph.append(name)
                        else:
                            d_no_graph.append(name)
                            continue
                        if CONFIG.io_graph_combined or not CONFIG.io_mode:
                            l_vals = [("rw", cls.disks_io_h, "available", False)]
                        else:
                            l_vals = [
                                ("read", cls.disks_io_h // 2, "free", False),
                                ("write", cls.disks_io_h // 2, "used", True),
                            ]

                        Graphs.disk_io[name] = {
                            _name: Graph(
                                width=cls.disks_width
                                - (6 if not CONFIG.io_mode else 0),
                                height=_height,
                                color=THEME.gradient[_gradient],
                                data=mem.disks_io_dict[name][_name],
                                invert=_invert,
                                max_value=cls.graph_speeds.get(name, 10),
                                no_zero=True,
                            )
                            for _name, _height, _gradient, _invert in l_vals
                        }
                    cls.disks_io_order = d_graph + d_no_graph

                if cls.disk_meter > 0:
                    for n, name in enumerate(mem.disks.keys()):
                        if n * 2 > h:
                            break
                        Meters.disks_used[name] = Meter(
                            mem.disks[name]["used_percent"], cls.disk_meter, "used"
                        )
                        if len(mem.disks) * 3 <= h + 1:
                            Meters.disks_free[name] = Meter(
                                mem.disks[name]["free_percent"], cls.disk_meter, "free"
                            )
            if not "g" in Key.mouse:
                Key.mouse["g"] = [[x + 8 + i, y - 1] for i in range(5)]
            out_misc += (
                f'{Mv.to(y-1, x + 7)}{THEME.mem_box(Symbol.title_left)}{Fx.b if CONFIG.mem_graphs else ""}'
                f'{THEME.hi_fg("g")}{THEME.title("raph")}{Fx.ub}{THEME.mem_box(Symbol.title_right)}'
            )
            if CONFIG.show_disks:
                if not "s" in Key.mouse:
                    Key.mouse["s"] = [[x + w - 6 + i, y - 1] for i in range(4)]
                out_misc += (
                    f'{Mv.to(y-1, x + w - 7)}{THEME.mem_box(Symbol.title_left)}{Fx.b if CONFIG.swap_disk else ""}'
                    f'{THEME.hi_fg("s")}{THEME.title("wap")}{Fx.ub}{THEME.mem_box(Symbol.title_right)}'
                )
                if not "i" in Key.mouse:
                    Key.mouse["i"] = [[x + w - 10 + i, y - 1] for i in range(2)]
                out_misc += (
                    f'{Mv.to(y-1, x + w - 11)}{THEME.mem_box(Symbol.title_left)}{Fx.b if CONFIG.io_mode else ""}'
                    f'{THEME.hi_fg("i")}{THEME.title("o")}{Fx.ub}{THEME.mem_box(Symbol.title_right)}'
                )

            if Collector.collect_interrupt:
                return
            Draw.buffer("mem_misc", out_misc, only_save=True)
        try:
            # * Mem
            cx = 1
            cy = 1

            out += f'{Mv.to(y, x+1)}{THEME.title}{Fx.b}Total:{mem.string["total"]:>{cls.mem_width - 9}}{Fx.ub}{THEME.main_fg}'
            if cls.graph_height > 0:
                gli = f'{Mv.l(2)}{THEME.mem_box(Symbol.title_right)}{THEME.div_line}{Symbol.h_line * (cls.mem_width - 1)}{"" if CONFIG.show_disks else THEME.mem_box}{Symbol.title_left}{Mv.l(cls.mem_width - 1)}{THEME.title}'
            if cls.graph_height >= 2:
                gbg = f"{Mv.l(1)}"
                gmv = f"{Mv.l(cls.mem_width - 2)}{Mv.u(cls.graph_height - 1)}"

            big_mem: bool = cls.mem_width > 21
            for name in cls.mem_names:
                if cy > h - 1:
                    break
                if Collector.collect_interrupt:
                    return
                if cls.mem_size > 2:
                    out += (
                        f'{Mv.to(y+cy, x+cx)}{gli}{name.capitalize()[:None if big_mem else 5]+":":<{1 if big_mem else 6.6}}{Mv.to(y+cy, x+cx + cls.mem_width - 3 - (len(mem.string[name])))}{Fx.trans(mem.string[name])}'
                        f'{Mv.to(y+cy+1, x+cx)}{gbg}{Meters.mem[name](None if cls.resized else mem.percent[name])}{gmv}{str(mem.percent[name])+"%":>4}'
                    )
                    cy += 2 if not cls.graph_height else cls.graph_height + 1
                else:
                    out += f"{Mv.to(y+cy, x+cx)}{name.capitalize():{5.5 if cls.mem_size > 1 else 1.1}} {gbg}{Meters.mem[name](None if cls.resized else mem.percent[name])}{mem.string[name][:None if cls.mem_size > 1 else -2]:>{9 if cls.mem_size > 1 else 7}}"
                    cy += 1 if not cls.graph_height else cls.graph_height
            # * Swap
            if (
                cls.swap_on
                and CONFIG.show_swap
                and not CONFIG.swap_disk
                and mem.swap_string
            ):
                if h - cy > 5:
                    if cls.graph_height > 0:
                        out += f"{Mv.to(y+cy, x+cx)}{gli}"
                    cy += 1

                out += f'{Mv.to(y+cy, x+cx)}{THEME.title}{Fx.b}Swap:{mem.swap_string["total"]:>{cls.mem_width - 8}}{Fx.ub}{THEME.main_fg}'
                cy += 1
                for name in cls.swap_names:
                    if cy > h - 1:
                        break
                    if Collector.collect_interrupt:
                        return
                    if cls.mem_size > 2:
                        out += (
                            f'{Mv.to(y+cy, x+cx)}{gli}{name.capitalize()[:None if big_mem else 5]+":":<{1 if big_mem else 6.6}}{Mv.to(y+cy, x+cx + cls.mem_width - 3 - (len(mem.swap_string[name])))}{Fx.trans(mem.swap_string[name])}'
                            f'{Mv.to(y+cy+1, x+cx)}{gbg}{Meters.swap[name](None if cls.resized else mem.swap_percent[name])}{gmv}{str(mem.swap_percent[name])+"%":>4}'
                        )
                        cy += 2 if not cls.graph_height else cls.graph_height + 1
                    else:
                        out += f"{Mv.to(y+cy, x+cx)}{name.capitalize():{5.5 if cls.mem_size > 1 else 1.1}} {gbg}{Meters.swap[name](None if cls.resized else mem.swap_percent[name])}{mem.swap_string[name][:None if cls.mem_size > 1 else -2]:>{9 if cls.mem_size > 1 else 7}}"
                        cy += 1 if not cls.graph_height else cls.graph_height

            if cls.graph_height > 0 and not cy == h:
                out += f"{Mv.to(y+cy, x+cx)}{gli}"

            # * Disks
            if CONFIG.show_disks and mem.disks:
                cx = x + cls.mem_width - 1
                cy = 0
                big_disk: bool = cls.disks_width >= 25
                gli = f"{Mv.l(2)}{THEME.div_line}{Symbol.title_right}{Symbol.h_line * cls.disks_width}{THEME.mem_box}{Symbol.title_left}{Mv.l(cls.disks_width - 1)}"
                if CONFIG.io_mode:
                    for name in cls.disks_io_order:
                        item = mem.disks[name]
                        io_item = mem.disks_io_dict.get(name, {})
                        if Collector.collect_interrupt:
                            return
                        if cy > h - 1:
                            break
                        out += Fx.trans(
                            f'{Mv.to(y+cy, x+cx)}{gli}{THEME.title}{Fx.b}{item["name"]:{cls.disks_width - 2}.12}{Mv.to(y+cy, x + cx + cls.disks_width - 11)}{item["total"][:None if big_disk else -2]:>9}'
                        )
                        if big_disk:
                            out += Fx.trans(
                                f'{Mv.to(y+cy, x + cx + (cls.disks_width // 2) - (len(str(item["used_percent"])) // 2) - 2)}{Fx.ub}{THEME.main_fg}{item["used_percent"]}%'
                            )
                        cy += 1

                        if io_item:
                            if cy > h - 1:
                                break
                            if CONFIG.io_graph_combined:
                                if cls.disks_io_h <= 1:
                                    out += f'{Mv.to(y+cy, x+cx-1)}{" " * 5}'
                                out += (
                                    f'{Mv.to(y+cy, x+cx-1)}{Fx.ub}{Graphs.disk_io[name]["rw"](None if cls.redraw else mem.disks_io_dict[name]["rw"][-1])}'
                                    f'{Mv.to(y+cy, x+cx-1)}{THEME.main_fg}{item["io"] or "RW"}'
                                )
                                cy += cls.disks_io_h
                            else:
                                if cls.disks_io_h <= 3:
                                    out += f'{Mv.to(y+cy, x+cx-1)}{" " * 5}{Mv.to(y+cy+1, x+cx-1)}{" " * 5}'
                                out += (
                                    f'{Mv.to(y+cy, x+cx-1)}{Fx.ub}{Graphs.disk_io[name]["read"](None if cls.redraw else mem.disks_io_dict[name]["read"][-1])}'
                                    f'{Mv.to(y+cy, x+cx-1)}{THEME.main_fg}{item["io_r"] or "R"}'
                                )
                                cy += cls.disks_io_h // 2
                                out += f'{Mv.to(y+cy, x+cx-1)}{Graphs.disk_io[name]["write"](None if cls.redraw else mem.disks_io_dict[name]["write"][-1])}'
                                cy += cls.disks_io_h // 2
                                out += f'{Mv.to(y+cy-1, x+cx-1)}{THEME.main_fg}{item["io_w"] or "W"}'
                else:
                    for name, item in mem.disks.items():
                        if Collector.collect_interrupt:
                            return
                        if not name in Meters.disks_used:
                            continue
                        if cy > h - 1:
                            break
                        out += Fx.trans(
                            f'{Mv.to(y+cy, x+cx)}{gli}{THEME.title}{Fx.b}{item["name"]:{cls.disks_width - 2}.12}{Mv.to(y+cy, x + cx + cls.disks_width - 11)}{item["total"][:None if big_disk else -2]:>9}'
                        )
                        if big_disk:
                            out += f'{Mv.to(y+cy, x + cx + (cls.disks_width // 2) - (len(item["io"]) // 2) - 2)}{Fx.ub}{THEME.main_fg}{Fx.trans(item["io"])}'
                        cy += 1
                        if cy > h - 1:
                            break
                        if CONFIG.show_io_stat and name in Graphs.disk_io:
                            out += f'{Mv.to(y+cy, x+cx-1)}{THEME.main_fg}{Fx.ub}{" IO: " if big_disk else " IO   " + Mv.l(2)}{Fx.ub}{Graphs.disk_io[name]["rw"](None if cls.redraw else mem.disks_io_dict[name]["rw"][-1])}'
                            if not big_disk and item["io"]:
                                out += f'{Mv.to(y+cy, x+cx-1)}{Fx.ub}{THEME.main_fg}{item["io"]}'
                            cy += 1
                            if cy > h - 1:
                                break
                        out += Mv.to(y + cy, x + cx) + (
                            f'Used:{str(item["used_percent"]) + "%":>4} '
                            if big_disk
                            else "U "
                        )
                        out += f'{Meters.disks_used[name](None if cls.resized else mem.disks[name]["used_percent"])}{item["used"][:None if big_disk else -2]:>{9 if big_disk else 7}}'
                        cy += 1

                        if (
                            len(mem.disks) * 3
                            + (len(mem.disks_io_dict) if CONFIG.show_io_stat else 0)
                            <= h + 1
                        ):
                            if cy > h - 1:
                                break
                            out += Mv.to(y + cy, x + cx)
                            out += (
                                f'Free:{str(item["free_percent"]) + "%":>4} '
                                if big_disk
                                else f'{"F "}'
                            )
                            out += f'{Meters.disks_free[name](None if cls.resized else mem.disks[name]["free_percent"])}{item["free"][:None if big_disk else -2]:>{9 if big_disk else 7}}'
                            cy += 1
                            if (
                                len(mem.disks) * 4
                                + (len(mem.disks_io_dict) if CONFIG.show_io_stat else 0)
                                <= h + 1
                            ):
                                cy += 1
        except (KeyError, TypeError):
            return
        Draw.buffer(cls.buffer, f"{out_misc}{out}{Term.fg}", only_save=Menu.active)
        cls.resized = cls.redraw = False


class NetBox(Box, SubBox):
    name = "net"
    num = 3
    height_p = 30
    width_p = 45
    min_w: int = 36
    min_h: int = 6
    x = 1
    y = 1
    resized: bool = True
    redraw: bool = True
    graph_height: Dict[str, int] = {}
    symbols: Dict[str, str] = {"download": "▼", "upload": "▲"}
    buffer: str = "net"

    Box.buffers.append(buffer)

    @classmethod
    def _calc_size(cls):
        if not "net" in cls.boxes:
            cls.width = Term.width
            return
        if not "proc" in cls.boxes:
            width_p = 100
        else:
            width_p = cls.width_p

        cls.width = round(Term.width * width_p / 100)
        cls.height = Term.height - Box._b_cpu_h - Box._b_mem_h
        cls.y = Term.height - cls.height + 1
        cls.box_width = 27 if cls.width > 45 else 19
        cls.box_height = 9 if cls.height > 10 else cls.height - 2
        cls.box_x = cls.width - cls.box_width - 1
        cls.box_y = cls.y + ((cls.height - 2) // 2) - cls.box_height // 2 + 1
        cls.graph_height["download"] = round((cls.height - 2) / 2)
        cls.graph_height["upload"] = cls.height - 2 - cls.graph_height["download"]
        cls.redraw = True

    @classmethod
    def _draw_bg(cls) -> str:
        if not "net" in cls.boxes:
            return ""
        return f'{create_box(box=cls, line_color=THEME.net_box)}\
        {create_box(x=cls.box_x, y=cls.box_y, width=cls.box_width, height=cls.box_height, line_color=THEME.div_line, fill=False, title="Download", title2="Upload")}'

    @classmethod
    def _draw_fg(cls):
        if not "net" in cls.boxes:
            return
        net = NetCollector
        if net.redraw:
            cls.redraw = True
        if not net.nic:
            return
        out: str = ""
        out_misc: str = ""
        x, y, w, h = cls.x + 1, cls.y + 1, cls.width - 2, cls.height - 2
        bx, by, bw, bh = (
            cls.box_x + 1,
            cls.box_y + 1,
            cls.box_width - 2,
            cls.box_height - 2,
        )
        reset: bool = bool(net.stats[net.nic]["download"]["offset"])

        if cls.resized or cls.redraw:
            out_misc += cls._draw_bg()
            Key.mouse["b"] = [
                [x + w - len(net.nic[:10]) - 9 + i, y - 1] for i in range(4)
            ]
            Key.mouse["n"] = [[x + w - 5 + i, y - 1] for i in range(4)]
            Key.mouse["z"] = [
                [x + w - len(net.nic[:10]) - 14 + i, y - 1] for i in range(4)
            ]

            out_misc += (
                f'{Mv.to(y-1, x+w - 25)}{THEME.net_box}{Symbol.h_line * (10 - len(net.nic[:10]))}{Symbol.title_left}{Fx.b if reset else ""}{THEME.hi_fg("z")}{THEME.title("ero")}'
                f"{Fx.ub}{THEME.net_box(Symbol.title_right)}{Term.fg}"
                f'{THEME.net_box}{Symbol.title_left}{Fx.b}{THEME.hi_fg("<b")} {THEME.title(net.nic[:10])} {THEME.hi_fg("n>")}{Fx.ub}{THEME.net_box(Symbol.title_right)}{Term.fg}'
            )
            if w - len(net.nic[:10]) - 20 > 6:
                Key.mouse["a"] = [
                    [x + w - 20 - len(net.nic[:10]) + i, y - 1] for i in range(4)
                ]
                out_misc += (
                    f'{Mv.to(y-1, x+w - 21 - len(net.nic[:10]))}{THEME.net_box(Symbol.title_left)}{Fx.b if net.auto_min else ""}{THEME.hi_fg("a")}{THEME.title("uto")}'
                    f"{Fx.ub}{THEME.net_box(Symbol.title_right)}{Term.fg}"
                )
            if w - len(net.nic[:10]) - 20 > 13:
                Key.mouse["y"] = [
                    [x + w - 26 - len(net.nic[:10]) + i, y - 1] for i in range(4)
                ]
                out_misc += (
                    f'{Mv.to(y-1, x+w - 27 - len(net.nic[:10]))}{THEME.net_box(Symbol.title_left)}{Fx.b if CONFIG.net_sync else ""}{THEME.title("s")}{THEME.hi_fg("y")}{THEME.title("nc")}'
                    f"{Fx.ub}{THEME.net_box(Symbol.title_right)}{Term.fg}"
                )
            if net.address and w - len(net.nic[:10]) - len(net.address) - 20 > 15:
                out_misc += f"{Mv.to(y-1, x+7)}{THEME.net_box(Symbol.title_left)}{Fx.b}{THEME.title(net.address)}{Fx.ub}{THEME.net_box(Symbol.title_right)}{Term.fg}"
            Draw.buffer("net_misc", out_misc, only_save=True)

        cy = 0
        for direction in ["download", "upload"]:
            strings = net.strings[net.nic][direction]
            stats = net.stats[net.nic][direction]
            if cls.redraw:
                stats["redraw"] = True
            if stats["redraw"] or cls.resized:
                Graphs.net[direction] = Graph(
                    w - bw - 3,
                    cls.graph_height[direction],
                    THEME.gradient[direction],
                    stats["speed"],
                    max_value=net.sync_top if CONFIG.net_sync else stats["graph_top"],
                    invert=direction != "download",
                    color_max_value=net.net_min.get(direction)
                    if CONFIG.net_color_fixed
                    else None,
                    round_up_low=True,
                )
            out += f'{Mv.to(y if direction == "download" else y + cls.graph_height["download"], x)}{Graphs.net[direction](None if stats["redraw"] else stats["speed"][-1])}'

            out += (
                f'{Mv.to(by+cy, bx)}{THEME.main_fg}{cls.symbols[direction]} {strings["byte_ps"]:<10.10}'
                + (
                    ""
                    if bw < 20
                    else f'{Mv.to(by+cy, bx+bw - 12)}{"(" + strings["bit_ps"] + ")":>12.12}'
                )
            )
            cy += 1 if bh != 3 else 2
            if bh >= 6:
                out += f'{Mv.to(by+cy, bx)}{cls.symbols[direction]} {"Top:"}{Mv.to(by+cy, bx+bw - 12)}{"(" + strings["top"] + ")":>12.12}'
                cy += 1
            if bh >= 4:
                out += f'{Mv.to(by+cy, bx)}{cls.symbols[direction]} {"Total:"}{Mv.to(by+cy, bx+bw - 10)}{strings["total"]:>10.10}'
                if bh > 2 and bh % 2:
                    cy += 2
                else:
                    cy += 1
            stats["redraw"] = False

        out += (
            f'{Mv.to(y, x)}{THEME.graph_text(net.sync_string if CONFIG.net_sync else net.strings[net.nic]["download"]["graph_top"])}'
            f'{Mv.to(y+h-1, x)}{THEME.graph_text(net.sync_string if CONFIG.net_sync else net.strings[net.nic]["upload"]["graph_top"])}'
        )

        Draw.buffer(cls.buffer, f"{out_misc}{out}{Term.fg}", only_save=Menu.active)
        cls.redraw = cls.resized = False


class ProcBox(Box):
    name = "proc"
    num = 4
    height_p = 68
    width_p = 55
    min_w: int = 44
    min_h: int = 16
    x = 1
    y = 1
    current_y: int = 0
    current_h: int = 0
    select_max: int = 0
    selected: int = 0
    selected_pid: int = 0
    last_selection: int = 0
    filtering: bool = False
    moved: bool = False
    start: int = 1
    count: int = 0
    s_len: int = 0
    detailed: bool = False
    detailed_x: int = 0
    detailed_y: int = 0
    detailed_width: int = 0
    detailed_height: int = 8
    resized: bool = True
    redraw: bool = True
    buffer: str = "proc"
    pid_counter: Dict[int, int] = {}
    Box.buffers.append(buffer)

    @classmethod
    def _calc_size(cls):
        if not "proc" in cls.boxes:
            cls.width = Term.width
            return
        width_p: int
        height_p: int
        if not "net" in cls.boxes and not "mem" in cls.boxes:
            width_p = 100
        else:
            width_p = cls.width_p

        if not "cpu" in cls.boxes:
            height_p = 100
        else:
            height_p = cls.height_p

        cls.width = round(Term.width * width_p / 100)
        cls.height = round(Term.height * height_p / 100)
        if cls.height + Box._b_cpu_h > Term.height:
            cls.height = Term.height - Box._b_cpu_h
        cls.x = Term.width - cls.width + 1
        cls.y = Box._b_cpu_h + 1
        cls.current_y = cls.y
        cls.current_h = cls.height
        cls.select_max = cls.height - 3
        cls.redraw = True
        cls.resized = True

    @classmethod
    def _draw_bg(cls) -> str:
        if not "proc" in cls.boxes:
            return ""
        return create_box(box=cls, line_color=THEME.proc_box)

    @classmethod
    def selector(cls, key: str, mouse_pos: Tuple[int, int] = (0, 0)):
        old: Tuple[int, int] = (cls.start, cls.selected)
        new_sel: int
        if key in ["up", "k"]:
            if cls.selected == 1 and cls.start > 1:
                cls.start -= 1
            elif cls.selected == 1:
                cls.selected = 0
            elif cls.selected > 1:
                cls.selected -= 1
        elif key in ["down", "j"]:
            if cls.selected == 0 and ProcCollector.detailed and cls.last_selection:
                cls.selected = cls.last_selection
                cls.last_selection = 0
            if (
                cls.selected == cls.select_max
                and cls.start < ProcCollector.num_procs - cls.select_max + 1
            ):
                cls.start += 1
            elif cls.selected < cls.select_max:
                cls.selected += 1
        elif key == "mouse_scroll_up" and cls.start > 1:
            cls.start -= 5
        elif (
            key == "mouse_scroll_down"
            and cls.start < ProcCollector.num_procs - cls.select_max + 1
        ):
            cls.start += 5
        elif key == "page_up" and cls.start > 1:
            cls.start -= cls.select_max
        elif (
            key == "page_down"
            and cls.start < ProcCollector.num_procs - cls.select_max + 1
        ):
            cls.start += cls.select_max
        elif key == "home":
            if cls.start > 1:
                cls.start = 1
            elif cls.selected > 0:
                cls.selected = 0
        elif key == "end":
            if cls.start < ProcCollector.num_procs - cls.select_max + 1:
                cls.start = ProcCollector.num_procs - cls.select_max + 1
            elif cls.selected < cls.select_max:
                cls.selected = cls.select_max
        elif key == "mouse_click":
            if (
                mouse_pos[0] > cls.x + cls.width - 4
                and cls.current_y + 1
                < mouse_pos[1]
                < cls.current_y + 1 + cls.select_max + 1
            ):
                if mouse_pos[1] == cls.current_y + 2:
                    cls.start = 1
                elif mouse_pos[1] == cls.current_y + 1 + cls.select_max:
                    cls.start = ProcCollector.num_procs - cls.select_max + 1
                else:
                    cls.start = round(
                        (mouse_pos[1] - cls.current_y)
                        * (
                            (ProcCollector.num_procs - cls.select_max - 2)
                            / (cls.select_max - 2)
                        )
                    )
            else:
                new_sel = (
                    mouse_pos[1] - cls.current_y - 1
                    if mouse_pos[1] >= cls.current_y - 1
                    else 0
                )
                if new_sel > 0 and new_sel == cls.selected:
                    Key.list.insert(0, "enter")
                    return
                elif new_sel > 0 and new_sel != cls.selected:
                    if cls.last_selection:
                        cls.last_selection = 0
                    cls.selected = new_sel
        elif key == "mouse_unselect":
            cls.selected = 0

        if (
            cls.start > ProcCollector.num_procs - cls.select_max + 1
            and ProcCollector.num_procs > cls.select_max
        ):
            cls.start = ProcCollector.num_procs - cls.select_max + 1
        elif cls.start > ProcCollector.num_procs:
            cls.start = ProcCollector.num_procs
        if cls.start < 1:
            cls.start = 1
        if (
            cls.selected > ProcCollector.num_procs
            and ProcCollector.num_procs < cls.select_max
        ):
            cls.selected = ProcCollector.num_procs
        elif cls.selected > cls.select_max:
            cls.selected = cls.select_max
        if cls.selected < 0:
            cls.selected = 0

        if old != (cls.start, cls.selected):
            cls.moved = True
            Collector.collect(
                ProcCollector, proc_interrupt=True, redraw=True, only_draw=True
            )

    @classmethod
    def _draw_fg(cls):
        if not "proc" in cls.boxes:
            return
        proc = ProcCollector
        if proc.proc_interrupt:
            return
        if proc.redraw:
            cls.redraw = True
        out: str = ""
        out_misc: str = ""
        n: int = 0
        x, y, w, h = cls.x + 1, cls.current_y + 1, cls.width - 2, cls.current_h - 2
        prog_len: int
        arg_len: int
        val: int
        c_color: str
        m_color: str
        t_color: str
        sort_pos: int
        tree_len: int
        is_selected: bool
        calc: int
        dgx: int
        dgw: int
        dx: int
        dw: int
        dy: int
        l_count: int = 0
        scroll_pos: int = 0
        killed: bool = True
        indent: str = ""
        offset: int = 0
        tr_show: bool = True
        usr_show: bool = True
        vals: List[str]
        g_color: str = ""
        s_len: int = 0
        if proc.search_filter:
            s_len = len(proc.search_filter[:10])
        loc_string: str = f"{cls.start + cls.selected - 1}/{proc.num_procs}"
        end: str = ""

        if proc.detailed:
            dgx, dgw = x, w // 3
            dw = w - dgw - 1
            if dw > 120:
                dw = 120
                dgw = w - 121
            dx = x + dgw + 2
            dy = cls.y + 1

        if w > 67:
            arg_len = w - 53 - (1 if proc.num_procs > cls.select_max else 0)
            prog_len = 15
        else:
            arg_len = 0
            prog_len = w - 38 - (1 if proc.num_procs > cls.select_max else 0)
            if prog_len < 15:
                tr_show = False
                prog_len += 5
            if prog_len < 12:
                usr_show = False
                prog_len += 9

        if CONFIG.proc_tree:
            tree_len = arg_len + prog_len + 6
            arg_len = 0

        # * Buttons and titles only redrawn if needed
        if cls.resized or cls.redraw:
            s_len += len(CONFIG.proc_sorting)
            if cls.resized or s_len != cls.s_len or proc.detailed:
                cls.s_len = s_len
                for k in [
                    "e",
                    "r",
                    "c",
                    "T",
                    "K",
                    "I",
                    "enter",
                    "left",
                    " ",
                    "f",
                    "delete",
                ]:
                    if k in Key.mouse:
                        del Key.mouse[k]
            if proc.detailed:
                killed = proc.details.get("killed", False)
                main = (
                    THEME.main_fg
                    if cls.selected == 0 and not killed
                    else THEME.inactive_fg
                )
                hi = (
                    THEME.hi_fg
                    if cls.selected == 0 and not killed
                    else THEME.inactive_fg
                )
                title = (
                    THEME.title
                    if cls.selected == 0 and not killed
                    else THEME.inactive_fg
                )
                if (
                    cls.current_y != cls.y + 8
                    or cls.resized
                    or Graphs.detailed_cpu is NotImplemented
                ):
                    cls.current_y = cls.y + 8
                    cls.current_h = cls.height - 8
                    for i in range(7):
                        out_misc += f'{Mv.to(dy+i, x)}{" " * w}'
                    out_misc += (
                        f"{Mv.to(dy+7, x-1)}{THEME.proc_box}{Symbol.title_right}{Symbol.h_line*w}{Symbol.title_left}"
                        f"{Mv.to(dy+7, x+1)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg(SUPERSCRIPT[cls.num])}{THEME.title(cls.name)}{Fx.ub}{THEME.proc_box(Symbol.title_right)}{THEME.div_line}"
                    )
                    for i in range(7):
                        out_misc += f"{Mv.to(dy + i, dgx + dgw + 1)}{Symbol.v_line}"

                out_misc += (
                    f"{Mv.to(dy-1, x-1)}{THEME.proc_box}{Symbol.left_up}{Symbol.h_line*w}{Symbol.right_up}"
                    f"{Mv.to(dy-1, dgx + dgw + 1)}{Symbol.div_up}"
                    f'{Mv.to(dy-1, x+1)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{THEME.title(str(proc.details["pid"]))}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
                    f'{THEME.proc_box(Symbol.title_left)}{Fx.b}{THEME.title(proc.details["name"][:(dgw - 11)])}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
                )

                if cls.selected == 0:
                    Key.mouse["enter"] = [[dx + dw - 10 + i, dy - 1] for i in range(7)]
                if cls.selected == 0 and not killed:
                    Key.mouse["T"] = [[dx + 2 + i, dy - 1] for i in range(9)]

                out_misc += (
                    f"{Mv.to(dy-1, dx+dw - 11)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{title if cls.selected > 0 else THEME.title}close{Fx.ub} {main if cls.selected > 0 else THEME.main_fg}{Symbol.enter}{THEME.proc_box(Symbol.title_right)}"
                    f"{Mv.to(dy-1, dx+1)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}T{title}erminate{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
                )
                if dw > 28:
                    if cls.selected == 0 and not killed and not "K" in Key.mouse:
                        Key.mouse["K"] = [[dx + 13 + i, dy - 1] for i in range(4)]
                    out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}K{title}ill{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
                if dw > 39:
                    if cls.selected == 0 and not killed and not "I" in Key.mouse:
                        Key.mouse["I"] = [[dx + 19 + i, dy - 1] for i in range(9)]
                    out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}I{title}nterrupt{Fx.ub}{THEME.proc_box(Symbol.title_right)}"

                if Graphs.detailed_cpu is NotImplemented or cls.resized:
                    Graphs.detailed_cpu = Graph(
                        dgw + 1, 7, THEME.gradient["cpu"], proc.details_cpu
                    )
                    Graphs.detailed_mem = Graph(dw // 3, 1, None, proc.details_mem)

                cls.select_max = cls.height - 11
                y = cls.y + 9
                h = cls.height - 10

            else:
                if cls.current_y != cls.y or cls.resized:
                    cls.current_y = cls.y
                    cls.current_h = cls.height
                    y, h = cls.y + 1, cls.height - 2
                    out_misc += (
                        f"{Mv.to(y-1, x-1)}{THEME.proc_box}{Symbol.left_up}{Symbol.h_line*w}{Symbol.right_up}"
                        f"{Mv.to(y-1, x+1)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg(SUPERSCRIPT[cls.num])}{THEME.title(cls.name)}{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
                        f"{Mv.to(y+7, x-1)}{THEME.proc_box(Symbol.v_line)}{Mv.r(w)}{THEME.proc_box(Symbol.v_line)}"
                    )
                cls.select_max = cls.height - 3

            sort_pos = x + w - len(CONFIG.proc_sorting) - 7
            if not "left" in Key.mouse:
                Key.mouse["left"] = [[sort_pos + i, y - 1] for i in range(3)]
                Key.mouse["right"] = [
                    [sort_pos + len(CONFIG.proc_sorting) + 3 + i, y - 1]
                    for i in range(3)
                ]

            out_misc += (
                f"{Mv.to(y-1, x + 8)}{THEME.proc_box(Symbol.h_line * (w - 9))}"
                + (
                    ""
                    if not proc.detailed
                    else f"{Mv.to(dy+7, dgx + dgw + 1)}{THEME.proc_box(Symbol.div_down)}"
                )
                + f'{Mv.to(y-1, sort_pos)}{THEME.proc_box(Symbol.title_left)}{Fx.b}{THEME.hi_fg("<")} {THEME.title(CONFIG.proc_sorting)} '
                f'{THEME.hi_fg(">")}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
            )

            if w > 29 + s_len:
                if not "e" in Key.mouse:
                    Key.mouse["e"] = [[sort_pos - 5 + i, y - 1] for i in range(4)]
                out_misc += (
                    f'{Mv.to(y-1, sort_pos - 6)}{THEME.proc_box(Symbol.title_left)}{Fx.b if CONFIG.proc_tree else ""}'
                    f'{THEME.title("tre")}{THEME.hi_fg("e")}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
                )
            if w > 37 + s_len:
                if not "r" in Key.mouse:
                    Key.mouse["r"] = [[sort_pos - 14 + i, y - 1] for i in range(7)]
                out_misc += (
                    f'{Mv.to(y-1, sort_pos - 15)}{THEME.proc_box(Symbol.title_left)}{Fx.b if CONFIG.proc_reversed else ""}'
                    f'{THEME.hi_fg("r")}{THEME.title("everse")}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
                )
            if w > 47 + s_len:
                if not "c" in Key.mouse:
                    Key.mouse["c"] = [[sort_pos - 24 + i, y - 1] for i in range(8)]
                out_misc += (
                    f'{Mv.to(y-1, sort_pos - 25)}{THEME.proc_box(Symbol.title_left)}{Fx.b if CONFIG.proc_per_core else ""}'
                    f'{THEME.title("per-")}{THEME.hi_fg("c")}{THEME.title("ore")}{Fx.ub}{THEME.proc_box(Symbol.title_right)}'
                )

            if not "f" in Key.mouse or cls.resized:
                Key.mouse["f"] = [
                    [x + 6 + i, y - 1]
                    for i in range(
                        6
                        if not proc.search_filter
                        else 2 + len(proc.search_filter[-10:])
                    )
                ]
            if proc.search_filter:
                if not "delete" in Key.mouse:
                    Key.mouse["delete"] = [
                        [x + 12 + len(proc.search_filter[-10:]) + i, y - 1]
                        for i in range(3)
                    ]
            elif "delete" in Key.mouse:
                del Key.mouse["delete"]
            out_misc += (
                f'{Mv.to(y-1, x + 8)}{THEME.proc_box(Symbol.title_left)}{Fx.b if cls.filtering or proc.search_filter else ""}{THEME.hi_fg("F" if cls.filtering and proc.case_sensitive else "f")}{THEME.title}'
                + (
                    "ilter"
                    if not proc.search_filter and not cls.filtering
                    else f' {proc.search_filter[-(10 if w < 83 else w - 74):]}{(Fx.bl + "█" + Fx.ubl) if cls.filtering else THEME.hi_fg(" del")}'
                )
                + f"{THEME.proc_box(Symbol.title_right)}"
            )

            main = THEME.inactive_fg if cls.selected == 0 else THEME.main_fg
            hi = THEME.inactive_fg if cls.selected == 0 else THEME.hi_fg
            title = THEME.inactive_fg if cls.selected == 0 else THEME.title
            out_misc += (
                f"{Mv.to(y+h, x + 1)}{THEME.proc_box}{Symbol.h_line*(w-4)}"
                f'{Mv.to(y+h, x+1)}{THEME.proc_box(Symbol.title_left)}{main}{Symbol.up} {Fx.b}{THEME.main_fg("select")} {Fx.ub}'
                f"{THEME.inactive_fg if cls.selected == cls.select_max else THEME.main_fg}{Symbol.down}{THEME.proc_box(Symbol.title_right)}"
                f"{THEME.proc_box(Symbol.title_left)}{title}{Fx.b}info {Fx.ub}{main}{Symbol.enter}{THEME.proc_box(Symbol.title_right)}"
            )
            if not "enter" in Key.mouse:
                Key.mouse["enter"] = [[x + 14 + i, y + h] for i in range(6)]
            if w - len(loc_string) > 34:
                if not "T" in Key.mouse:
                    Key.mouse["T"] = [[x + 22 + i, y + h] for i in range(9)]
                out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}T{title}erminate{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
            if w - len(loc_string) > 40:
                if not "K" in Key.mouse:
                    Key.mouse["K"] = [[x + 33 + i, y + h] for i in range(4)]
                out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}K{title}ill{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
            if w - len(loc_string) > 51:
                if not "I" in Key.mouse:
                    Key.mouse["I"] = [[x + 39 + i, y + h] for i in range(9)]
                out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}I{title}nterrupt{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
            if CONFIG.proc_tree and w - len(loc_string) > 65:
                if not " " in Key.mouse:
                    Key.mouse[" "] = [[x + 50 + i, y + h] for i in range(12)]
                out_misc += f"{THEME.proc_box(Symbol.title_left)}{Fx.b}{hi}spc {title}collapse{Fx.ub}{THEME.proc_box(Symbol.title_right)}"

            # * Processes labels
            selected: str = CONFIG.proc_sorting
            label: str
            if selected == "memory":
                selected = "mem"
            if selected == "threads" and not CONFIG.proc_tree and not arg_len:
                selected = "tr"
            if CONFIG.proc_tree:
                label = (
                    f'{THEME.title}{Fx.b}{Mv.to(y, x)}{" Tree:":<{tree_len-2}}'
                    + (f'{"Threads: ":<9}' if tr_show else " " * 4)
                    + (f'{"User:":<9}' if usr_show else "")
                    + f'Mem%{"Cpu%":>11}{Fx.ub}{THEME.main_fg} '
                    + (" " if proc.num_procs > cls.select_max else "")
                )
                if selected in ["pid", "program", "arguments"]:
                    selected = "tree"
            else:
                label = (
                    f'{THEME.title}{Fx.b}{Mv.to(y, x)}{"Pid:":>7} {"Program:" if prog_len > 8 else "Prg:":<{prog_len}}'
                    + (f'{"Arguments:":<{arg_len-4}}' if arg_len else "")
                    + (
                        (f'{"Threads:":<9}' if arg_len else f'{"Tr:":^5}')
                        if tr_show
                        else ""
                    )
                    + (f'{"User:":<9}' if usr_show else "")
                    + f'Mem%{"Cpu%":>11}{Fx.ub}{THEME.main_fg} '
                    + (" " if proc.num_procs > cls.select_max else "")
                )
                if selected == "program" and prog_len <= 8:
                    selected = "prg"
            selected = selected.split(" ")[0].capitalize()
            if CONFIG.proc_mem_bytes:
                label = label.replace("Mem%", "MemB")
            label = label.replace(selected, f"{Fx.u}{selected}{Fx.uu}")
            out_misc += label

            Draw.buffer("proc_misc", out_misc, only_save=True)

        # * Detailed box draw
        if proc.detailed:
            if proc.details["status"] == psutil.STATUS_RUNNING:
                stat_color = Fx.b
            elif proc.details["status"] in [
                psutil.STATUS_DEAD,
                psutil.STATUS_STOPPED,
                psutil.STATUS_ZOMBIE,
            ]:
                stat_color = f"{THEME.inactive_fg}"
            else:
                stat_color = ""
            expand = proc.expand
            iw = (dw - 3) // (4 + expand)
            iw2 = iw - 1
            out += (
                f'{Mv.to(dy, dgx)}{Graphs.detailed_cpu(None if cls.moved or proc.details["killed"] else proc.details_cpu[-1])}'
                f'{Mv.to(dy, dgx)}{THEME.title}{Fx.b}{0 if proc.details["killed"] else proc.details["cpu_percent"]}%{Mv.r(1)}{"" if SYSTEM == "MacOS" else (("C" if dgw < 20 else "Core") + str(proc.details["cpu_num"]))}'
            )
            for i, l in enumerate(["C", "P", "U"]):
                out += f"{Mv.to(dy+2+i, dgx)}{l}"
            for i, l in enumerate(["C", "M", "D"]):
                out += f"{Mv.to(dy+4+i, dx+1)}{l}"
            out += (
                f'{Mv.to(dy, dx+1)} {"Status:":^{iw}.{iw2}}{"Elapsed:":^{iw}.{iw2}}'
                + (f'{"Parent:":^{iw}.{iw2}}' if dw > 28 else "")
                + (f'{"User:":^{iw}.{iw2}}' if dw > 38 else "")
                + (f'{"Threads:":^{iw}.{iw2}}' if expand > 0 else "")
                + (f'{"Nice:":^{iw}.{iw2}}' if expand > 1 else "")
                + (f'{"IO Read:":^{iw}.{iw2}}' if expand > 2 else "")
                + (f'{"IO Write:":^{iw}.{iw2}}' if expand > 3 else "")
                + (f'{"TTY:":^{iw}.{iw2}}' if expand > 4 else "")
                + f'{Mv.to(dy+1, dx+1)}{Fx.ub}{THEME.main_fg}{stat_color}{proc.details["status"]:^{iw}.{iw2}}{Fx.ub}{THEME.main_fg}{proc.details["uptime"]:^{iw}.{iw2}} '
                + (f'{proc.details["parent_name"]:^{iw}.{iw2}}' if dw > 28 else "")
                + (f'{proc.details["username"]:^{iw}.{iw2}}' if dw > 38 else "")
                + (f'{proc.details["threads"]:^{iw}.{iw2}}' if expand > 0 else "")
                + (f'{proc.details["nice"]:^{iw}.{iw2}}' if expand > 1 else "")
                + (f'{proc.details["io_read"]:^{iw}.{iw2}}' if expand > 2 else "")
                + (f'{proc.details["io_write"]:^{iw}.{iw2}}' if expand > 3 else "")
                + (
                    f'{proc.details["terminal"][-(iw2):]:^{iw}.{iw2}}'
                    if expand > 4
                    else ""
                )
                + f'{Mv.to(dy+3, dx)}{THEME.title}{Fx.b}{("Memory: " if dw > 42 else "M:") + str(round(proc.details["memory_percent"], 1)) + "%":>{dw//3-1}}{Fx.ub} {THEME.inactive_fg}{"⡀"*(dw//3)}'
                f"{Mv.l(dw//3)}{THEME.proc_misc}{Graphs.detailed_mem(None if cls.moved else proc.details_mem[-1])} "
                f'{THEME.title}{Fx.b}{proc.details["memory_bytes"]:.{dw//3 - 2}}{THEME.main_fg}{Fx.ub}'
            )
            cy = dy + (4 if len(proc.details["cmdline"]) > dw - 5 else 5)
            for i in range(ceil(len(proc.details["cmdline"]) / (dw - 5))):
                out += f'{Mv.to(cy+i, dx + 3)}{proc.details["cmdline"][((dw-5)*i):][:(dw-5)]:{"^" if i == 0 else "<"}{dw-5}}'
                if i == 2:
                    break

        # * Checking for selection out of bounds
        if (
            cls.start > proc.num_procs - cls.select_max + 1
            and proc.num_procs > cls.select_max
        ):
            cls.start = proc.num_procs - cls.select_max + 1
        elif cls.start > proc.num_procs:
            cls.start = proc.num_procs
        if cls.start < 1:
            cls.start = 1
        if cls.selected > proc.num_procs and proc.num_procs < cls.select_max:
            cls.selected = proc.num_procs
        elif cls.selected > cls.select_max:
            cls.selected = cls.select_max
        if cls.selected < 0:
            cls.selected = 0

        # * Start iteration over all processes and info
        cy = 1
        for n, (pid, items) in enumerate(proc.processes.items(), start=1):
            if n < cls.start:
                continue
            l_count += 1
            if l_count == cls.selected:
                is_selected = True
                cls.selected_pid = pid
            else:
                is_selected = False

            indent, name, cmd, threads, username, mem, mem_b, cpu = [
                items.get(v, d)
                for v, d in [
                    ("indent", ""),
                    ("name", ""),
                    ("cmd", ""),
                    ("threads", 0),
                    ("username", "?"),
                    ("mem", 0.0),
                    ("mem_b", 0),
                    ("cpu", 0.0),
                ]
            ]

            if CONFIG.proc_tree:
                arg_len = 0
                offset = tree_len - len(f"{indent}{pid}")
                if offset < 1:
                    offset = 0
                indent = f"{indent:.{tree_len - len(str(pid))}}"
                if offset - len(name) > 12:
                    cmd = cmd.split(" ")[0].split("/")[-1]
                    if not cmd.startswith(name):
                        offset = len(name)
                        arg_len = tree_len - len(f"{indent}{pid} {name} ") + 2
                        cmd = f"({cmd[:(arg_len-4)]})"
            else:
                offset = prog_len - 1
            if cpu > 1.0 or pid in Graphs.pid_cpu:
                if pid not in Graphs.pid_cpu:
                    Graphs.pid_cpu[pid] = Graph(5, 1, None, [0])
                    cls.pid_counter[pid] = 0
                elif cpu < 1.0:
                    cls.pid_counter[pid] += 1
                    if cls.pid_counter[pid] > 10:
                        del cls.pid_counter[pid], Graphs.pid_cpu[pid]
                else:
                    cls.pid_counter[pid] = 0

            end = f"{THEME.main_fg}{Fx.ub}" if CONFIG.proc_colors else Fx.ub
            if cls.selected > cy:
                calc = cls.selected - cy
            elif 0 < cls.selected <= cy:
                calc = cy - cls.selected
            else:
                calc = cy
            if CONFIG.proc_colors and not is_selected:
                vals = []
                for v in [int(cpu), int(mem), int(threads // 3)]:
                    if CONFIG.proc_gradient:
                        val = (
                            (v if v <= 100 else 100) + 100
                        ) - calc * 100 // cls.select_max
                        vals += [
                            f'{THEME.gradient["proc_color" if val < 100 else "process"][val if val < 100 else val - 100]}'
                        ]
                    else:
                        vals += [f'{THEME.gradient["process"][v if v <= 100 else 100]}']
                c_color, m_color, t_color = vals
            else:
                c_color = m_color = t_color = Fx.b
            if CONFIG.proc_gradient and not is_selected:
                g_color = f'{THEME.gradient["proc"][calc * 100 // cls.select_max]}'
            if is_selected:
                c_color = m_color = t_color = g_color = end = ""
                out += f"{THEME.selected_bg}{THEME.selected_fg}{Fx.b}"

            # * Creates one line for a process with all gathered information
            out += (
                f"{Mv.to(y+cy, x)}{g_color}{indent}{pid:>{(1 if CONFIG.proc_tree else 7)}} "
                + f"{c_color}{name:<{offset}.{offset}} {end}"
                + (f"{g_color}{cmd:<{arg_len}.{arg_len-1}}" if arg_len else "")
                + (
                    t_color + (f"{threads:>4} " if threads < 1000 else "999> ") + end
                    if tr_show
                    else ""
                )
                + (
                    g_color
                    + (
                        f"{username:<9.9}"
                        if len(username) < 10
                        else f"{username[:8]:<8}+"
                    )
                    if usr_show
                    else ""
                )
                + m_color
                + (
                    (f"{mem:>4.1f}" if mem < 100 else f"{mem:>4.0f} ")
                    if not CONFIG.proc_mem_bytes
                    else f"{fmt.floating_humanizer(mem_b, short=True):>4.4}"
                )
                + end
                + f' {THEME.inactive_fg}{"⡀"*5}{THEME.main_fg}{g_color}{c_color}'
                + (f" {cpu:>4.1f} " if cpu < 100 else f"{cpu:>5.0f} ")
                + end
                + (" " if proc.num_procs > cls.select_max else "")
            )

            # * Draw small cpu graph for process if cpu usage was above 1% in the last 10 updates
            if pid in Graphs.pid_cpu:
                out += f"{Mv.to(y+cy, x + w - (12 if proc.num_procs > cls.select_max else 11))}{c_color if CONFIG.proc_colors else THEME.proc_misc}{Graphs.pid_cpu[pid](None if cls.moved else round(cpu))}{THEME.main_fg}"

            if is_selected:
                out += f'{Fx.ub}{Term.fg}{Term.bg}{Mv.to(y+cy, x + w - 1)}{" " if proc.num_procs > cls.select_max else ""}'

            cy += 1
            if cy == h:
                break
        if cy < h:
            for i in range(h - cy):
                out += f'{Mv.to(y+cy+i, x)}{" " * w}'

        # * Draw scrollbar if needed
        if proc.num_procs > cls.select_max:
            if cls.resized:
                Key.mouse["mouse_scroll_up"] = [[x + w - 2 + i, y] for i in range(3)]
                Key.mouse["mouse_scroll_down"] = [
                    [x + w - 2 + i, y + h - 1] for i in range(3)
                ]
            scroll_pos = round(
                cls.start
                * (cls.select_max - 2)
                / (proc.num_procs - (cls.select_max - 2))
            )
            if scroll_pos < 0 or cls.start == 1:
                scroll_pos = 0
            elif scroll_pos > h - 3 or cls.start >= proc.num_procs - cls.select_max:
                scroll_pos = h - 3
            out += (
                f"{Mv.to(y, x+w-1)}{Fx.b}{THEME.main_fg}↑{Mv.to(y+h-1, x+w-1)}↓{Fx.ub}"
                f"{Mv.to(y+1+scroll_pos, x+w-1)}█"
            )
        elif "scroll_up" in Key.mouse:
            del Key.mouse["scroll_up"], Key.mouse["scroll_down"]

        # * Draw current selection and number of processes
        out += (
            f"{Mv.to(y+h, x + w - 3 - len(loc_string))}{THEME.proc_box}{Symbol.title_left}{THEME.title}"
            f"{Fx.b}{loc_string}{Fx.ub}{THEME.proc_box(Symbol.title_right)}"
        )

        # * Clean up dead processes graphs and counters
        cls.count += 1
        if cls.count == 100:
            cls.count = 0
            for p in list(cls.pid_counter):
                if not psutil.pid_exists(p):
                    del cls.pid_counter[p], Graphs.pid_cpu[p]

        Draw.buffer(cls.buffer, f"{out_misc}{out}{Term.fg}", only_save=Menu.active)
        cls.redraw = cls.resized = cls.moved = False


class Timer:
    timestamp: float
    return_zero = False

    @classmethod
    def stamp(cls):
        cls.timestamp = time()

    @classmethod
    def not_zero(cls) -> bool:
        if cls.return_zero:
            cls.return_zero = False
            return False
        return cls.timestamp + (CONFIG.update_ms / 1000) > time()

    @classmethod
    def left(cls) -> float:
        t_left: float = cls.timestamp + (CONFIG.update_ms / 1000) - time()
        if t_left > CONFIG.update_ms / 1000:
            cls.stamp()
            return CONFIG.update_ms / 1000
        return t_left

    @classmethod
    def finish(cls):
        cls.return_zero = True
        cls.timestamp = time() - (CONFIG.update_ms / 1000)
        Key.break_wait()


class UpdateChecker:
    version: str = VERSION
    thread: threading.Thread

    @classmethod
    def run(cls):
        cls.thread = threading.Thread(target=cls._checker)
        cls.thread.start()

    @classmethod
    def _checker(cls):
        try:
            with urllib.request.urlopen("https://github.com/aristocratos/bpytop/raw/master/bpytop.py", timeout=5) as source:  # type: ignore
                for line in source:
                    line = line.decode("utf-8")
                    if line.startswith("VERSION: str ="):
                        cls.version = line[(line.index("=") + 1) :].strip('" \n')
                        break
        except Exception as e:
            errlog.exception(f"{e}")
        else:
            if cls.version != VERSION and which("notify-send"):
                try:
                    subprocess.run(
                        [
                            "notify-send",
                            "-u",
                            "normal",
                            "BpyTop Update!",
                            f"New version of BpyTop available!\nCurrent version: {VERSION}\nNew version: {cls.version}\nDownload at github.com/aristocratos/bpytop",
                            "-i",
                            "update-notifier",
                            "-t",
                            "10000",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    errlog.exception(f"{e}")


# ? Functions ------------------------------------------------------------------------------------->


def create_box(
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
    title: str = "",
    title2: str = "",
    line_color: Color = None,
    title_color: Color = None,
    fill: bool = True,
    box=None,
) -> str:
    """Create a box from a box object or by given arguments"""
    out: str = f"{Term.fg}{Term.bg}"
    num: int = 0
    if not line_color:
        line_color = THEME.div_line
    if not title_color:
        title_color = THEME.title

    # * Get values from box class if given
    if box:
        x = box.x
        y = box.y
        width = box.width
        height = box.height
        title = box.name
        num = box.num
    hlines: Tuple[int, int] = (y, y + height - 1)

    out += f"{line_color}"

    # * Draw all horizontal lines
    for hpos in hlines:
        out += f"{Mv.to(hpos, x)}{Symbol.h_line * (width - 1)}"

    # * Draw all vertical lines and fill if enabled
    for hpos in range(hlines[0] + 1, hlines[1]):
        out += f'{Mv.to(hpos, x)}{Symbol.v_line}{" " * (width-2) if fill else Mv.r(width-2)}{Symbol.v_line}'

    # * Draw corners
    out += f"{Mv.to(y, x)}{Symbol.left_up}\
    {Mv.to(y, x + width - 1)}{Symbol.right_up}\
    {Mv.to(y + height - 1, x)}{Symbol.left_down}\
    {Mv.to(y + height - 1, x + width - 1)}{Symbol.right_down}"

    # * Draw titles if enabled
    if title:
        numbered: str = "" if not num else f"{THEME.hi_fg(SUPERSCRIPT[num])}"
        out += f"{Mv.to(y, x + 2)}{Symbol.title_left}{Fx.b}{numbered}{title_color}{title}{Fx.ub}{line_color}{Symbol.title_right}"
    if title2:
        out += f"{Mv.to(hlines[1], x + 2)}{Symbol.title_left}{title_color}{Fx.b}{title2}{Fx.ub}{line_color}{Symbol.title_right}"

    return f"{out}{Term.fg}{Mv.to(y + 1, x + 1)}"


def now_sleeping(signum, frame):
    """Reset terminal settings and stop background input read before putting to sleep"""
    Key.stop()
    Collector.stop()
    Draw.now(
        Term.clear,
        Term.normal_screen,
        Term.show_cursor,
        Term.mouse_off,
        Term.mouse_direct_off,
        Term.title(),
    )
    Term.echo(True)
    os.kill(os.getpid(), signal.SIGSTOP)


def now_awake(signum, frame):
    """Set terminal settings and restart background input read"""
    Draw.now(
        Term.alt_screen,
        Term.clear,
        Term.hide_cursor,
        Term.mouse_on,
        Term.title("BpyTOP"),
    )
    Term.echo(False)
    Key.start()
    Term.refresh()
    Box.calc_sizes()
    Box.draw_bg()
    Collector.start()


def quit_sigint(signum, frame):
    """SIGINT redirection to clean_quit()"""
    clean_quit()


def clean_quit(errcode: int = 0, errmsg: str = "", thread: bool = False):
    """Stop background input read, save current config and reset terminal settings before quitting"""
    global THREAD_ERROR
    if thread:
        THREAD_ERROR = errcode
        interrupt_main()
        return
    if THREAD_ERROR:
        errcode = THREAD_ERROR
    Key.stop()
    Collector.stop()
    if not errcode:
        CONFIG.save_config()
    Draw.now(
        Term.clear,
        Term.normal_screen,
        Term.show_cursor,
        Term.mouse_off,
        Term.mouse_direct_off,
        Term.title(),
    )
    Term.echo(True)
    if errcode == 0:
        errlog.info(
            f"Exiting. Runtime {timedelta(seconds=round(time() - SELF_START, 0))} \n"
        )
    else:
        errlog.warning(
            f"Exiting with errorcode ({errcode}). Runtime {timedelta(seconds=round(time() - SELF_START, 0))} \n"
        )
        if not errmsg:
            errmsg = f"Bpytop exited with errorcode ({errcode}). See {CONFIG_DIR}/error.log for more information!"
    if errmsg:
        print(errmsg)

    raise SystemExit(errcode)


def readfile(file: str, default: str = "") -> str:
    out: Union[str, None] = None
    if os.path.isfile(file):
        try:
            with open(file, "r") as f:
                out = f.read().strip()
        except:
            pass
    return default if out is None else out


def temperature(value: int, scale: str = "celsius") -> Tuple[int, str]:
    """Returns a tuple with integer value and string unit converted from an integer in celsius to: celsius, fahrenheit, kelvin or rankine."""
    if scale == "celsius":
        return (value, "°C")
    elif scale == "fahrenheit":
        return (round(value * 1.8 + 32), "°F")
    elif scale == "kelvin":
        return (round(value + 273.15), "K ")
    elif scale == "rankine":
        return (round(value * 1.8 + 491.67), "°R")
    else:
        return (0, "")


def process_keys():
    mouse_pos: Tuple[int, int] = (0, 0)
    filtered: bool = False
    box_keys = {"1": "cpu", "2": "mem", "3": "net", "4": "proc"}
    while Key.has_key():
        key = Key.get()
        found: bool = True
        if key in ["mouse_scroll_up", "mouse_scroll_down", "mouse_click"]:
            mouse_pos = Key.get_mouse()
            if (
                mouse_pos[0] >= ProcBox.x
                and ProcBox.current_y + 1
                <= mouse_pos[1]
                < ProcBox.current_y + ProcBox.current_h - 1
            ):
                pass
            elif key == "mouse_click":
                key = "mouse_unselect"
            else:
                key = "_null"

        if ProcBox.filtering:
            if key in ["enter", "mouse_click", "mouse_unselect"]:
                ProcBox.filtering = False
                Collector.collect(ProcCollector, redraw=True, only_draw=True)
                continue
            elif key in ["escape", "delete"]:
                ProcCollector.search_filter = ""
                ProcBox.filtering = False
            elif len(key) == 1:
                ProcCollector.search_filter += key
            elif key == "backspace" and len(ProcCollector.search_filter) > 0:
                ProcCollector.search_filter = ProcCollector.search_filter[:-1]
            else:
                continue
            Collector.collect(ProcCollector, proc_interrupt=True, redraw=True)
            if filtered:
                Collector.collect_done.wait(0.1)
            filtered = True
            continue

        if key == "_null":
            continue
        elif key == "q":
            clean_quit()
        elif key == "+" and CONFIG.update_ms + 100 <= 86399900:
            CONFIG.update_ms += 100
            Box.draw_update_ms()
        elif key == "-" and CONFIG.update_ms - 100 >= 100:
            CONFIG.update_ms -= 100
            Box.draw_update_ms()
        elif key in ["M", "escape"]:
            Menu.main()
        elif key in ["o", "f2"]:
            Menu.options()
        elif key in ["H", "f1"]:
            Menu.help()
        elif key == "m":
            if (
                list(Box.view_modes).index(Box.view_mode) + 1
                > len(list(Box.view_modes)) - 1
            ):
                Box.view_mode = list(Box.view_modes)[0]
            else:
                Box.view_mode = list(Box.view_modes)[
                    (list(Box.view_modes).index(Box.view_mode) + 1)
                ]
            CONFIG.shown_boxes = " ".join(Box.view_modes[Box.view_mode])
            Draw.clear(saved=True)
            Term.refresh(force=True)
        elif key in box_keys:
            boxes = CONFIG.shown_boxes.split()
            if box_keys[key] in boxes:
                boxes.remove(box_keys[key])
            else:
                boxes.append(box_keys[key])
            CONFIG.shown_boxes = " ".join(boxes)
            Box.view_mode = "user"
            Box.view_modes["user"] = CONFIG.shown_boxes.split()
            Draw.clear(saved=True)
            Term.refresh(force=True)
        else:
            found = False

        if found:
            continue

        if "proc" in Box.boxes:
            if key in ["left", "right", "h", "l"]:
                ProcCollector.sorting(key)
            elif key == " " and CONFIG.proc_tree and ProcBox.selected > 0:
                if ProcBox.selected_pid in ProcCollector.collapsed:
                    ProcCollector.collapsed[
                        ProcBox.selected_pid
                    ] = not ProcCollector.collapsed[ProcBox.selected_pid]
                Collector.collect(ProcCollector, interrupt=True, redraw=True)
            elif key == "e":
                CONFIG.proc_tree = not CONFIG.proc_tree
                Collector.collect(ProcCollector, interrupt=True, redraw=True)
            elif key == "r":
                CONFIG.proc_reversed = not CONFIG.proc_reversed
                Collector.collect(ProcCollector, interrupt=True, redraw=True)
            elif key == "c":
                CONFIG.proc_per_core = not CONFIG.proc_per_core
                Collector.collect(ProcCollector, interrupt=True, redraw=True)
            elif key in ["f", "F"]:
                ProcBox.filtering = True
                ProcCollector.case_sensitive = key == "F"
                if not ProcCollector.search_filter:
                    ProcBox.start = 0
                Collector.collect(ProcCollector, redraw=True, only_draw=True)
            elif key in ["T", "K", "I"] and (
                ProcBox.selected > 0 or ProcCollector.detailed
            ):
                pid: int = ProcBox.selected_pid if ProcBox.selected > 0 else ProcCollector.detailed_pid  # type: ignore
                if psutil.pid_exists(pid):
                    if key == "T":
                        sig = signal.SIGTERM
                    elif key == "K":
                        sig = signal.SIGKILL
                    elif key == "I":
                        sig = signal.SIGINT
                    try:
                        os.kill(pid, sig)
                    except Exception as e:
                        errlog.error(
                            f"Exception when sending signal {sig} to pid {pid}"
                        )
                        errlog.exception(f"{e}")
            elif key == "delete" and ProcCollector.search_filter:
                ProcCollector.search_filter = ""
                Collector.collect(ProcCollector, proc_interrupt=True, redraw=True)
            elif key == "enter":
                if (
                    ProcBox.selected > 0
                    and ProcCollector.detailed_pid != ProcBox.selected_pid
                    and psutil.pid_exists(ProcBox.selected_pid)
                ):
                    ProcCollector.detailed = True
                    ProcBox.last_selection = ProcBox.selected
                    ProcBox.selected = 0
                    ProcCollector.detailed_pid = ProcBox.selected_pid
                    ProcBox.resized = True
                    Collector.proc_counter = 1
                elif ProcCollector.detailed:
                    ProcBox.selected = ProcBox.last_selection
                    ProcBox.last_selection = 0
                    ProcCollector.detailed = False
                    ProcCollector.detailed_pid = None
                    ProcBox.resized = True
                    Collector.proc_counter = 1
                else:
                    continue
                ProcCollector.details = {}
                ProcCollector.details_cpu = []
                ProcCollector.details_mem = []
                Graphs.detailed_cpu = NotImplemented
                Graphs.detailed_mem = NotImplemented
                Collector.collect(ProcCollector, proc_interrupt=True, redraw=True)
            elif key in [
                "up",
                "down",
                "mouse_scroll_up",
                "mouse_scroll_down",
                "page_up",
                "page_down",
                "home",
                "end",
                "mouse_click",
                "mouse_unselect",
                "j",
                "k",
            ]:
                ProcBox.selector(key, mouse_pos)

        if "net" in Box.boxes:
            if key in ["b", "n"]:
                NetCollector.switch(key)
            elif key == "z":
                NetCollector.reset = not NetCollector.reset
                Collector.collect(NetCollector, redraw=True)
            elif key == "y":
                CONFIG.net_sync = not CONFIG.net_sync
                Collector.collect(NetCollector, redraw=True)
            elif key == "a":
                NetCollector.auto_min = not NetCollector.auto_min
                NetCollector.net_min = {"download": -1, "upload": -1}
                Collector.collect(NetCollector, redraw=True)

        if "mem" in Box.boxes:
            if key == "g":
                CONFIG.mem_graphs = not CONFIG.mem_graphs
                Collector.collect(MemCollector, interrupt=True, redraw=True)
            elif key == "s":
                Collector.collect_idle.wait()
                CONFIG.swap_disk = not CONFIG.swap_disk
                Collector.collect(MemCollector, interrupt=True, redraw=True)
            elif key == "d":
                Collector.collect_idle.wait()
                CONFIG.show_disks = not CONFIG.show_disks
                Collector.collect(MemCollector, interrupt=True, redraw=True)
            elif key == "i":
                Collector.collect_idle.wait()
                CONFIG.io_mode = not CONFIG.io_mode
                Collector.collect(MemCollector, interrupt=True, redraw=True)


# ? Pre main -------------------------------------------------------------------------------------->


CPU_NAME: str = platform.get_cpu_name()

CORE_MAP: List[int] = platform.get_cpu_core_mapping()

THEME: Theme


def main():
    global THEME

    Term.width = os.get_terminal_size().columns
    Term.height = os.get_terminal_size().lines

    # ? Init -------------------------------------------------------------------------------------->
    if DEBUG:
        TimeIt.start("Init")

    # ? Switch to alternate screen, clear screen, hide cursor, enable mouse reporting and disable input echo
    Draw.now(
        Term.alt_screen,
        Term.clear,
        Term.hide_cursor,
        Term.mouse_on,
        Term.title("BpyTOP"),
    )
    Term.echo(False)
    # Term.refresh(force=True)

    # ? Start a thread checking for updates while running init
    if CONFIG.update_check:
        UpdateChecker.run()

    # ? Draw banner and init status
    if CONFIG.show_init and not Init.resized:
        Init.start()

    # ? Load theme
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Loading theme and creating colors... ")}{Mv.save}',
        )
    try:
        THEME = Theme(CONFIG.color_theme)
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Setup boxes
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Doing some maths and drawing... ")}{Mv.save}',
        )
    try:
        if CONFIG.check_temp:
            CpuCollector.get_sensors()
        Box.calc_sizes()
        Box.draw_bg(now=False)
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Setup signal handlers for SIGSTP, SIGCONT, SIGINT and SIGWINCH
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Setting up signal handlers... ")}{Mv.save}',
        )
    try:
        signal.signal(signal.SIGTSTP, now_sleeping)  # * Ctrl-Z
        signal.signal(signal.SIGCONT, now_awake)  # * Resume
        signal.signal(signal.SIGINT, quit_sigint)  # * Ctrl-C
        signal.signal(signal.SIGWINCH, Term.refresh)  # * Terminal resized
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Start a separate thread for reading keyboard input
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Starting input reader thread... ")}{Mv.save}',
        )
    try:
        if isinstance(sys.stdin, io.TextIOWrapper) and sys.version_info >= (3, 7):
            sys.stdin.reconfigure(errors="ignore")  # type: ignore
        Key.start()
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Start a separate thread for data collection and drawing
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Starting data collection and drawer thread... ")}{Mv.save}',
        )
    try:
        Collector.start()
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Collect data and draw to buffer
    if CONFIG.show_init:
        Draw.buffer(
            "+init!",
            f'{Mv.restore}{Fx.trans("Collecting data and drawing... ")}{Mv.save}',
        )
    try:
        Collector.collect(draw_now=False)
        pass
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    # ? Draw to screen
    if CONFIG.show_init:
        Draw.buffer("+init!", f'{Mv.restore}{Fx.trans("Finishing up... ")}{Mv.save}')
    try:
        Collector.collect_done.wait()
    except Exception as e:
        Init.fail(e)
    else:
        Init.success()

    Init.done()
    Term.refresh()
    Draw.out(clear=True)
    if CONFIG.draw_clock:
        Box.clock_on = True
    if DEBUG:
        TimeIt.stop("Init")

    # ? Main loop ------------------------------------------------------------------------------------->

    def run():
        while not False:
            Term.refresh()
            Timer.stamp()

            while Timer.not_zero():
                if Key.input_wait(Timer.left()):
                    process_keys()

            Collector.collect()

    # ? Start main loop
    try:
        run()
    except Exception as e:
        errlog.exception(f"{e}")
        clean_quit(1)
    else:
        # ? Quit cleanly even if false starts being true...
        clean_quit()


if __name__ == "__main__":
    main()
