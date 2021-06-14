from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, Tuple

DEFAULT_MENU_COLORS: Dict[str, Tuple[str, ...]] = {
    "normal": ("#0fd7ff", "#00bfe6", "#00a6c7", "#008ca8"),
    "selected": ("#ffa50a", "#f09800", "#db8b00", "#c27b00"),
}

@dataclass
class MenuTitle:
    text: str
    focus: str
    colour: str

    @staticmethod
    def load(fpath, focus):
        with open(fpath) as istream:
            text = istream.read()
        return MenuTitle(
            text=text,
            focus=focus,
            colour=DEFAULT_MENU_COLORS[focus],
        )
        

@dataclass
class MenuTitles:
    options: MenuTitle
    help:    MenuTitle
    quit:    MenuTitle

    @staticmethod
    def load():
        pass
        # return MenuTitles(
        #     options=MenuTitle.
        # )


def titles():
    titles = defaultdict(dict)
    for menu_title in ['options', 'help', 'quit']:
        for typ in ['normal', 'selected']:
            with open(f'bpytop/ui/{menu_title}_{typ}.txt') as istream:
                titles[menu_title][typ] = istream.read()
    return titles


class Menu:
    """Holds all menus"""

    active: bool = False
    close: bool = False
    resized: bool = True
    menus: Dict[str, Dict[str, str]] = {}
    menu_length: Dict[str, int] = {}
    background: str = ""
    for name, menu in MENUS.items():
        menu_length[name] = len(menu["normal"][0])
        menus[name] = {}
        for sel in ["normal", "selected"]:
            menus[name][sel] = ""
            for i in range(len(menu[sel])):
                menus[name][sel] += Fx.trans(
                    f"{Color.fg(MENU_COLORS[sel][i])}{menu[sel][i]}"
                )
                if i < len(menu[sel]) - 1:
                    menus[name][sel] += f"{Mv.d(1)}{Mv.l(len(menu[sel][i]))}"

    @classmethod
    def main(cls):
        if Term.width < 80 or Term.height < 24:
            errlog.warning(
                f"The menu system only works on a terminal size of 80x24 or above!"
            )
            return
        out: str = ""
        banner: str = ""
        redraw: bool = True
        key: str = ""
        mx: int = 0
        my: int = 0
        skip: bool = False
        mouse_over: bool = False
        mouse_items: Dict[str, Dict[str, int]] = {}
        cls.active = True
        cls.resized = True
        menu_names: List[str] = list(cls.menus.keys())
        menu_index: int = 0
        menu_current: str = menu_names[0]
        cls.background = (
            f"{THEME.inactive_fg}" + Fx.uncolor(f"{Draw.saved_buffer()}") + f"{Term.fg}"
        )

        while not cls.close:
            key = ""
            if cls.resized:
                banner = (
                    f"{Banner.draw(Term.height // 2 - 10, center=True)}{Mv.d(1)}{Mv.l(46)}{Colors.black_bg}{Colors.default}{Fx.b}← esc"
                    f"{Mv.r(30)}{Fx.i}Version: {VERSION}{Fx.ui}{Fx.ub}{Term.bg}{Term.fg}"
                )
                if UpdateChecker.version != VERSION:
                    banner += f"{Mv.to(Term.height, 1)}{Fx.b}{THEME.title}New release {UpdateChecker.version} available at https://github.com/aristocratos/bpytop{Fx.ub}{Term.fg}"
                cy = 0
                for name, menu in cls.menus.items():
                    ypos = Term.height // 2 - 2 + cy
                    xpos = Term.width // 2 - (cls.menu_length[name] // 2)
                    mouse_items[name] = {
                        "x1": xpos,
                        "x2": xpos + cls.menu_length[name] - 1,
                        "y1": ypos,
                        "y2": ypos + 2,
                    }
                    cy += 3
                redraw = True
                cls.resized = False

            if redraw:
                out = ""
                for name, menu in cls.menus.items():
                    out += f'{Mv.to(mouse_items[name]["y1"], mouse_items[name]["x1"])}{menu["selected" if name == menu_current else "normal"]}'

            if skip and redraw:
                Draw.now(out)
            elif not skip:
                Draw.now(f"{cls.background}{banner}{out}")
            skip = redraw = False

            if Key.input_wait(Timer.left(), mouse=True):
                if Key.mouse_moved():
                    mx, my = Key.get_mouse()
                    for name, pos in mouse_items.items():
                        if (
                            pos["x1"] <= mx <= pos["x2"]
                            and pos["y1"] <= my <= pos["y2"]
                        ):
                            mouse_over = True
                            if name != menu_current:
                                menu_current = name
                                menu_index = menu_names.index(name)
                                redraw = True
                            break
                    else:
                        mouse_over = False
                else:
                    key = Key.get()

                if key == "mouse_click" and not mouse_over:
                    key = "M"

                if key == "q":
                    clean_quit()
                elif key in ["escape", "M"]:
                    cls.close = True
                    break
                elif key in ["up", "mouse_scroll_up", "shift_tab"]:
                    menu_index -= 1
                    if menu_index < 0:
                        menu_index = len(menu_names) - 1
                    menu_current = menu_names[menu_index]
                    redraw = True
                elif key in ["down", "mouse_scroll_down", "tab"]:
                    menu_index += 1
                    if menu_index > len(menu_names) - 1:
                        menu_index = 0
                    menu_current = menu_names[menu_index]
                    redraw = True
                elif key == "enter" or (key == "mouse_click" and mouse_over):
                    if menu_current == "quit":
                        clean_quit()
                    elif menu_current == "options":
                        cls.options()
                        cls.resized = True
                    elif menu_current == "help":
                        cls.help()
                        cls.resized = True

            if Timer.not_zero() and not cls.resized:
                skip = True
            else:
                Collector.collect()
                Collector.collect_done.wait(2)
                if CONFIG.background_update:
                    cls.background = (
                        f"{THEME.inactive_fg}"
                        + Fx.uncolor(f"{Draw.saved_buffer()}")
                        + f"{Term.fg}"
                    )
                Timer.stamp()

        Draw.now(f"{Draw.saved_buffer()}")
        cls.background = ""
        cls.active = False
        cls.close = False

    @classmethod
    def help(cls):
        if Term.width < 80 or Term.height < 24:
            errlog.warning(
                f"The menu system only works on a terminal size of 80x24 or above!"
            )
            return
        out: str = ""
        out_misc: str = ""
        redraw: bool = True
        key: str = ""
        skip: bool = False
        main_active: bool = cls.active
        cls.active = True
        cls.resized = True
        if not cls.background:
            cls.background = (
                f"{THEME.inactive_fg}"
                + Fx.uncolor(f"{Draw.saved_buffer()}")
                + f"{Term.fg}"
            )
        help_items: Dict[str, str] = {
            "(Mouse 1)": "Clicks buttons and selects in process list.",
            "Selected (Mouse 1)": "Show detailed information for selected process.",
            "(Mouse scroll)": "Scrolls any scrollable list/text under cursor.",
            "(Esc, shift+m)": "Toggles main menu.",
            "(m)": "Cycle view presets, order: full->proc->stat->user.",
            "(1)": "Toggle CPU box.",
            "(2)": "Toggle MEM box.",
            "(3)": "Toggle NET box.",
            "(4)": "Toggle PROC box.",
            "(d)": "Toggle disks view in MEM box.",
            "(F2, o)": "Shows options.",
            "(F1, shift+h)": "Shows this window.",
            "(ctrl+z)": "Sleep program and put in background.",
            "(ctrl+c, q)": "Quits program.",
            "(+) / (-)": "Add/Subtract 100ms to/from update timer.",
            "(Up, k) (Down, j)": "Select in process list.",
            "(Enter)": "Show detailed information for selected process.",
            "(Spacebar)": "Expand/collapse the selected process in tree view.",
            "(Pg Up) (Pg Down)": "Jump 1 page in process list.",
            "(Home) (End)": "Jump to first or last page in process list.",
            "(Left, h) (Right, l)": "Select previous/next sorting column.",
            "(b) (n)": "Select previous/next network device.",
            "(s)": "Toggle showing swap as a disk.",
            "(i)": "Toggle disks io mode with big graphs.",
            "(z)": "Toggle totals reset for current network device",
            "(a)": "Toggle auto scaling for the network graphs.",
            "(y)": "Toggle synced scaling mode for network graphs.",
            "(f)": "Input a NON case-sensitive process filter.",
            "(shift+f)": "Input a case-sensitive process filter.",
            "(c)": "Toggle per-core cpu usage of processes.",
            "(r)": "Reverse sorting order in processes box.",
            "(e)": "Toggle processes tree view.",
            "(delete)": "Clear any entered filter.",
            "Selected (shift+t)": "Terminate selected process with SIGTERM - 15.",
            "Selected (shift+k)": "Kill selected process with SIGKILL - 9.",
            "Selected (shift+i)": "Interrupt selected process with SIGINT - 2.",
            "_1": " ",
            "_2": "For bug reporting and project updates, visit:",
            "_3": "https://github.com/aristocratos/bpytop",
        }

        while not cls.close:
            key = ""
            if cls.resized:
                y = (
                    8
                    if Term.height < len(help_items) + 10
                    else Term.height // 2 - len(help_items) // 2 + 4
                )
                out_misc = (
                    f"{Banner.draw(y-7, center=True)}{Mv.d(1)}{Mv.l(46)}{Colors.black_bg}{Colors.default}{Fx.b}← esc"
                    f"{Mv.r(30)}{Fx.i}Version: {VERSION}{Fx.ui}{Fx.ub}{Term.bg}{Term.fg}"
                )
                x = Term.width // 2 - 36
                h, w = Term.height - 2 - y, 72
                if len(help_items) > h:
                    pages = ceil(len(help_items) / h)
                else:
                    h = len(help_items)
                    pages = 0
                page = 1
                out_misc += create_box(
                    x, y, w, h + 3, "help", line_color=THEME.div_line
                )
                redraw = True
                cls.resized = False

            if redraw:
                out = ""
                cy = 0
                if pages:
                    out += (
                        f'{Mv.to(y, x+56)}{THEME.div_line(Symbol.title_left)}{Fx.b}{THEME.title("pg")}{Fx.ub}{THEME.main_fg(Symbol.up)} {Fx.b}{THEME.title}{page}/{pages} '
                        f"pg{Fx.ub}{THEME.main_fg(Symbol.down)}{THEME.div_line(Symbol.title_right)}"
                    )
                out += f'{Mv.to(y+1, x+1)}{THEME.title}{Fx.b}{"Keys:":^20}Description:{THEME.main_fg}'
                for n, (keys, desc) in enumerate(help_items.items()):
                    if pages and n < (page - 1) * h:
                        continue
                    out += f'{Mv.to(y+2+cy, x+1)}{Fx.b}{("" if keys.startswith("_") else keys):^20.20}{Fx.ub}{desc:50.50}'
                    cy += 1
                    if cy == h:
                        break
                if cy < h:
                    for i in range(h - cy):
                        out += f'{Mv.to(y+2+cy+i, x+1)}{" " * (w-2)}'

            if skip and redraw:
                Draw.now(out)
            elif not skip:
                Draw.now(f"{cls.background}{out_misc}{out}")
            skip = redraw = False

            if Key.input_wait(Timer.left()):
                key = Key.get()

                if key == "mouse_click":
                    mx, my = Key.get_mouse()
                    if x <= mx < x + w and y <= my < y + h + 3:
                        if pages and my == y and x + 56 < mx < x + 61:
                            key = "up"
                        elif pages and my == y and x + 63 < mx < x + 68:
                            key = "down"
                    else:
                        key = "escape"

                if key == "q":
                    clean_quit()
                elif key in ["escape", "M", "enter", "backspace", "H", "f1"]:
                    cls.close = True
                    break
                elif key in ["up", "mouse_scroll_up", "page_up"] and pages:
                    page -= 1
                    if page < 1:
                        page = pages
                    redraw = True
                elif key in ["down", "mouse_scroll_down", "page_down"] and pages:
                    page += 1
                    if page > pages:
                        page = 1
                    redraw = True

            if Timer.not_zero() and not cls.resized:
                skip = True
            else:
                Collector.collect()
                Collector.collect_done.wait(2)
                if CONFIG.background_update:
                    cls.background = (
                        f"{THEME.inactive_fg}"
                        + Fx.uncolor(f"{Draw.saved_buffer()}")
                        + f"{Term.fg}"
                    )
                Timer.stamp()

        if main_active:
            cls.close = False
            return
        Draw.now(f"{Draw.saved_buffer()}")
        cls.background = ""
        cls.active = False
        cls.close = False

    @classmethod
    def options(cls):
        if Term.width < 80 or Term.height < 24:
            errlog.warning(
                f"The menu system only works on a terminal size of 80x24 or above!"
            )
            return
        out: str = ""
        out_misc: str = ""
        redraw: bool = True
        selected_cat: str = ""
        selected_int: int = 0
        option_items: Dict[str, List[str]] = {}
        cat_list: List[str] = []
        cat_int: int = 0
        change_cat: bool = False
        key: str = ""
        skip: bool = False
        main_active: bool = cls.active
        cls.active = True
        cls.resized = True
        d_quote: str
        inputting: bool = False
        input_val: str = ""
        Theme.refresh()
        if not cls.background:
            cls.background = (
                f"{THEME.inactive_fg}"
                + Fx.uncolor(f"{Draw.saved_buffer()}")
                + f"{Term.fg}"
            )
        categories: Dict[str, Dict[str, List[str]]] = {
            "system": {
                "color_theme": [
                    "Set color theme.",
                    "",
                    "Choose from all theme files in",
                    '"/usr/[local/]share/bpytop/themes" and',
                    '"~/.config/bpytop/themes".',
                    "",
                    '"Default" for builtin default theme.',
                    'User themes are prefixed by a plus sign "+".',
                    "",
                    "For theme updates see:",
                    "https://github.com/aristocratos/bpytop",
                ],
                "theme_background": [
                    "If the theme set background should be shown.",
                    "",
                    "Set to False if you want terminal background",
                    "transparency.",
                ],
                "truecolor": [
                    "Sets if 24-bit truecolor should be used.",
                    "(Requires restart to take effect!)",
                    "",
                    "Will convert 24-bit colors to 256 color",
                    "(6x6x6 color cube) if False.",
                    "",
                    "Set to False if your terminal doesn't have",
                    "truecolor support and can't convert to",
                    "256-color.",
                ],
                "shown_boxes": [
                    "Manually set which boxes to show.",
                    "",
                    'Available values are "cpu mem net proc".',
                    "Seperate values with whitespace.",
                    "",
                    'Toggle between presets with mode key "m".',
                ],
                "update_ms": [
                    "Update time in milliseconds.",
                    "",
                    "Recommended 2000 ms or above for better sample",
                    "times for graphs.",
                    "",
                    "Min value: 100 ms",
                    "Max value: 86400000 ms = 24 hours.",
                ],
                "draw_clock": [
                    "Draw a clock at top of screen.",
                    "(Only visible if cpu box is enabled!)",
                    "",
                    "Formatting according to strftime, empty",
                    "string to disable.",
                    "",
                    "Custom formatting options:",
                    '"/host" = hostname',
                    '"/user" = username',
                    '"/uptime" = system uptime',
                    "",
                    "Examples of strftime formats:",
                    '"%X" = locale HH:MM:SS',
                    '"%H" = 24h hour, "%I" = 12h hour',
                    '"%M" = minute, "%S" = second',
                    '"%d" = day, "%m" = month, "%y" = year',
                ],
                "background_update": [
                    "Update main ui when menus are showing.",
                    "",
                    "True or False.",
                    "",
                    "Set this to false if the menus is flickering",
                    "too much for a comfortable experience.",
                ],
                "show_battery": [
                    "Show battery stats.",
                    "(Only visible if cpu box is enabled!)",
                    "",
                    "Show battery stats in the top right corner",
                    "if a battery is present.",
                ],
                "show_init": [
                    "Show init screen at startup.",
                    "",
                    "The init screen is purely cosmetical and",
                    "slows down start to show status messages.",
                ],
                "update_check": [
                    "Check for updates at start.",
                    "",
                    "Checks for latest version from:",
                    "https://github.com/aristocratos/bpytop",
                ],
                "log_level": [
                    "Set loglevel for error.log",
                    "",
                    'Levels are: "ERROR" "WARNING" "INFO" "DEBUG".',
                    "The level set includes all lower levels,",
                    'i.e. "DEBUG" will show all logging info.',
                ],
            },
            "cpu": {
                "cpu_graph_upper": [
                    "Sets the CPU stat shown in upper half of",
                    "the CPU graph.",
                    "",
                    '"total" = Total cpu usage.',
                    '"user" = User mode cpu usage.',
                    '"system" = Kernel mode cpu usage.',
                    "See:",
                    "https://psutil.readthedocs.io/en/latest/",
                    "#psutil.cpu_times",
                    "for attributes available on specific platforms.",
                ],
                "cpu_graph_lower": [
                    "Sets the CPU stat shown in lower half of",
                    "the CPU graph.",
                    "",
                    '"total" = Total cpu usage.',
                    '"user" = User mode cpu usage.',
                    '"system" = Kernel mode cpu usage.',
                    "See:",
                    "https://psutil.readthedocs.io/en/latest/",
                    "#psutil.cpu_times",
                    "for attributes available on specific platforms.",
                ],
                "cpu_invert_lower": [
                    "Toggles orientation of the lower CPU graph.",
                    "",
                    "True or False.",
                ],
                "cpu_single_graph": [
                    "Completely disable the lower CPU graph.",
                    "",
                    "Shows only upper CPU graph and resizes it",
                    "to fit to box height.",
                    "",
                    "True or False.",
                ],
                "check_temp": [
                    "Enable cpu temperature reporting.",
                    "",
                    "True or False.",
                ],
                "cpu_sensor": [
                    "Cpu temperature sensor",
                    "",
                    "Select the sensor that corresponds to",
                    "your cpu temperature.",
                    'Set to "Auto" for auto detection.',
                ],
                "show_coretemp": [
                    "Show temperatures for cpu cores.",
                    "",
                    "Only works if check_temp is True and",
                    "the system is reporting core temps.",
                ],
                "temp_scale": [
                    "Which temperature scale to use.",
                    "",
                    "Celsius, default scale.",
                    "",
                    "Fahrenheit, the american one.",
                    "",
                    "Kelvin, 0 = absolute zero, 1 degree change",
                    "equals 1 degree change in Celsius.",
                    "",
                    "Rankine, 0 = abosulte zero, 1 degree change",
                    "equals 1 degree change in Fahrenheit.",
                ],
                "show_cpu_freq": [
                    "Show CPU frequency",
                    "",
                    "Can cause slowdowns on systems with many",
                    "cores and psutil versions below 5.8.1",
                ],
                "custom_cpu_name": [
                    "Custom cpu model name in cpu percentage box.",
                    "",
                    "Empty string to disable.",
                ],
                "show_uptime": [
                    "Shows the system uptime in the CPU box.",
                    "",
                    "Can also be shown in the clock by using",
                    '"/uptime" in the formatting.',
                    "",
                    "True or False.",
                ],
            },
            "mem": {
                "mem_graphs": ["Show graphs for memory values.", "", "True or False."],
                "show_disks": [
                    "Split memory box to also show disks.",
                    "",
                    "True or False.",
                ],
                "show_io_stat": [
                    "Toggle small IO stat graphs.",
                    "",
                    "Toggles the small IO graphs for the regular",
                    "disk usage view.",
                    "",
                    "True or False.",
                ],
                "io_mode": [
                    "Toggles io mode for disks.",
                    "",
                    "Shows big graphs for disk read/write speeds",
                    "instead of used/free percentage meters.",
                    "",
                    "True or False.",
                ],
                "io_graph_combined": [
                    "Toggle combined read and write graphs.",
                    "",
                    'Only has effect if "io mode" is True.',
                    "",
                    "True or False.",
                ],
                "io_graph_speeds": [
                    "Set top speeds for the io graphs.",
                    "",
                    "Manually set which speed in MiB/s that equals",
                    "100 percent in the io graphs.",
                    "(10 MiB/s by default).",
                    "",
                    'Format: "device:speed" seperate disks with a',
                    'comma ",".',
                    "",
                    'Example: "/dev/sda:100, /dev/sdb:20".',
                ],
                "show_swap": [
                    "If swap memory should be shown in memory box.",
                    "",
                    "True or False.",
                ],
                "swap_disk": [
                    "Show swap as a disk.",
                    "",
                    "Ignores show_swap value above.",
                    "Inserts itself after first disk.",
                ],
                "only_physical": [
                    "Filter out non physical disks.",
                    "",
                    "Set this to False to include network disks,",
                    "RAM disks and similar.",
                    "",
                    "True or False.",
                ],
                "use_fstab": [
                    "Read disks list from /etc/fstab.",
                    "(Has no effect on macOS X)",
                    "",
                    "This also disables only_physical.",
                    "",
                    "True or False.",
                ],
                "disks_filter": [
                    "Optional filter for shown disks.",
                    "",
                    "Should be full path of a mountpoint,",
                    '"root" replaces "/", separate multiple values',
                    'with a comma ",".',
                    'Begin line with "exclude=" to change to exclude',
                    "filter.",
                    'Oterwise defaults to "most include" filter.',
                    "",
                    'Example: disks_filter="exclude=/boot, /home/user"',
                ],
            },
            "net": {
                "net_download": [
                    "Fixed network graph download value.",
                    "",
                    'Default "10M" = 10 MibiBytes.',
                    "Possible units:",
                    '"K" (KiB), "M" (MiB), "G" (GiB).',
                    "",
                    'Append "bit" for bits instead of bytes,',
                    'i.e "100Mbit"',
                    "",
                    "Can be toggled with auto button.",
                ],
                "net_upload": [
                    "Fixed network graph upload value.",
                    "",
                    'Default "10M" = 10 MibiBytes.',
                    "Possible units:",
                    '"K" (KiB), "M" (MiB), "G" (GiB).',
                    "",
                    'Append "bit" for bits instead of bytes,',
                    'i.e "100Mbit"',
                    "",
                    "Can be toggled with auto button.",
                ],
                "net_auto": [
                    "Start in network graphs auto rescaling mode.",
                    "",
                    "Ignores any values set above at start and",
                    "rescales down to 10KibiBytes at the lowest.",
                    "",
                    "True or False.",
                ],
                "net_sync": [
                    "Network scale sync.",
                    "",
                    "Syncs the scaling for download and upload to",
                    "whichever currently has the highest scale.",
                    "",
                    "True or False.",
                ],
                "net_color_fixed": [
                    "Set network graphs color gradient to fixed.",
                    "",
                    "If True the network graphs color is based",
                    "on the total bandwidth usage instead of",
                    "the current autoscaling.",
                    "",
                    "The bandwidth usage is based on the",
                    '"net_download" and "net_upload" values set',
                    "above.",
                ],
                "net_iface": [
                    "Network Interface.",
                    "",
                    "Manually set the starting Network Interface.",
                    "Will otherwise automatically choose the NIC",
                    "with the highest total download since boot.",
                ],
            },
            "proc": {
                "proc_update_mult": [
                    "Processes update multiplier.",
                    "Sets how often the process list is updated as",
                    'a multiplier of "update_ms".',
                    "",
                    "Set to 2 or higher to greatly decrease bpytop",
                    "cpu usage. (Only integers)",
                ],
                "proc_sorting": [
                    "Processes sorting option.",
                    "",
                    'Possible values: "pid", "program", "arguments",',
                    '"threads", "user", "memory", "cpu lazy" and',
                    '"cpu responsive".',
                    "",
                    '"cpu lazy" updates top process over time,',
                    '"cpu responsive" updates top process directly.',
                ],
                "proc_reversed": [
                    "Reverse processes sorting order.",
                    "",
                    "True or False.",
                ],
                "proc_tree": [
                    "Processes tree view.",
                    "",
                    "Set true to show processes grouped by parents,",
                    "with lines drawn between parent and child",
                    "process.",
                ],
                "tree_depth": [
                    "Process tree auto collapse depth.",
                    "",
                    "Sets the depth where the tree view will auto",
                    "collapse processes at.",
                ],
                "proc_colors": [
                    "Enable colors in process view.",
                    "",
                    "Uses the cpu graph gradient colors.",
                ],
                "proc_gradient": [
                    "Enable process view gradient fade.",
                    "",
                    "Fades from top or current selection.",
                    "Max fade value is equal to current themes",
                    '"inactive_fg" color value.',
                ],
                "proc_per_core": [
                    "Process usage per core.",
                    "",
                    "If process cpu usage should be of the core",
                    "it's running on or usage of the total",
                    "available cpu power.",
                    "",
                    "If true and process is multithreaded",
                    "cpu usage can reach over 100%.",
                ],
                "proc_mem_bytes": [
                    "Show memory as bytes in process list.",
                    " ",
                    "True or False.",
                ],
            },
        }

        loglevel_i: int = CONFIG.log_levels.index(CONFIG.log_level)
        cpu_sensor_i: int = CONFIG.cpu_sensors.index(CONFIG.cpu_sensor)
        cpu_graph_i: Dict[str, int] = {
            "cpu_graph_upper": CONFIG.cpu_percent_fields.index(CONFIG.cpu_graph_upper),
            "cpu_graph_lower": CONFIG.cpu_percent_fields.index(CONFIG.cpu_graph_lower),
        }
        temp_scale_i: int = CONFIG.temp_scales.index(CONFIG.temp_scale)
        color_i: int
        max_opt_len: int = max([len(categories[x]) for x in categories]) * 2
        cat_list = list(categories)
        while not cls.close:
            key = ""
            if cls.resized or change_cat:
                cls.resized = change_cat = False
                selected_cat = list(categories)[cat_int]
                option_items = categories[cat_list[cat_int]]
                option_len: int = len(option_items) * 2
                y = (
                    12
                    if Term.height < max_opt_len + 13
                    else Term.height // 2 - max_opt_len // 2 + 7
                )
                out_misc = (
                    f"{Banner.draw(y-10, center=True)}{Mv.d(1)}{Mv.l(46)}{Colors.black_bg}{Colors.default}{Fx.b}← esc"
                    f"{Mv.r(30)}{Fx.i}Version: {VERSION}{Fx.ui}{Fx.ub}{Term.bg}{Term.fg}"
                )
                x = Term.width // 2 - 38
                x2 = x + 27
                h, w, w2 = min(Term.height - 1 - y, option_len), 26, 50
                h -= h % 2
                color_i = list(Theme.themes).index(THEME.current)
                out_misc += create_box(
                    x,
                    y - 3,
                    w + w2 + 1,
                    3,
                    f"tab{Symbol.right}",
                    line_color=THEME.div_line,
                )
                out_misc += create_box(
                    x, y, w, h + 2, "options", line_color=THEME.div_line
                )
                redraw = True

                cat_width = floor((w + w2) / len(categories))
                out_misc += f"{Fx.b}"
                for cx, cat in enumerate(categories):
                    out_misc += f"{Mv.to(y-2, x + 1 + (cat_width * cx) + round(cat_width / 2 - len(cat) / 2 ))}"
                    if cat == selected_cat:
                        out_misc += f"{THEME.hi_fg}[{THEME.title}{Fx.u}{cat}{Fx.uu}{THEME.hi_fg}]"
                    else:
                        out_misc += (
                            f"{THEME.hi_fg}{SUPERSCRIPT[cx+1]}{THEME.title}{cat}"
                        )
                out_misc += f"{Fx.ub}"
                if option_len > h:
                    pages = ceil(option_len / h)
                else:
                    h = option_len
                    pages = 0
                page = pages if selected_int == -1 and pages > 0 else 1
                selected_int = 0 if selected_int >= 0 else len(option_items) - 1
            if redraw:
                out = ""
                cy = 0

                selected = list(option_items)[selected_int]
                if pages:
                    out += (
                        f'{Mv.to(y+h+1, x+11)}{THEME.div_line(Symbol.title_left)}{Fx.b}{THEME.title("pg")}{Fx.ub}{THEME.main_fg(Symbol.up)} {Fx.b}{THEME.title}{page}/{pages} '
                        f"pg{Fx.ub}{THEME.main_fg(Symbol.down)}{THEME.div_line(Symbol.title_right)}"
                    )
                # out += f'{Mv.to(y+1, x+1)}{THEME.title}{Fx.b}{"Keys:":^20}Description:{THEME.main_fg}'
                for n, opt in enumerate(option_items):
                    if pages and n < (page - 1) * ceil(h / 2):
                        continue
                    value = getattr(CONFIG, opt)
                    t_color = (
                        f"{THEME.selected_bg}{THEME.selected_fg}"
                        if opt == selected
                        else f"{THEME.title}"
                    )
                    v_color = "" if opt == selected else f"{THEME.title}"
                    d_quote = '"' if isinstance(value, str) else ""
                    if opt == "color_theme":
                        counter = f" {color_i + 1}/{len(Theme.themes)}"
                    elif opt == "proc_sorting":
                        counter = f" {CONFIG.sorting_options.index(CONFIG.proc_sorting) + 1}/{len(CONFIG.sorting_options)}"
                    elif opt == "log_level":
                        counter = f" {loglevel_i + 1}/{len(CONFIG.log_levels)}"
                    elif opt == "cpu_sensor":
                        counter = f" {cpu_sensor_i + 1}/{len(CONFIG.cpu_sensors)}"
                    elif opt in ["cpu_graph_upper", "cpu_graph_lower"]:
                        counter = (
                            f" {cpu_graph_i[opt] + 1}/{len(CONFIG.cpu_percent_fields)}"
                        )
                    elif opt == "temp_scale":
                        counter = f" {temp_scale_i + 1}/{len(CONFIG.temp_scales)}"
                    else:
                        counter = ""
                    out += f'{Mv.to(y+1+cy, x+1)}{t_color}{Fx.b}{opt.replace("_", " ").capitalize() + counter:^24.24}{Fx.ub}{Mv.to(y+2+cy, x+1)}{v_color}'
                    if opt == selected:
                        if isinstance(value, bool) or opt in [
                            "color_theme",
                            "proc_sorting",
                            "log_level",
                            "cpu_sensor",
                            "cpu_graph_upper",
                            "cpu_graph_lower",
                            "temp_scale",
                        ]:
                            out += f"{t_color} {Symbol.left}{v_color}{d_quote + str(value) + d_quote:^20.20}{t_color}{Symbol.right} "
                        elif inputting:
                            out += f'{str(input_val)[-17:] + Fx.bl + "█" + Fx.ubl + "" + Symbol.enter:^33.33}'
                        else:
                            out += (
                                (
                                    f"{t_color} {Symbol.left}{v_color}"
                                    if type(value) is int
                                    else "  "
                                )
                                + f'{str(value) + " " + Symbol.enter:^20.20}'
                                + (
                                    f"{t_color}{Symbol.right} "
                                    if type(value) is int
                                    else "  "
                                )
                            )
                    else:
                        out += f"{d_quote + str(value) + d_quote:^24.24}"
                    out += f"{Term.bg}"
                    if opt == selected:
                        h2 = len(option_items[opt]) + 2
                        y2 = y + (selected_int * 2) - ((page - 1) * h)
                        if y2 + h2 > Term.height:
                            y2 = Term.height - h2
                        out += f'{create_box(x2, y2, w2, h2, "description", line_color=THEME.div_line)}{THEME.main_fg}'
                        for n, desc in enumerate(option_items[opt]):
                            out += f"{Mv.to(y2+1+n, x2+2)}{desc:.48}"
                    cy += 2
                    if cy >= h:
                        break
                if cy < h:
                    for i in range(h - cy):
                        out += f'{Mv.to(y+1+cy+i, x+1)}{" " * (w-2)}'

            if not skip or redraw:
                Draw.now(f"{cls.background}{out_misc}{out}")
            skip = redraw = False

            if Key.input_wait(Timer.left()):
                key = Key.get()
                redraw = True
                has_sel = False
                if key == "mouse_click" and not inputting:
                    mx, my = Key.get_mouse()
                    if x < mx < x + w + w2 and y - 4 < my < y:
                        # if my == y - 2:
                        for cx, cat in enumerate(categories):
                            ccx = (
                                x
                                + (cat_width * cx)
                                + round(cat_width / 2 - len(cat) / 2)
                            )
                            if ccx - 2 < mx < ccx + 2 + len(cat):
                                key = str(cx + 1)
                                break
                    elif x < mx < x + w and y < my < y + h + 2:
                        mouse_sel = ceil((my - y) / 2) - 1 + ceil((page - 1) * (h / 2))
                        if pages and my == y + h + 1 and x + 11 < mx < x + 16:
                            key = "page_up"
                        elif pages and my == y + h + 1 and x + 19 < mx < x + 24:
                            key = "page_down"
                        elif my == y + h + 1:
                            pass
                        elif mouse_sel == selected_int:
                            if mx < x + 6:
                                key = "left"
                            elif mx > x + 19:
                                key = "right"
                            else:
                                key = "enter"
                        elif mouse_sel < len(option_items):
                            selected_int = mouse_sel
                            has_sel = True
                    else:
                        key = "escape"
                if inputting:
                    if key in ["escape", "mouse_click"]:
                        inputting = False
                    elif key == "enter":
                        inputting = False
                        if str(getattr(CONFIG, selected)) != input_val:
                            if selected == "update_ms":
                                if not input_val or int(input_val) < 100:
                                    CONFIG.update_ms = 100
                                elif int(input_val) > 86399900:
                                    CONFIG.update_ms = 86399900
                                else:
                                    CONFIG.update_ms = int(input_val)
                            elif selected == "proc_update_mult":
                                if not input_val or int(input_val) < 1:
                                    CONFIG.proc_update_mult = 1
                                else:
                                    CONFIG.proc_update_mult = int(input_val)
                                Collector.proc_counter = 1
                            elif selected == "tree_depth":
                                if not input_val or int(input_val) < 0:
                                    CONFIG.tree_depth = 0
                                else:
                                    CONFIG.tree_depth = int(input_val)
                                ProcCollector.collapsed = {}
                            elif selected == "shown_boxes":
                                new_boxes: List = []
                                for box in input_val.split():
                                    if box in ["cpu", "mem", "net", "proc"]:
                                        new_boxes.append(box)
                                CONFIG.shown_boxes = " ".join(new_boxes)
                                Box.view_mode = "user"
                                Box.view_modes["user"] = CONFIG.shown_boxes.split()
                                Draw.clear(saved=True)
                            elif isinstance(getattr(CONFIG, selected), str):
                                setattr(CONFIG, selected, input_val)
                                if selected.startswith("net_"):
                                    NetCollector.net_min = {
                                        "download": -1,
                                        "upload": -1,
                                    }
                                elif selected == "draw_clock":
                                    Box.clock_on = len(CONFIG.draw_clock) > 0
                                    if not Box.clock_on:
                                        Draw.clear("clock", saved=True)
                                elif selected == "io_graph_speeds":
                                    MemBox.graph_speeds = {}
                            Term.refresh(force=True)
                            cls.resized = False
                    elif key == "backspace" and len(input_val):
                        input_val = input_val[:-1]
                    elif key == "delete":
                        input_val = ""
                    elif isinstance(getattr(CONFIG, selected), str) and len(key) == 1:
                        input_val += key
                    elif isinstance(getattr(CONFIG, selected), int) and key.isdigit():
                        input_val += key
                elif key == "q":
                    clean_quit()
                elif key in ["escape", "o", "M", "f2"]:
                    cls.close = True
                    break
                elif key == "tab" or (
                    key == "down"
                    and selected_int == len(option_items) - 1
                    and (page == pages or pages == 0)
                ):
                    if cat_int == len(categories) - 1:
                        cat_int = 0
                    else:
                        cat_int += 1
                    change_cat = True
                elif key == "shift_tab" or (
                    key == "up" and selected_int == 0 and page == 1
                ):
                    if cat_int == 0:
                        cat_int = len(categories) - 1
                    else:
                        cat_int -= 1
                    change_cat = True
                    selected_int = -1 if key != "shift_tab" else 0
                elif key in list(map(str, range(1, len(cat_list) + 1))) and key != str(
                    cat_int + 1
                ):
                    cat_int = int(key) - 1
                    change_cat = True
                elif key == "enter" and selected in [
                    "update_ms",
                    "disks_filter",
                    "custom_cpu_name",
                    "net_download",
                    "net_upload",
                    "draw_clock",
                    "tree_depth",
                    "proc_update_mult",
                    "shown_boxes",
                    "net_iface",
                    "io_graph_speeds",
                ]:
                    inputting = True
                    input_val = str(getattr(CONFIG, selected))
                elif (
                    key == "left"
                    and selected == "update_ms"
                    and CONFIG.update_ms - 100 >= 100
                ):
                    CONFIG.update_ms -= 100
                    Box.draw_update_ms()
                elif (
                    key == "right"
                    and selected == "update_ms"
                    and CONFIG.update_ms + 100 <= 86399900
                ):
                    CONFIG.update_ms += 100
                    Box.draw_update_ms()
                elif (
                    key == "left"
                    and selected == "proc_update_mult"
                    and CONFIG.proc_update_mult > 1
                ):
                    CONFIG.proc_update_mult -= 1
                    Collector.proc_counter = 1
                elif key == "right" and selected == "proc_update_mult":
                    CONFIG.proc_update_mult += 1
                    Collector.proc_counter = 1
                elif (
                    key == "left" and selected == "tree_depth" and CONFIG.tree_depth > 0
                ):
                    CONFIG.tree_depth -= 1
                    ProcCollector.collapsed = {}
                elif key == "right" and selected == "tree_depth":
                    CONFIG.tree_depth += 1
                    ProcCollector.collapsed = {}
                elif key in ["left", "right"] and isinstance(
                    getattr(CONFIG, selected), bool
                ):
                    setattr(CONFIG, selected, not getattr(CONFIG, selected))
                    if selected == "check_temp":
                        if CONFIG.check_temp:
                            CpuCollector.get_sensors()
                        else:
                            CpuCollector.sensor_method = ""
                            CpuCollector.got_sensors = False
                    if selected in ["net_auto", "net_color_fixed", "net_sync"]:
                        if selected == "net_auto":
                            NetCollector.auto_min = CONFIG.net_auto
                        NetBox.redraw = True
                    if selected == "theme_background":
                        Term.bg = (
                            f"{THEME.main_bg}"
                            if CONFIG.theme_background
                            else "\033[49m"
                        )
                        Draw.now(Term.bg)
                    if selected == "show_battery":
                        Draw.clear("battery", saved=True)
                    Term.refresh(force=True)
                    cls.resized = False
                elif (
                    key in ["left", "right"]
                    and selected == "color_theme"
                    and len(Theme.themes) > 1
                ):
                    if key == "left":
                        color_i -= 1
                        if color_i < 0:
                            color_i = len(Theme.themes) - 1
                    elif key == "right":
                        color_i += 1
                        if color_i > len(Theme.themes) - 1:
                            color_i = 0
                    Collector.collect_idle.wait()
                    CONFIG.color_theme = list(Theme.themes)[color_i]
                    THEME(CONFIG.color_theme)
                    Term.refresh(force=True)
                    Timer.finish()
                elif key in ["left", "right"] and selected == "proc_sorting":
                    ProcCollector.sorting(key)
                elif key in ["left", "right"] and selected == "log_level":
                    if key == "left":
                        loglevel_i -= 1
                        if loglevel_i < 0:
                            loglevel_i = len(CONFIG.log_levels) - 1
                    elif key == "right":
                        loglevel_i += 1
                        if loglevel_i > len(CONFIG.log_levels) - 1:
                            loglevel_i = 0
                    CONFIG.log_level = CONFIG.log_levels[loglevel_i]
                    errlog.setLevel(getattr(logging, CONFIG.log_level))
                    errlog.info(f"Loglevel set to {CONFIG.log_level}")
                elif key in ["left", "right"] and selected in [
                    "cpu_graph_upper",
                    "cpu_graph_lower",
                ]:
                    if key == "left":
                        cpu_graph_i[selected] -= 1
                        if cpu_graph_i[selected] < 0:
                            cpu_graph_i[selected] = len(CONFIG.cpu_percent_fields) - 1
                    if key == "right":
                        cpu_graph_i[selected] += 1
                        if cpu_graph_i[selected] > len(CONFIG.cpu_percent_fields) - 1:
                            cpu_graph_i[selected] = 0
                    setattr(
                        CONFIG,
                        selected,
                        CONFIG.cpu_percent_fields[cpu_graph_i[selected]],
                    )
                    setattr(CpuCollector, selected.replace("_graph", ""), [])
                    Term.refresh(force=True)
                    cls.resized = False
                elif key in ["left", "right"] and selected == "temp_scale":
                    if key == "left":
                        temp_scale_i -= 1
                        if temp_scale_i < 0:
                            temp_scale_i = len(CONFIG.temp_scales) - 1
                    if key == "right":
                        temp_scale_i += 1
                        if temp_scale_i > len(CONFIG.temp_scales) - 1:
                            temp_scale_i = 0
                    CONFIG.temp_scale = CONFIG.temp_scales[temp_scale_i]
                    Term.refresh(force=True)
                    cls.resized = False
                elif (
                    key in ["left", "right"]
                    and selected == "cpu_sensor"
                    and len(CONFIG.cpu_sensors) > 1
                ):
                    if key == "left":
                        cpu_sensor_i -= 1
                        if cpu_sensor_i < 0:
                            cpu_sensor_i = len(CONFIG.cpu_sensors) - 1
                    elif key == "right":
                        cpu_sensor_i += 1
                        if cpu_sensor_i > len(CONFIG.cpu_sensors) - 1:
                            cpu_sensor_i = 0
                    Collector.collect_idle.wait()
                    CpuCollector.sensor_swap = True
                    CONFIG.cpu_sensor = CONFIG.cpu_sensors[cpu_sensor_i]
                    if CONFIG.check_temp and (
                        CpuCollector.sensor_method != "psutil"
                        or CONFIG.cpu_sensor == "Auto"
                    ):
                        CpuCollector.get_sensors()
                        Term.refresh(force=True)
                        cls.resized = False
                elif key in ["up", "mouse_scroll_up"]:
                    selected_int -= 1
                    if selected_int < 0:
                        selected_int = len(option_items) - 1
                    page = floor(selected_int * 2 / h) + 1
                elif key in ["down", "mouse_scroll_down"]:
                    selected_int += 1
                    if selected_int > len(option_items) - 1:
                        selected_int = 0
                    page = floor(selected_int * 2 / h) + 1
                elif key == "page_up":
                    if not pages or page == 1:
                        selected_int = 0
                    else:
                        page -= 1
                        if page < 1:
                            page = pages
                    selected_int = (page - 1) * ceil(h / 2)
                elif key == "page_down":
                    if not pages or page == pages:
                        selected_int = len(option_items) - 1
                    else:
                        page += 1
                        if page > pages:
                            page = 1
                        selected_int = (page - 1) * ceil(h / 2)
                elif has_sel:
                    pass
                else:
                    redraw = False

            if Timer.not_zero() and not cls.resized:
                skip = True
            else:
                Collector.collect()
                Collector.collect_done.wait(2)
                if CONFIG.background_update:
                    cls.background = (
                        f"{THEME.inactive_fg}"
                        + Fx.uncolor(f"{Draw.saved_buffer()}")
                        + f"{Term.fg}"
                    )
                Timer.stamp()

        if main_active:
            cls.close = False
            return
        Draw.now(f"{Draw.saved_buffer()}")
        cls.background = ""
        cls.active = False
        cls.close = False
