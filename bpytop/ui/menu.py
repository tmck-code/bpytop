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
