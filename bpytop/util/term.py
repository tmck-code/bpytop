import os, sys

class Term:
    """Terminal info and commands"""

    width: int = 0
    height: int = 0
    resized: bool = False
    _w: int = 0
    _h: int = 0
    fg: str = ""  # * Default foreground color
    bg: str = ""  # * Default background color
    hide_cursor = "\033[?25l"  # * Hide terminal cursor
    show_cursor = "\033[?25h"  # * Show terminal cursor
    alt_screen = "\033[?1049h"  # * Switch to alternate screen
    normal_screen = "\033[?1049l"  # * Switch to normal screen
    clear = "\033[2J\033[0;0f"  # * Clear screen and set cursor to position 0,0
    mouse_on = "\033[?1002h\033[?1015h\033[?1006h"  # * Enable reporting of mouse position on click and release
    mouse_off = "\033[?1002l"  # * Disable mouse reporting
    mouse_direct_on = (
        "\033[?1003h"  # * Enable reporting of mouse position at any movement
    )
    mouse_direct_off = "\033[?1003l"  # * Disable direct mouse reporting
    winch = threading.Event()
    old_boxes: List = []
    min_width: int = 0
    min_height: int = 0

    @classmethod
    def refresh(cls, *args, force: bool = False):
        """Update width, height and set resized flag if terminal has been resized"""
        if Init.running:
            cls.resized = False
            return
        if cls.resized:
            cls.winch.set()
            return
        cls._w, cls._h = os.get_terminal_size()
        if (
            (cls._w, cls._h) == (cls.width, cls.height)
            and cls.old_boxes == Box.boxes
            and not force
        ):
            return
        if force:
            Collector.collect_interrupt = True
        if cls.old_boxes != Box.boxes:
            w_p = h_p = 0
            cls.min_width = cls.min_height = 0
            cls.old_boxes = Box.boxes.copy()
            for box_class in Box.__subclasses__():
                for box_name in Box.boxes:
                    if box_name in str(box_class).capitalize():
                        if (
                            not (box_name == "cpu" and "proc" in Box.boxes)
                            and not (box_name == "net" and "mem" in Box.boxes)
                            and w_p + box_class.width_p <= 100
                        ):
                            w_p += box_class.width_p
                            cls.min_width += getattr(box_class, "min_w", 0)
                        if (
                            not (box_name in ["mem", "net"] and "proc" in Box.boxes)
                            and h_p + box_class.height_p <= 100
                        ):
                            h_p += box_class.height_p
                            cls.min_height += getattr(box_class, "min_h", 0)
        while (cls._w, cls._h) != (cls.width, cls.height) or (
            cls._w < cls.min_width or cls._h < cls.min_height
        ):
            if Init.running:
                Init.resized = True
            CpuBox.clock_block = True
            cls.resized = True
            Collector.collect_interrupt = True
            cls.width, cls.height = cls._w, cls._h
            Draw.now(Term.clear)
            box_width = min(50, cls._w - 2)
            Draw.now(
                f'{create_box(cls._w // 2 - box_width // 2, cls._h // 2 - 2, 50, 3, "resizing", line_color=Colors.green, title_color=Colors.white)}',
                f"{Mv.r(box_width // 4)}{Colors.default}{Colors.black_bg}{Fx.b}Width : {cls._w}   Height: {cls._h}{Fx.ub}{Term.bg}{Term.fg}",
            )
            if cls._w < 80 or cls._h < 24:
                while cls._w < cls.min_width or cls._h < cls.min_height:
                    Draw.now(Term.clear)
                    box_width = min(50, cls._w - 2)
                    Draw.now(
                        f'{create_box(cls._w // 2 - box_width // 2, cls._h // 2 - 2, box_width, 4, "warning", line_color=Colors.red, title_color=Colors.white)}',
                        f"{Mv.r(box_width // 4)}{Colors.default}{Colors.black_bg}{Fx.b}Width: {Colors.red if cls._w < cls.min_width else Colors.green}{cls._w}   ",
                        f"{Colors.default}Height: {Colors.red if cls._h < cls.min_height else Colors.green}{cls._h}{Term.bg}{Term.fg}",
                        f"{Mv.d(1)}{Mv.l(25)}{Colors.default}{Colors.black_bg}Current config need: {cls.min_width} x {cls.min_height}{Fx.ub}{Term.bg}{Term.fg}",
                    )
                    cls.winch.wait(0.3)
                    while Key.has_key():
                        if Key.last() == "q":
                            clean_quit()
                    cls.winch.clear()
                    cls._w, cls._h = os.get_terminal_size()
            else:
                cls.winch.wait(0.3)
                cls.winch.clear()
            cls._w, cls._h = os.get_terminal_size()

        Key.mouse = {}
        Box.calc_sizes()
        Collector.proc_counter = 1
        if Menu.active:
            Menu.resized = True
        Box.draw_bg(now=False)
        cls.resized = False
        Timer.finish()

    @staticmethod
    def echo(on: bool):
        """Toggle input echo"""
        (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) = termios.tcgetattr(
            sys.stdin.fileno()
        )
        if on:
            lflag |= termios.ECHO  # type: ignore
        else:
            lflag &= ~termios.ECHO  # type: ignore
        new_attr = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, new_attr)

    @staticmethod
    def title(text: str = "") -> str:
        out: str = f'{os.environ.get("TERMINAL_TITLE", "")}'
        if out and text:
            out += " "
        if text:
            out += f"{text}"
        return f"\033]0;{out}\a"
