class Banner:
    """Holds the bpytop banner, .draw(line, [col=0], [center=False], [now=False])"""

    out: List[str] = []
    c_color: str = ""
    length: int = 0
    if not out:
        for num, (color, color2, line) in enumerate(BANNER_SRC):
            if len(line) > length:
                length = len(line)
            out_var = ""
            line_color = Color.fg(color)
            line_color2 = Color.fg(color2)
            line_dark = Color.fg(f"#{80 - num * 6}")
            for n, letter in enumerate(line):
                if letter == "█" and c_color != line_color:
                    if 5 < n < 25:
                        c_color = line_color2
                    else:
                        c_color = line_color
                    out_var += c_color
                elif letter == " ":
                    letter = f"{Mv.r(1)}"
                    c_color = ""
                elif letter != "█" and c_color != line_dark:
                    c_color = line_dark
                    out_var += line_dark
                out_var += letter
            out.append(out_var)

    @classmethod
    def draw(cls, line: int, col: int = 0, center: bool = False, now: bool = False):
        out: str = ""
        if center:
            col = Term.width // 2 - cls.length // 2
        for n, o in enumerate(cls.out):
            out += f"{Mv.to(line + n, col)}{o}"
        out += f"{Term.fg}"
        if now:
            Draw.out(out)
        else:
            return out