from typing import Tuple, Iterable
import logging

errlog = logging.getLogger("ErrorLogger")


class Color:
    """Holds representations for a 24-bit color value
    __init__(color, depth="fg", default=False)
    -- color accepts 6 digit hexadecimal: string "#RRGGBB", 2 digit hexadecimal: string "#FF" or decimal RGB "255 255 255" as a string.
    -- depth accepts "fg" or "bg"
    __call__(*args) joins str arguments to a string and apply color
    __str__ returns escape sequence to set color
    __iter__ returns iteration over red, green and blue in integer values of 0-255.
    * Values:  .hexa: str  |  .dec: Tuple[int, int, int]  |  .red: int  |  .green: int  |  .blue: int  |  .depth: str  |  .escape: str
    """

    hexa: str
    dec: Tuple[int, int, int]
    red: int
    green: int
    blue: int
    depth: str
    escape: str
    default: bool

    def __init__(
        self,
        color: str,
        depth: str = "fg",
        default: bool = False,
        true_color: bool = True,
        low_color: bool = False,
    ):
        self.depth = depth
        self.default = default
        self.true_color = true_color
        self.low_color = low_color
        try:
            if not color:
                self.dec = (-1, -1, -1)
                self.hexa = ""
                self.red = self.green = self.blue = -1
                self.escape = "\033[49m" if depth == "bg" and default else ""
                return

            elif color.startswith("#"):
                self.hexa = color
                if len(self.hexa) == 3:
                    self.hexa += self.hexa[1:3] + self.hexa[1:3]
                    c = int(self.hexa[1:3], base=16)
                    self.dec = (c, c, c)
                elif len(self.hexa) == 7:
                    self.dec = (
                        int(self.hexa[1:3], base=16),
                        int(self.hexa[3:5], base=16),
                        int(self.hexa[5:7], base=16),
                    )
                else:
                    raise ValueError(
                        f"Incorrectly formatted hexadecimal rgb string: {self.hexa}"
                    )

            else:
                c_t = tuple(map(int, color.split(" ")))
                if len(c_t) == 3:
                    self.dec = c_t  # type: ignore
                else:
                    raise ValueError(f'RGB dec should be "0-255 0-255 0-255"')

            if not all(0 <= c <= 255 for c in self.dec):
                raise ValueError(f"One or more RGB values are out of range: {color}")

        except Exception as e:
            errlog.exception(str(e))
            self.escape = ""
            return

        if self.dec and not self.hexa:
            self.hexa = f'{hex(self.dec[0]).lstrip("0x").zfill(2)}{hex(self.dec[1]).lstrip("0x").zfill(2)}{hex(self.dec[2]).lstrip("0x").zfill(2)}'

        if self.dec and self.hexa:
            self.red, self.green, self.blue = self.dec
            self.escape = f'\033[{38 if self.depth == "fg" else 48};2;{";".join(str(c) for c in self.dec)}m'

        if not self.true_color or self.low_color:
            self.escape = f"{self.true_color_to_256(rgb=self.dec, depth=self.depth)}"

    def __str__(self) -> str:
        return self.escape

    def __repr__(self) -> str:
        return repr(self.escape)

    def __iter__(self) -> Iterable:
        for c in self.dec:
            yield c

    def __call__(self, *args: str) -> str:
        if len(args) < 1:
            return ""
        return f'{self.escape}{"".join(args)}{getattr(Term, self.depth)}'

    @staticmethod
    def true_color_to_256(rgb: Tuple[int, int, int], depth: str = "fg") -> str:
        out: str = ""
        pre: str = f'\033[{"38" if depth == "fg" else "48"};5;'

        greyscale: Tuple[int, int, int] = (rgb[0] // 11, rgb[1] // 11, rgb[2] // 11)
        if greyscale[0] == greyscale[1] == greyscale[2]:
            out = f"{pre}{232 + greyscale[0]}m"
        else:
            out = f"{pre}{round(rgb[0] / 51) * 36 + round(rgb[1] / 51) * 6 + round(rgb[2] / 51) + 16}m"

        return out

    @staticmethod
    def escape_color(
        hexa: str = "",
        r: int = 0,
        g: int = 0,
        b: int = 0,
        depth: str = "fg",
        true_color: bool = True,
        low_color: bool = False,
    ) -> str:
        """Returns escape sequence to set color
        * accepts either 6 digit hexadecimal hexa="#RRGGBB", 2 digit hexadecimal: hexa="#FF"
        * or decimal RGB: r=0-255, g=0-255, b=0-255
        * depth="fg" or "bg"
        """
        dint: int = 38 if depth == "fg" else 48
        color: str = ""
        if hexa:
            try:
                if len(hexa) == 3:
                    c = int(hexa[1:], base=16)
                    if true_color and not low_color:
                        color = f"\033[{dint};2;{c};{c};{c}m"
                    else:
                        color = f"{Color.true_color_to_256(rgb=(c, c, c), depth=depth)}"
                elif len(hexa) == 7:
                    if true_color and not low_color:
                        color = f"\033[{dint};2;{int(hexa[1:3], base=16)};{int(hexa[3:5], base=16)};{int(hexa[5:7], base=16)}m"
                    else:
                        color = f"{Color.true_color_to_256(rgb=(int(hexa[1:3], base=16), int(hexa[3:5], base=16), int(hexa[5:7], base=16)), depth=depth)}"
            except ValueError as e:
                errlog.exception(f"{e}")
        else:
            if true_color and not low_color:
                color = f"\033[{dint};2;{r};{g};{b}m"
            else:
                color = f"{Color.true_color_to_256(rgb=(r, g, b), depth=depth)}"
        return color

    @classmethod
    def fg(cls, *args) -> str:
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="fg")
        else:
            return cls.escape_color(hexa=args[0], depth="fg")

    @classmethod
    def bg(cls, *args) -> str:
        if len(args) > 2:
            return cls.escape_color(r=args[0], g=args[1], b=args[2], depth="bg")
        else:
            return cls.escape_color(hexa=args[0], depth="bg")
