from typing import List, Dict, Union
import psutil
import os, logging
from string import Template

from util import platform

errlog = logging.getLogger("ErrorLogger")

class Config:
    """Holds all config variables and functions for loading from and saving to disk"""

    keys: List[str] = [
        "color_theme",
        "update_ms",
        "proc_sorting",
        "proc_reversed",
        "proc_tree",
        "check_temp",
        "draw_clock",
        "background_update",
        "custom_cpu_name",
        "proc_colors",
        "proc_gradient",
        "proc_per_core",
        "proc_mem_bytes",
        "disks_filter",
        "update_check",
        "log_level",
        "mem_graphs",
        "show_swap",
        "swap_disk",
        "show_disks",
        "use_fstab",
        "net_download",
        "net_upload",
        "net_auto",
        "net_color_fixed",
        "show_init",
        "theme_background",
        "net_sync",
        "show_battery",
        "tree_depth",
        "cpu_sensor",
        "show_coretemp",
        "proc_update_mult",
        "shown_boxes",
        "net_iface",
        "only_physical",
        "truecolor",
        "io_mode",
        "io_graph_combined",
        "io_graph_speeds",
        "show_io_stat",
        "cpu_graph_upper",
        "cpu_graph_lower",
        "cpu_invert_lower",
        "cpu_single_graph",
        "show_uptime",
        "temp_scale",
        "show_cpu_freq",
    ]
    conf_dict: Dict[str, Union[str, int, bool]] = {}
    color_theme: str = "default"
    theme_background: bool = True
    truecolor: bool = True
    shown_boxes: str = "cpu mem net proc"
    update_ms: int = 2000
    proc_update_mult: int = 2
    proc_sorting: str = "cpu lazy"
    proc_reversed: bool = False
    proc_tree: bool = False
    tree_depth: int = 3
    proc_colors: bool = True
    proc_gradient: bool = True
    proc_per_core: bool = False
    proc_mem_bytes: bool = True
    cpu_graph_upper: str = "total"
    cpu_graph_lower: str = "total"
    cpu_invert_lower: bool = True
    cpu_single_graph: bool = False
    show_uptime: bool = True
    check_temp: bool = True
    cpu_sensor: str = "Auto"
    show_coretemp: bool = True
    temp_scale: str = "celsius"
    show_cpu_freq: bool = True
    draw_clock: str = "%X"
    background_update: bool = True
    custom_cpu_name: str = ""
    disks_filter: str = ""
    update_check: bool = True
    mem_graphs: bool = True
    show_swap: bool = True
    swap_disk: bool = True
    show_disks: bool = True
    only_physical: bool = True
    use_fstab: bool = False
    show_io_stat: bool = True
    io_mode: bool = False
    io_graph_combined: bool = False
    io_graph_speeds: str = ""
    net_download: str = "10M"
    net_upload: str = "10M"
    net_color_fixed: bool = False
    net_auto: bool = True
    net_sync: bool = False
    net_iface: str = ""
    show_battery: bool = True
    show_init: bool = False
    log_level: str = "WARNING"

    warnings: List[str] = []
    info: List[str] = []

    sorting_options: List[str] = [
        "pid",
        "program",
        "arguments",
        "threads",
        "user",
        "memory",
        "cpu lazy",
        "cpu responsive",
    ]
    log_levels: List[str] = ["ERROR", "WARNING", "INFO", "DEBUG"]
    cpu_percent_fields: List = ["total"]
    cpu_percent_fields.extend(getattr(psutil.cpu_times_percent(), "_fields", []))
    temp_scales: List[str] = ["celsius", "fahrenheit", "kelvin", "rankine"]

    cpu_sensors: List[str] = ["Auto"]

    if hasattr(psutil, "sensors_temperatures"):
        try:
            _temps = psutil.sensors_temperatures()
            if _temps:
                for _name, _entries in _temps.items():
                    for _num, _entry in enumerate(_entries, 1):
                        if hasattr(_entry, "current"):
                            cpu_sensors.append(
                                f'{_name}:{_num if _entry.label == "" else _entry.label}'
                            )
        except:
            pass

    changed: bool = False
    recreate: bool = False
    config_file: str = ""

    _initialized: bool = False

    def __init__(self, path: str, version: str):
        self.config_file = path
        conf: Dict[str, Union[str, int, bool]] = self.load_config()
        if not "version" in conf.keys():
            self.recreate = True
            self.info.append(
                f"Config file malformatted or missing, will be recreated on exit!"
            )
        elif conf["version"] != version:
            self.recreate = True
            self.info.append(
                f"Config file version and bpytop version missmatch, will be recreated on exit!"
            )
        for key in self.keys:
            if key in conf.keys() and conf[key] != "_error_":
                setattr(self, key, conf[key])
            else:
                self.recreate = True
                self.conf_dict[key] = getattr(self, key)
        self._initialized = True

    def __setattr__(self, name, value):
        if self._initialized:
            object.__setattr__(self, "changed", True)
        object.__setattr__(self, name, value)
        if name not in ["_initialized", "recreate", "changed"]:
            self.conf_dict[name] = value

    def load_config(self) -> Dict[str, Union[str, int, bool]]:
        """Load config from file, set correct types for values and return a dict"""
        new_config: Dict[str, Union[str, int, bool]] = {}
        conf_file: str = ""
        if os.path.isfile(self.config_file):
            conf_file = self.config_file
        elif platform.detect() == "BSD" and os.path.isfile("/usr/local/etc/bpytop.conf"):
            conf_file = "/usr/local/etc/bpytop.conf"
        elif platform.detect() != "BSD" and os.path.isfile("/etc/bpytop.conf"):
            conf_file = "/etc/bpytop.conf"
        else:
            return new_config
        try:
            with open(conf_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#? Config"):
                        new_config["version"] = line[line.find("v. ") + 3 :]
                        continue
                    if not "=" in line:
                        continue
                    key, line = line.split("=", maxsplit=1)
                    if not key in self.keys:
                        continue
                    line = line.strip('"')
                    if type(getattr(self, key)) == int:
                        try:
                            new_config[key] = int(line)
                        except ValueError:
                            self.warnings.append(
                                f'Config key "{key}" should be an integer!'
                            )
                    if type(getattr(self, key)) == bool:
                        try:
                            new_config[key] = bool(strtobool(line))
                        except ValueError:
                            self.warnings.append(
                                f'Config key "{key}" can only be True or False!'
                            )
                    if type(getattr(self, key)) == str:
                        new_config[key] = str(line)
        except Exception as e:
            errlog.exception(str(e))
        if (
            "proc_sorting" in new_config
            and not new_config["proc_sorting"] in self.sorting_options
        ):
            new_config["proc_sorting"] = "_error_"
            self.warnings.append(
                f'Config key "proc_sorted" didn\'t get an acceptable value!'
            )
        if "log_level" in new_config and not new_config["log_level"] in self.log_levels:
            new_config["log_level"] = "_error_"
            self.warnings.append(
                f'Config key "log_level" didn\'t get an acceptable value!'
            )
        if "update_ms" in new_config and int(new_config["update_ms"]) < 100:
            new_config["update_ms"] = 100
            self.warnings.append(f'Config key "update_ms" can\'t be lower than 100!')
        for net_name in ["net_download", "net_upload"]:
            if net_name in new_config and not new_config[net_name][0].isdigit():  # type: ignore
                new_config[net_name] = "_error_"
        if (
            "cpu_sensor" in new_config
            and not new_config["cpu_sensor"] in self.cpu_sensors
        ):
            new_config["cpu_sensor"] = "_error_"
            self.warnings.append(
                f'Config key "cpu_sensor" does not contain an available sensor!'
            )
        if "shown_boxes" in new_config and not new_config["shown_boxes"] == "":
            for box in new_config["shown_boxes"].split():  # type: ignore
                if not box in ["cpu", "mem", "net", "proc"]:
                    new_config["shown_boxes"] = "_error_"
                    self.warnings.append(
                        f'Config key "shown_boxes" contains invalid box names!'
                    )
                    break
        for cpu_graph in ["cpu_graph_upper", "cpu_graph_lower"]:
            if (
                cpu_graph in new_config
                and not new_config[cpu_graph] in self.cpu_percent_fields
            ):
                new_config[cpu_graph] = "_error_"
                self.warnings.append(
                    f'Config key "{cpu_graph}" does not contain an available cpu stat attribute!'
                )
        if (
            "temp_scale" in new_config
            and not new_config["temp_scale"] in self.temp_scales
        ):
            new_config["temp_scale"] = "_error_"
            self.warnings.append(
                f'Config key "temp_scale" does not contain a recognized temperature scale!'
            )
        return new_config

    # *?This is the template used to create the config file
    @property
    def default_conf(self) -> Template:
        with open("configs/bpytop.conf") as istream:
            return Template(
                f"#? Config file for bpytop v. {self.version}" + istream.read()
        )


    def save_config(self):
        """Save current config to config file if difference in values or version, creates a new file if not found"""
        if not self.changed and not self.recreate:
            return
        try:
            with open(
                self.config_file, "w" if os.path.isfile(self.config_file) else "x"
            ) as f:
                f.write(self.default_conf.substitute(self.conf_dict))
        except Exception as e:
            errlog.exception(str(e))
