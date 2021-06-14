from typing import Union, Tuple, Dict

def floating_humanizer(
    value: Union[float, int],
    bit: bool = False,
    per_second: bool = False,
    start: int = 0,
    short: bool = False,
) -> str:
    """Scales up in steps of 1024 to highest possible unit and returns string with unit suffixed
    * bit=True or defaults to bytes
    * start=int to set 1024 multiplier starting unit
    * short=True always returns 0 decimals and shortens unit to 1 character
    """
    out: str = ""
    mult: int = 8 if bit else 1
    selector: int = start
    unit: Tuple[str, ...] = UNITS["bit"] if bit else UNITS["byte"]

    if isinstance(value, float):
        value = round(value * 100 * mult)
    elif value > 0:
        value *= 100 * mult
    else:
        value = 0

    while len(f"{value}") > 5 and value >= 102400:
        value >>= 10
        if value < 100:
            out = f"{value}"
            break
        selector += 1
    else:
        if len(f"{value}") == 4 and selector > 0:
            out = f"{value}"[:-2] + "." + f"{value}"[-2]
        elif len(f"{value}") == 3 and selector > 0:
            out = f"{value}"[:-2] + "." + f"{value}"[-2:]
        elif len(f"{value}") >= 2:
            out = f"{value}"[:-2]
        else:
            out = f"{value}"

    if short:
        if "." in out:
            out = f"{round(float(out))}"
        if len(out) > 3:
            out = f"{int(out[0]) + 1}"
            selector += 1
    out += f'{"" if short else " "}{unit[selector][0] if short else unit[selector]}'
    if per_second:
        out += "ps" if bit else "/s"

    return out


def units_to_bytes(value: str) -> int:
    if not value:
        return 0
    out: int = 0
    mult: int = 0
    bit: bool = False
    value_i: int = 0
    units: Dict[str, int] = {"k": 1, "m": 2, "g": 3}
    try:
        if value.lower().endswith("s"):
            value = value[:-1]
        if value.lower().endswith("bit"):
            bit = True
            value = value[:-3]
        elif value.lower().endswith("byte"):
            value = value[:-4]

        if value[-1].lower() in units:
            mult = units[value[-1].lower()]
            value = value[:-1]

        if "." in value and value.replace(".", "").isdigit():
            if mult > 0:
                value_i = round(float(value) * 1024)
                mult -= 1
            else:
                value_i = round(float(value))
        elif value.isdigit():
            value_i = int(value)

        out = int(value_i) << (10 * mult)
        if bit:
            out = round(out / 8)
    except ValueError:
        out = 0
    return out


def min_max(value: int, min_value: int = 0, max_value: int = 100) -> int:
    return max(min_value, min(value, max_value))
