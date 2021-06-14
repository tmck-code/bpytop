from typing import Dict, Union, Any, List
from collections import defaultdict
import psutil

from bpytop.collectors.collector import Collector

class ProcCollector(Collector):
    """Collects process stats"""

    buffer: str = ProcBox.buffer
    search_filter: str = ""
    case_sensitive: bool = False
    processes: Dict = {}
    num_procs: int = 0
    det_cpu: float = 0.0
    detailed: bool = False
    detailed_pid: Union[int, None] = None
    details: Dict[str, Any] = {}
    details_cpu: List[int] = []
    details_mem: List[int] = []
    expand: int = 0
    collapsed: Dict = {}
    tree_counter: int = 0
    p_values: List[str] = [
        "pid",
        "name",
        "cmdline",
        "num_threads",
        "username",
        "memory_percent",
        "cpu_percent",
        "cpu_times",
        "create_time",
    ]
    sort_expr: Dict = {}
    sort_expr["pid"] = compile("p.info['pid']", "str", "eval")
    sort_expr["program"] = compile(
        "'' if p.info['name'] == 0.0 else p.info['name']", "str", "eval"
    )
    sort_expr["arguments"] = compile(
        "' '.join(str(p.info['cmdline'])) or ('' if p.info['name'] == 0.0 else p.info['name'])",
        "str",
        "eval",
    )
    sort_expr["threads"] = compile(
        "0 if p.info['num_threads'] == 0.0 else p.info['num_threads']", "str", "eval"
    )
    sort_expr["user"] = compile(
        "'' if p.info['username'] == 0.0 else p.info['username']", "str", "eval"
    )
    sort_expr["memory"] = compile("p.info['memory_percent']", "str", "eval")
    sort_expr["cpu lazy"] = compile(
        "(sum(p.info['cpu_times'][:2] if not p.info['cpu_times'] == 0.0 else [0.0, 0.0]) * 1000 / (time() - p.info['create_time']))",
        "str",
        "eval",
    )
    sort_expr["cpu responsive"] = compile(
        "(p.info['cpu_percent'] if CONFIG.proc_per_core else (p.info['cpu_percent'] / THREADS))",
        "str",
        "eval",
    )

    @classmethod
    def _collect(cls):
        """List all processess with pid, name, arguments, threads, username, memory percent and cpu percent"""
        if not "proc" in Box.boxes:
            return
        out: Dict = {}
        cls.det_cpu = 0.0
        sorting: str = CONFIG.proc_sorting
        reverse: bool = not CONFIG.proc_reversed
        proc_per_cpu: bool = CONFIG.proc_per_core
        search: List[str] = []
        if cls.search_filter:
            if cls.case_sensitive:
                search = [i.strip() for i in cls.search_filter.split(",")]
            else:
                search = [i.strip() for i in cls.search_filter.lower().split(",")]
        err: float = 0.0
        n: int = 0

        if CONFIG.proc_tree and sorting == "arguments":
            sorting = "program"

        sort_cmd = cls.sort_expr[sorting]

        if CONFIG.proc_tree:
            cls._tree(
                sort_cmd=sort_cmd,
                reverse=reverse,
                proc_per_cpu=proc_per_cpu,
                search=search,
            )
        else:
            for p in sorted(
                psutil.process_iter(
                    cls.p_values + (["memory_info"] if CONFIG.proc_mem_bytes else []),
                    err,
                ),
                key=lambda p: eval(sort_cmd),
                reverse=reverse,
            ):
                if cls.collect_interrupt or cls.proc_interrupt:
                    return
                if (
                    p.info["name"] == "idle"
                    or p.info["name"] == err
                    or p.info["pid"] == err
                ):
                    continue
                if p.info["cmdline"] == err:
                    p.info["cmdline"] = ""
                if p.info["username"] == err:
                    p.info["username"] = ""
                if p.info["num_threads"] == err:
                    p.info["num_threads"] = 0
                if search:
                    if cls.detailed and p.info["pid"] == cls.detailed_pid:
                        cls.det_cpu = p.info["cpu_percent"]
                    for value in [
                        p.info["name"],
                        " ".join(p.info["cmdline"]),
                        str(p.info["pid"]),
                        p.info["username"],
                    ]:
                        if not cls.case_sensitive:
                            value = value.lower()
                        for s in search:
                            if s in value:
                                break
                        else:
                            continue
                        break
                    else:
                        continue

                cpu = (
                    p.info["cpu_percent"]
                    if proc_per_cpu
                    else round(p.info["cpu_percent"] / THREADS, 2)
                )
                mem = p.info["memory_percent"]
                if CONFIG.proc_mem_bytes and hasattr(p.info["memory_info"], "rss"):
                    mem_b = p.info["memory_info"].rss
                else:
                    mem_b = 0

                cmd = " ".join(p.info["cmdline"]) or "[" + p.info["name"] + "]"

                out[p.info["pid"]] = {
                    "name": p.info["name"],
                    "cmd": cmd,
                    "threads": p.info["num_threads"],
                    "username": p.info["username"],
                    "mem": mem,
                    "mem_b": mem_b,
                    "cpu": cpu,
                }

                n += 1

            cls.num_procs = n
            cls.processes = out.copy()

        if cls.detailed:
            cls.expand = ((ProcBox.width - 2) - ((ProcBox.width - 2) // 3) - 40) // 10
            if cls.expand > 5:
                cls.expand = 5
        if cls.detailed and not cls.details.get("killed", False):
            try:
                c_pid = cls.detailed_pid
                det = psutil.Process(c_pid)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                cls.details["killed"] = True
                cls.details["status"] = psutil.STATUS_DEAD
                ProcBox.redraw = True
            else:
                attrs: List[str] = ["status", "memory_info", "create_time"]
                if not SYSTEM == "MacOS":
                    attrs.extend(["cpu_num"])
                if cls.expand:
                    attrs.extend(["nice", "terminal"])
                    if not SYSTEM == "MacOS":
                        attrs.extend(["io_counters"])

                if not c_pid in cls.processes:
                    attrs.extend(
                        [
                            "pid",
                            "name",
                            "cmdline",
                            "num_threads",
                            "username",
                            "memory_percent",
                        ]
                    )

                cls.details = det.as_dict(attrs=attrs, ad_value="")
                if det.parent() != None:
                    cls.details["parent_name"] = det.parent().name()
                else:
                    cls.details["parent_name"] = ""

                cls.details["pid"] = c_pid
                if c_pid in cls.processes:
                    cls.details["name"] = cls.processes[c_pid]["name"]
                    cls.details["cmdline"] = cls.processes[c_pid]["cmd"]
                    cls.details["threads"] = f'{cls.processes[c_pid]["threads"]}'
                    cls.details["username"] = cls.processes[c_pid]["username"]
                    cls.details["memory_percent"] = cls.processes[c_pid]["mem"]
                    cls.details["cpu_percent"] = round(
                        cls.processes[c_pid]["cpu"]
                        * (1 if CONFIG.proc_per_core else THREADS)
                    )
                else:
                    cls.details["cmdline"] = (
                        " ".join(cls.details["cmdline"])
                        or "[" + cls.details["name"] + "]"
                    )
                    cls.details["threads"] = f'{cls.details["num_threads"]}'
                    cls.details["cpu_percent"] = round(cls.det_cpu)

                cls.details["killed"] = False
                if SYSTEM == "MacOS":
                    cls.details["cpu_num"] = -1
                    cls.details["io_counters"] = ""

                if hasattr(cls.details["memory_info"], "rss"):
                    cls.details["memory_bytes"] = floating_humanizer(cls.details["memory_info"].rss)  # type: ignore
                else:
                    cls.details["memory_bytes"] = "? Bytes"

                if isinstance(cls.details["create_time"], float):
                    uptime = timedelta(
                        seconds=round(time() - cls.details["create_time"], 0)
                    )
                    if uptime.days > 0:
                        cls.details[
                            "uptime"
                        ] = f'{uptime.days}d {str(uptime).split(",")[1][:-3].strip()}'
                    else:
                        cls.details["uptime"] = f"{uptime}"
                else:
                    cls.details["uptime"] = "??:??:??"

                if cls.expand:
                    if cls.expand > 1:
                        cls.details["nice"] = f'{cls.details["nice"]}'
                    if SYSTEM == "BSD":
                        if cls.expand > 2:
                            if hasattr(cls.details["io_counters"], "read_count"):
                                cls.details[
                                    "io_read"
                                ] = f'{cls.details["io_counters"].read_count}'
                            else:
                                cls.details["io_read"] = "?"
                        if cls.expand > 3:
                            if hasattr(cls.details["io_counters"], "write_count"):
                                cls.details[
                                    "io_write"
                                ] = f'{cls.details["io_counters"].write_count}'
                            else:
                                cls.details["io_write"] = "?"
                    else:
                        if cls.expand > 2:
                            if hasattr(cls.details["io_counters"], "read_bytes"):
                                cls.details["io_read"] = floating_humanizer(
                                    cls.details["io_counters"].read_bytes
                                )
                            else:
                                cls.details["io_read"] = "?"
                        if cls.expand > 3:
                            if hasattr(cls.details["io_counters"], "write_bytes"):
                                cls.details["io_write"] = floating_humanizer(
                                    cls.details["io_counters"].write_bytes
                                )
                            else:
                                cls.details["io_write"] = "?"
                    if cls.expand > 4:
                        cls.details["terminal"] = f'{cls.details["terminal"]}'.replace(
                            "/dev/", ""
                        )

                cls.details_cpu.append(cls.details["cpu_percent"])
                mem = cls.details["memory_percent"]
                if mem > 80:
                    mem = round(mem)
                elif mem > 60:
                    mem = round(mem * 1.2)
                elif mem > 30:
                    mem = round(mem * 1.5)
                elif mem > 10:
                    mem = round(mem * 2)
                elif mem > 5:
                    mem = round(mem * 10)
                else:
                    mem = round(mem * 20)
                cls.details_mem.append(mem)
                if len(cls.details_cpu) > ProcBox.width:
                    del cls.details_cpu[0]
                if len(cls.details_mem) > ProcBox.width:
                    del cls.details_mem[0]

    @classmethod
    def _tree(cls, sort_cmd, reverse: bool, proc_per_cpu: bool, search: List[str]):
        """List all processess in a tree view with pid, name, threads, username, memory percent and cpu percent"""
        out: Dict = {}
        err: float = 0.0
        det_cpu: float = 0.0
        infolist: Dict = {}
        cls.tree_counter += 1
        tree = defaultdict(list)
        n: int = 0
        for p in sorted(
            psutil.process_iter(
                cls.p_values + (["memory_info"] if CONFIG.proc_mem_bytes else []), err
            ),
            key=lambda p: eval(sort_cmd),
            reverse=reverse,
        ):
            if cls.collect_interrupt:
                return
            try:
                tree[p.ppid()].append(p.pid)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                pass
            else:
                infolist[p.pid] = p.info
                n += 1
        if 0 in tree and 0 in tree[0]:
            tree[0].remove(0)

        def create_tree(
            pid: int,
            tree: defaultdict,
            indent: str = "",
            inindent: str = " ",
            found: bool = False,
            depth: int = 0,
            collapse_to: Union[None, int] = None,
        ):
            nonlocal infolist, proc_per_cpu, search, out, det_cpu
            name: str
            threads: int
            username: str
            mem: float
            cpu: float
            collapse: bool = False
            cont: bool = True
            getinfo: Dict = {}
            if cls.collect_interrupt:
                return
            try:
                name = psutil.Process(pid).name()
                if name == "idle":
                    return
            except psutil.Error:
                pass
                cont = False
                name = ""
            if pid in infolist:
                getinfo = infolist[pid]

            if search and not found:
                if cls.detailed and pid == cls.detailed_pid:
                    det_cpu = getinfo["cpu_percent"]
                if "username" in getinfo and isinstance(getinfo["username"], float):
                    getinfo["username"] = ""
                if "cmdline" in getinfo and isinstance(getinfo["cmdline"], float):
                    getinfo["cmdline"] = ""
                for value in [
                    name,
                    str(pid),
                    getinfo.get("username", ""),
                    " ".join(getinfo.get("cmdline", "")),
                ]:
                    if not cls.case_sensitive:
                        value = value.lower()
                    for s in search:
                        if s in value:
                            found = True
                            break
                    else:
                        continue
                    break
                else:
                    cont = False
            if cont:
                if getinfo:
                    if getinfo["num_threads"] == err:
                        threads = 0
                    else:
                        threads = getinfo["num_threads"]
                    if getinfo["username"] == err:
                        username = ""
                    else:
                        username = getinfo["username"]
                    cpu = (
                        getinfo["cpu_percent"]
                        if proc_per_cpu
                        else round(getinfo["cpu_percent"] / THREADS, 2)
                    )
                    mem = getinfo["memory_percent"]
                    if getinfo["cmdline"] == err:
                        cmd = ""
                    else:
                        cmd = (
                            " ".join(getinfo["cmdline"]) or "[" + getinfo["name"] + "]"
                        )
                    if CONFIG.proc_mem_bytes and hasattr(getinfo["memory_info"], "rss"):
                        mem_b = getinfo["memory_info"].rss
                    else:
                        mem_b = 0
                else:
                    threads = mem_b = 0
                    username = ""
                    mem = cpu = 0.0

                if pid in cls.collapsed:
                    collapse = cls.collapsed[pid]
                else:
                    collapse = depth > CONFIG.tree_depth
                    cls.collapsed[pid] = collapse

                if collapse_to and not search:
                    out[collapse_to]["threads"] += threads
                    out[collapse_to]["mem"] += mem
                    out[collapse_to]["mem_b"] += mem_b
                    out[collapse_to]["cpu"] += cpu
                else:
                    if pid in tree and len(tree[pid]) > 0:
                        sign: str = "+" if collapse else "-"
                        inindent = inindent.replace(" ├─ ", "[" + sign + "]─").replace(
                            " └─ ", "[" + sign + "]─"
                        )
                    out[pid] = {
                        "indent": inindent,
                        "name": name,
                        "cmd": cmd,
                        "threads": threads,
                        "username": username,
                        "mem": mem,
                        "mem_b": mem_b,
                        "cpu": cpu,
                        "depth": depth,
                    }

            if search:
                collapse = False
            elif collapse and not collapse_to:
                collapse_to = pid

            if pid not in tree:
                return
            children = tree[pid][:-1]

            for child in children:
                create_tree(
                    child,
                    tree,
                    indent + " │ ",
                    indent + " ├─ ",
                    found=found,
                    depth=depth + 1,
                    collapse_to=collapse_to,
                )
            create_tree(
                tree[pid][-1],
                tree,
                indent + "  ",
                indent + " └─ ",
                depth=depth + 1,
                collapse_to=collapse_to,
            )

        create_tree(min(tree), tree)
        cls.det_cpu = det_cpu

        if cls.collect_interrupt:
            return
        if cls.tree_counter >= 100:
            cls.tree_counter = 0
            for pid in list(cls.collapsed):
                if not psutil.pid_exists(pid):
                    del cls.collapsed[pid]
        cls.num_procs = len(out)
        cls.processes = out.copy()

    @classmethod
    def sorting(cls, key: str):
        index: int = CONFIG.sorting_options.index(CONFIG.proc_sorting) + (
            1 if key in ["right", "l"] else -1
        )
        if index >= len(CONFIG.sorting_options):
            index = 0
        elif index < 0:
            index = len(CONFIG.sorting_options) - 1
        CONFIG.proc_sorting = CONFIG.sorting_options[index]
        if "left" in Key.mouse:
            del Key.mouse["left"]
        Collector.collect(ProcCollector, interrupt=True, redraw=True)

    @classmethod
    def _draw(cls):
        ProcBox._draw_fg()
