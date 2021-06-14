import sys
from functools import lru_cache

@lru_cache
def detect() -> str:
    if "linux" in sys.platform:
        return "Linux"
    elif "bsd" in sys.platform:
        return "BSD"
    elif "darwin" in sys.platform:
        return "MacOS"
    else:
        return "Other"

def get_cpu_name() -> str:
    """Fetch a suitable CPU identifier from the CPU model name string"""
    name: str = ""
    nlist: List = []
    command: str = ""
    cmd_out: str = ""
    rem_line: str = ""
    if SYSTEM == "Linux":
        command = "cat /proc/cpuinfo"
        rem_line = "model name"
    elif SYSTEM == "MacOS":
        command = "sysctl -n machdep.cpu.brand_string"
    elif SYSTEM == "BSD":
        command = "sysctl hw.model"
        rem_line = "hw.model"

    try:
        cmd_out = subprocess.check_output(
            "LANG=C " + command, shell=True, universal_newlines=True
        )
    except:
        pass
    if rem_line:
        for line in cmd_out.split("\n"):
            if rem_line in line:
                name = re.sub(".*" + rem_line + ".*:", "", line, 1).lstrip()
    else:
        name = cmd_out
    nlist = name.split(" ")
    try:
        if "Xeon" in name and "CPU" in name:
            name = nlist[
                nlist.index("CPU") + (-1 if name.endswith(("CPU", "z")) else 1)
            ]
        elif "Ryzen" in name:
            name = " ".join(nlist[nlist.index("Ryzen") : nlist.index("Ryzen") + 3])
        elif "Duo" in name and "@" in name:
            name = " ".join(nlist[: nlist.index("@")])
        elif (
            "CPU" in name
            and not nlist[0] == "CPU"
            and not nlist[nlist.index("CPU") - 1].isdigit()
        ):
            name = nlist[nlist.index("CPU") - 1]
    except:
        pass

    name = (
        name.replace("Processor", "")
        .replace("CPU", "")
        .replace("(R)", "")
        .replace("(TM)", "")
        .replace("Intel", "")
    )
    name = re.sub(r"\d?\.?\d+[mMgG][hH][zZ]", "", name)
    name = " ".join(name.split())

    return name


def get_cpu_core_mapping() -> List[int]:
    mapping: List[int] = []
    core_ids: List[int] = []

    if SYSTEM == "Linux" and os.path.isfile("/proc/cpuinfo"):
        try:
            mapping = [0] * THREADS
            num = 0
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("processor"):
                        num = int(line.strip()[(line.index(": ") + 2) :])
                        if num > THREADS - 1:
                            break
                    elif line.startswith("core id"):
                        core_id = int(line.strip()[(line.index(": ") + 2) :])
                        if core_id not in core_ids:
                            core_ids.append(core_id)
                        mapping[num] = core_ids.index(core_id)
            if num < THREADS - 1:
                raise Exception
        except:
            mapping = []

    if not mapping:
        mapping = []
        for _ in range(THREADS // CORES):
            mapping.extend([x for x in range(CORES)])

    return mapping
