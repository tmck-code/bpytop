from typing import Dict

class Symbol:
    h_line: str = "─"
    v_line: str = "│"
    left_up: str = "┌"
    right_up: str = "┐"
    left_down: str = "└"
    right_down: str = "┘"
    title_left: str = "┤"
    title_right: str = "├"
    div_up: str = "┬"
    div_down: str = "┴"
    graph_up: Dict[float, str] = {
        0.0: " ",
        0.1: "⢀",
        0.2: "⢠",
        0.3: "⢰",
        0.4: "⢸",
        1.0: "⡀",
        1.1: "⣀",
        1.2: "⣠",
        1.3: "⣰",
        1.4: "⣸",
        2.0: "⡄",
        2.1: "⣄",
        2.2: "⣤",
        2.3: "⣴",
        2.4: "⣼",
        3.0: "⡆",
        3.1: "⣆",
        3.2: "⣦",
        3.3: "⣶",
        3.4: "⣾",
        4.0: "⡇",
        4.1: "⣇",
        4.2: "⣧",
        4.3: "⣷",
        4.4: "⣿",
    }
    graph_up_small = graph_up.copy()
    graph_up_small[0.0] = "\033[1C"

    graph_down: Dict[float, str] = {
        0.0: " ",
        0.1: "⠈",
        0.2: "⠘",
        0.3: "⠸",
        0.4: "⢸",
        1.0: "⠁",
        1.1: "⠉",
        1.2: "⠙",
        1.3: "⠹",
        1.4: "⢹",
        2.0: "⠃",
        2.1: "⠋",
        2.2: "⠛",
        2.3: "⠻",
        2.4: "⢻",
        3.0: "⠇",
        3.1: "⠏",
        3.2: "⠟",
        3.3: "⠿",
        3.4: "⢿",
        4.0: "⡇",
        4.1: "⡏",
        4.2: "⡟",
        4.3: "⡿",
        4.4: "⣿",
    }
    graph_down_small = graph_down.copy()
    graph_down_small[0.0] = "\033[1C"
    meter: str = "■"
    up: str = "↑"
    down: str = "↓"
    left: str = "←"
    right: str = "→"
    enter: str = "↲"
    ok: str = f'{Color.fg("#30ff50")}√{Color.fg("#cc")}'
    fail: str = f'{Color.fg("#ff3050")}!{Color.fg("#cc")}'
