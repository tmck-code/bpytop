from typing import List, Dict, Any
from time import time

import psutil

from bpytop.collectors.collector import Collector
from bpytop.util import fmt

class NetCollector(Collector):
    """Collects network stats"""

    buffer: str = NetBox.buffer
    nics: List[str] = []
    nic_i: int = 0
    nic: str = ""
    new_nic: str = ""
    nic_error: bool = False
    reset: bool = False
    graph_raise: Dict[str, int] = {"download": 5, "upload": 5}
    graph_lower: Dict[str, int] = {"download": 5, "upload": 5}
    # min_top: int = 10<<10
    # * Stats structure = stats[netword device][download, upload][total, last, top, graph_top, offset, speed, redraw, graph_raise, graph_low] = int, List[int], bool
    stats: Dict[str, Dict[str, Dict[str, Any]]] = {}
    # * Strings structure strings[network device][download, upload][total, byte_ps, bit_ps, top, graph_top] = str
    strings: Dict[str, Dict[str, Dict[str, str]]] = {}
    switched: bool = False
    timestamp: float = time()
    net_min: Dict[str, int] = {"download": -1, "upload": -1}
    auto_min: bool = CONFIG.net_auto
    net_iface: str = CONFIG.net_iface
    sync_top: int = 0
    sync_string: str = ""
    address: str = ""

    @classmethod
    def _get_nics(cls):
        """Get a list of all network devices sorted by highest throughput"""
        cls.nic_i = 0
        cls.nics = []
        cls.nic = ""
        try:
            io_all = psutil.net_io_counters(pernic=True)
        except Exception as e:
            if not cls.nic_error:
                cls.nic_error = True
                errlog.exception(f"{e}")
        if not io_all:
            return
        up_stat = psutil.net_if_stats()
        for nic in sorted(
            io_all.keys(),
            key=lambda nic: (
                getattr(io_all[nic], "bytes_recv", 0)
                + getattr(io_all[nic], "bytes_sent", 0)
            ),
            reverse=True,
        ):
            if nic not in up_stat or not up_stat[nic].isup:
                continue
            cls.nics.append(nic)
        if not cls.nics:
            cls.nics = [""]
        cls.nic = cls.nics[cls.nic_i]
        if cls.net_iface and cls.net_iface in cls.nics:
            cls.nic = cls.net_iface
            cls.nic_i = cls.nics.index(cls.nic)

    @classmethod
    def switch(cls, key: str):
        if cls.net_iface:
            cls.net_iface = ""
        if len(cls.nics) < 2 and cls.nic in cls.nics:
            return

        if cls.nic_i == -1:
            cls.nic_i = 0 if key == "n" else -1
        else:
            cls.nic_i += +1 if key == "n" else -1

        cls.nic_i %= len(cls.nics)
        cls.new_nic = cls.nics[cls.nic_i]
        cls.switched = True
        Collector.collect(NetCollector, redraw=True)

    @classmethod
    def _collect(cls):
        speed: int
        stat: Dict
        up_stat = psutil.net_if_stats()

        if sorted(cls.nics) != sorted(nic for nic in up_stat if up_stat[nic].isup):
            old_nic = cls.nic
            cls._get_nics()
            cls.nic = old_nic
            if cls.nic not in cls.nics:
                cls.nic_i = -1
            else:
                cls.nic_i = cls.nics.index(cls.nic)

        if cls.switched:
            cls.nic = cls.new_nic
            cls.switched = False

        if not cls.nic or cls.nic not in up_stat:
            cls._get_nics()
            if not cls.nic:
                return
            NetBox.redraw = True
        try:
            io_all = psutil.net_io_counters(pernic=True)[cls.nic]
        except KeyError:
            pass
            return
        if not cls.nic in cls.stats:
            cls.stats[cls.nic] = {}
            cls.strings[cls.nic] = {"download": {}, "upload": {}}
            for direction, value in ["download", io_all.bytes_recv], [
                "upload",
                io_all.bytes_sent,
            ]:
                cls.stats[cls.nic][direction] = {
                    "total": value,
                    "last": value,
                    "top": 0,
                    "graph_top": 0,
                    "offset": 0,
                    "speed": [],
                    "redraw": True,
                    "graph_raise": 0,
                    "graph_lower": 7,
                }
                for v in ["total", "byte_ps", "bit_ps", "top", "graph_top"]:
                    cls.strings[cls.nic][direction][v] = ""

        cls.stats[cls.nic]["download"]["total"] = io_all.bytes_recv
        cls.stats[cls.nic]["upload"]["total"] = io_all.bytes_sent
        if cls.nic in psutil.net_if_addrs():
            cls.address = getattr(psutil.net_if_addrs()[cls.nic][0], "address", "")

        for direction in ["download", "upload"]:
            stat = cls.stats[cls.nic][direction]
            strings = cls.strings[cls.nic][direction]
            # * Calculate current speed
            stat["speed"].append(
                round((stat["total"] - stat["last"]) / (time() - cls.timestamp))
            )
            stat["last"] = stat["total"]
            speed = stat["speed"][-1]

            if cls.net_min[direction] == -1:
                cls.net_min[direction] = units_to_bytes(
                    getattr(CONFIG, "net_" + direction)
                )
                stat["graph_top"] = cls.net_min[direction]
                stat["graph_lower"] = 7
                if not cls.auto_min:
                    stat["redraw"] = True
                    strings["graph_top"] = fmt.floating_humanizer(
                        stat["graph_top"], short=True
                    )

            if stat["offset"] and stat["offset"] > stat["total"]:
                cls.reset = True

            if cls.reset:
                if not stat["offset"]:
                    stat["offset"] = stat["total"]
                else:
                    stat["offset"] = 0
                if direction == "upload":
                    cls.reset = False
                    NetBox.redraw = True

            if len(stat["speed"]) > NetBox.width * 2:
                del stat["speed"][0]

            strings["total"] = fmt.floating_humanizer(stat["total"] - stat["offset"])
            strings["byte_ps"] = fmt.floating_humanizer(stat["speed"][-1], per_second=True)
            strings["bit_ps"] = fmt.floating_humanizer(
                stat["speed"][-1], bit=True, per_second=True
            )

            if speed > stat["top"] or not stat["top"]:
                stat["top"] = speed
                strings["top"] = fmt.floating_humanizer(
                    stat["top"], bit=True, per_second=True
                )

            if cls.auto_min:
                if speed > stat["graph_top"]:
                    stat["graph_raise"] += 1
                    if stat["graph_lower"] > 0:
                        stat["graph_lower"] -= 1
                elif speed < stat["graph_top"] // 10:
                    stat["graph_lower"] += 1
                    if stat["graph_raise"] > 0:
                        stat["graph_raise"] -= 1

                if stat["graph_raise"] >= 5 or stat["graph_lower"] >= 5:
                    if stat["graph_raise"] >= 5:
                        stat["graph_top"] = round(max(stat["speed"][-5:]) / 0.8)
                    elif stat["graph_lower"] >= 5:
                        stat["graph_top"] = max(10 << 10, max(stat["speed"][-5:]) * 3)
                    stat["graph_raise"] = 0
                    stat["graph_lower"] = 0
                    stat["redraw"] = True
                    strings["graph_top"] = fmt.floating_humanizer(
                        stat["graph_top"], short=True
                    )

        cls.timestamp = time()

        if CONFIG.net_sync:
            c_max: int = max(
                cls.stats[cls.nic]["download"]["graph_top"],
                cls.stats[cls.nic]["upload"]["graph_top"],
            )
            if c_max != cls.sync_top:
                cls.sync_top = c_max
                cls.sync_string = fmt.floating_humanizer(cls.sync_top, short=True)
                NetBox.redraw = True

    @classmethod
    def _draw(cls):
        NetBox._draw_fg()
