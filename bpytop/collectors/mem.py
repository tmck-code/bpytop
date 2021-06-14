from typing import List, Dict, Tuple
from time import time

import psutil

from bpytop.collectors.collector import Collector

class MemCollector(Collector):
    """Collects memory and disks information"""

    values: Dict[str, int] = {}
    vlist: Dict[str, List[int]] = {}
    percent: Dict[str, int] = {}
    string: Dict[str, str] = {}

    swap_values: Dict[str, int] = {}
    swap_vlist: Dict[str, List[int]] = {}
    swap_percent: Dict[str, int] = {}
    swap_string: Dict[str, str] = {}

    disks: Dict[str, Dict]
    disk_hist: Dict[str, Tuple] = {}
    timestamp: float = time()
    disks_io_dict: Dict[str, Dict[str, List[int]]] = {}
    recheck_diskutil: bool = True
    diskutil_map: Dict[str, str] = {}

    io_error: bool = False

    old_disks: List[str] = []
    old_io_disks: List[str] = []

    fstab_filter: List[str] = []

    excludes: List[str] = ["squashfs", "nullfs"]
    if SYSTEM == "BSD":
        excludes += ["devfs", "tmpfs", "procfs", "linprocfs", "gvfs", "fusefs"]

    buffer: str = MemBox.buffer

    @classmethod
    def _collect(cls):
        # * Collect memory
        mem = psutil.virtual_memory()
        if hasattr(mem, "cached"):
            cls.values["cached"] = mem.cached
        else:
            cls.values["cached"] = mem.active
        cls.values["total"], cls.values["free"], cls.values["available"] = (
            mem.total,
            mem.free,
            mem.available,
        )
        cls.values["used"] = cls.values["total"] - cls.values["available"]

        for key, value in cls.values.items():
            cls.string[key] = floating_humanizer(value)
            if key == "total":
                continue
            cls.percent[key] = round(value * 100 / cls.values["total"])
            if CONFIG.mem_graphs:
                if not key in cls.vlist:
                    cls.vlist[key] = []
                cls.vlist[key].append(cls.percent[key])
                if len(cls.vlist[key]) > MemBox.width:
                    del cls.vlist[key][0]

        # * Collect swap
        if CONFIG.show_swap or CONFIG.swap_disk:
            swap = psutil.swap_memory()
            cls.swap_values["total"], cls.swap_values["free"] = swap.total, swap.free
            cls.swap_values["used"] = cls.swap_values["total"] - cls.swap_values["free"]

            if swap.total:
                if not MemBox.swap_on:
                    MemBox.redraw = True
                MemBox.swap_on = True
                for key, value in cls.swap_values.items():
                    cls.swap_string[key] = floating_humanizer(value)
                    if key == "total":
                        continue
                    cls.swap_percent[key] = round(
                        value * 100 / cls.swap_values["total"]
                    )
                    if CONFIG.mem_graphs:
                        if not key in cls.swap_vlist:
                            cls.swap_vlist[key] = []
                        cls.swap_vlist[key].append(cls.swap_percent[key])
                        if len(cls.swap_vlist[key]) > MemBox.width:
                            del cls.swap_vlist[key][0]
            else:
                if MemBox.swap_on:
                    MemBox.redraw = True
                MemBox.swap_on = False
        else:
            if MemBox.swap_on:
                MemBox.redraw = True
            MemBox.swap_on = False

        if not CONFIG.show_disks:
            return
        # * Collect disks usage
        disk_read: int = 0
        disk_write: int = 0
        dev_name: str
        disk_name: str
        filtering: Tuple = ()
        filter_exclude: bool = False
        io_string_r: str
        io_string_w: str
        u_percent: int
        cls.disks = {}

        if CONFIG.disks_filter:
            if CONFIG.disks_filter.startswith("exclude="):
                filter_exclude = True
                filtering = tuple(
                    v.strip()
                    for v in CONFIG.disks_filter.replace("exclude=", "")
                    .strip()
                    .split(",")
                )
            else:
                filtering = tuple(
                    v.strip() for v in CONFIG.disks_filter.strip().split(",")
                )
        try:
            io_counters = psutil.disk_io_counters(perdisk=SYSTEM != "BSD", nowrap=True)
        except ValueError as e:
            if not cls.io_error:
                cls.io_error = True
                errlog.error(f"Non fatal error during disk io collection!")
                if psutil.version_info[0] < 5 or (
                    psutil.version_info[0] == 5 and psutil.version_info[1] < 7
                ):
                    errlog.error(f"Caused by outdated psutil version.")
                errlog.exception(f"{e}")
            io_counters = None

        if SYSTEM == "MacOS" and cls.recheck_diskutil:
            cls.recheck_diskutil = False
            try:
                dutil_out = subprocess.check_output(
                    ["diskutil", "list", "physical"], universal_newlines=True
                )
                for line in dutil_out.split("\n"):
                    line = line.replace("\u2068", "").replace("\u2069", "")
                    if line.startswith("/dev/"):
                        xdisk = line.split()[0].replace("/dev/", "")
                    elif "Container" in line:
                        ydisk = line.split()[3]
                        if xdisk and ydisk:
                            cls.diskutil_map[xdisk] = ydisk
                            xdisk = ydisk = ""
            except:
                pass

        if CONFIG.use_fstab and SYSTEM != "MacOS" and not cls.fstab_filter:
            try:
                with open("/etc/fstab", "r") as fstab:
                    for line in fstab:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            mount_data = line.split()
                            if mount_data[2].lower() != "swap":
                                cls.fstab_filter += [mount_data[1]]
                errlog.debug(f"new fstab_filter set : {cls.fstab_filter}")
            except IOError:
                CONFIG.use_fstab = False
                errlog.warning(
                    f"Error reading fstab, use_fstab flag reset to {CONFIG.use_fstab}"
                )
        if not CONFIG.use_fstab and cls.fstab_filter:
            cls.fstab_filter = []
            errlog.debug(
                f"use_fstab flag has been turned to {CONFIG.use_fstab}, fstab_filter cleared"
            )

        for disk in psutil.disk_partitions(
            all=CONFIG.use_fstab or not CONFIG.only_physical
        ):
            disk_io = None
            io_string_r = io_string_w = ""
            if CONFIG.use_fstab and disk.mountpoint not in cls.fstab_filter:
                continue
            disk_name = (
                disk.mountpoint.rsplit("/", 1)[-1]
                if not disk.mountpoint == "/"
                else "root"
            )
            if cls.excludes and disk.fstype in cls.excludes:
                continue
            if filtering and (
                (not filter_exclude and not disk.mountpoint in filtering)
                or (filter_exclude and disk.mountpoint in filtering)
            ):
                continue
            if SYSTEM == "MacOS" and disk.mountpoint == "/private/var/vm":
                continue
            try:
                disk_u = psutil.disk_usage(disk.mountpoint)
            except:
                pass

            u_percent = round(getattr(disk_u, "percent", 0))
            cls.disks[disk.device] = {
                "name": disk_name,
                "used_percent": u_percent,
                "free_percent": 100 - u_percent,
            }
            for name in ["total", "used", "free"]:
                cls.disks[disk.device][name] = floating_humanizer(
                    getattr(disk_u, name, 0)
                )

            # * Collect disk io
            if io_counters:
                try:
                    if SYSTEM != "BSD":
                        dev_name = os.path.realpath(disk.device).rsplit("/", 1)[-1]
                        if not dev_name in io_counters:
                            for names in io_counters:
                                if names in dev_name:
                                    disk_io = io_counters[names]
                                    break
                            else:
                                if cls.diskutil_map:
                                    for names, items in cls.diskutil_map.items():
                                        if items in dev_name and names in io_counters:
                                            disk_io = io_counters[names]
                        else:
                            disk_io = io_counters[dev_name]
                    elif disk.mountpoint == "/":
                        disk_io = io_counters
                    else:
                        raise Exception
                    disk_read = round((disk_io.read_bytes - cls.disk_hist[disk.device][0]) / (time() - cls.timestamp))  # type: ignore
                    disk_write = round((disk_io.write_bytes - cls.disk_hist[disk.device][1]) / (time() - cls.timestamp))  # type: ignore
                    if not disk.device in cls.disks_io_dict:
                        cls.disks_io_dict[disk.device] = {
                            "read": [],
                            "write": [],
                            "rw": [],
                        }
                    cls.disks_io_dict[disk.device]["read"].append(disk_read >> 20)
                    cls.disks_io_dict[disk.device]["write"].append(disk_write >> 20)
                    cls.disks_io_dict[disk.device]["rw"].append(
                        (disk_read + disk_write) >> 20
                    )

                    if len(cls.disks_io_dict[disk.device]["read"]) > MemBox.width:
                        del (
                            cls.disks_io_dict[disk.device]["read"][0],
                            cls.disks_io_dict[disk.device]["write"][0],
                            cls.disks_io_dict[disk.device]["rw"][0],
                        )

                except:
                    disk_read = disk_write = 0
            else:
                disk_read = disk_write = 0

            if disk_io:
                cls.disk_hist[disk.device] = (disk_io.read_bytes, disk_io.write_bytes)
                if CONFIG.io_mode or MemBox.disks_width > 30:
                    if disk_read > 0:
                        io_string_r = f"▲{floating_humanizer(disk_read, short=True)}"
                    if disk_write > 0:
                        io_string_w = f"▼{floating_humanizer(disk_write, short=True)}"
                    if CONFIG.io_mode:
                        cls.disks[disk.device]["io_r"] = io_string_r
                        cls.disks[disk.device]["io_w"] = io_string_w
                elif disk_read + disk_write > 0:
                    io_string_r += (
                        f"▼▲{floating_humanizer(disk_read + disk_write, short=True)}"
                    )

            cls.disks[disk.device]["io"] = (
                io_string_r + (" " if io_string_w and io_string_r else "") + io_string_w
            )

        if CONFIG.swap_disk and MemBox.swap_on:
            cls.disks["__swap"] = {
                "name": "swap",
                "used_percent": cls.swap_percent["used"],
                "free_percent": cls.swap_percent["free"],
                "io": "",
            }
            for name in ["total", "used", "free"]:
                cls.disks["__swap"][name] = cls.swap_string[name]
            if len(cls.disks) > 2:
                try:
                    new = {list(cls.disks)[0]: cls.disks.pop(list(cls.disks)[0])}
                    new["__swap"] = cls.disks.pop("__swap")
                    new.update(cls.disks)
                    cls.disks = new
                except:
                    pass

        if cls.old_disks != list(cls.disks) or cls.old_io_disks != list(
            cls.disks_io_dict
        ):
            MemBox.redraw = True
            cls.recheck_diskutil = True
            cls.old_disks = list(cls.disks)
            cls.old_io_disks = list(cls.disks_io_dict)

        cls.timestamp = time()

    @classmethod
    def _draw(cls):
        MemBox._draw_fg()
