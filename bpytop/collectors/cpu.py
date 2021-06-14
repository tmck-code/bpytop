class CpuCollector(Collector):
    """Collects cpu usage for cpu and cores, cpu frequency, load_avg, uptime and cpu temps"""

    cpu_usage: List[List[int]] = []
    cpu_upper: List[int] = []
    cpu_lower: List[int] = []
    cpu_temp: List[List[int]] = []
    cpu_temp_high: int = 0
    cpu_temp_crit: int = 0
    for _ in range(THREADS + 1):
        cpu_usage.append([])
        cpu_temp.append([])
    freq_error: bool = False
    cpu_freq: int = 0
    load_avg: List[float] = []
    uptime: str = ""
    buffer: str = CpuBox.buffer
    sensor_method: str = ""
    got_sensors: bool = False
    sensor_swap: bool = False
    cpu_temp_only: bool = False

    @classmethod
    def get_sensors(cls):
        """Check if we can get cpu temps and return method of getting temps"""
        cls.sensor_method = ""
        if SYSTEM == "MacOS":
            try:
                if (
                    which("coretemp")
                    and subprocess.check_output(
                        ["coretemp", "-p"], universal_newlines=True
                    )
                    .strip()
                    .replace("-", "")
                    .isdigit()
                ):
                    cls.sensor_method = "coretemp"
                elif which("osx-cpu-temp") and subprocess.check_output(
                    "osx-cpu-temp", universal_newlines=True
                ).rstrip().endswith("°C"):
                    cls.sensor_method = "osx-cpu-temp"
            except:
                pass
        elif CONFIG.cpu_sensor != "Auto" and CONFIG.cpu_sensor in CONFIG.cpu_sensors:
            cls.sensor_method = "psutil"
        elif hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if name.lower().startswith("cpu"):
                            cls.sensor_method = "psutil"
                            break
                        for entry in entries:
                            if entry.label.startswith(
                                ("Package", "Core 0", "Tdie", "CPU")
                            ):
                                cls.sensor_method = "psutil"
                                break
            except:
                pass
        if not cls.sensor_method and SYSTEM == "Linux":
            try:
                if which("vcgencmd") and subprocess.check_output(
                    ["vcgencmd", "measure_temp"], universal_newlines=True
                ).strip().endswith("'C"):
                    cls.sensor_method = "vcgencmd"
            except:
                pass
        cls.got_sensors = bool(cls.sensor_method)

    @classmethod
    def _collect(cls):
        cls.cpu_usage[0].append(ceil(psutil.cpu_percent(percpu=False)))
        if len(cls.cpu_usage[0]) > Term.width * 4:
            del cls.cpu_usage[0][0]

        cpu_times_percent = psutil.cpu_times_percent()
        for x in ["upper", "lower"]:
            if getattr(CONFIG, "cpu_graph_" + x) == "total":
                setattr(cls, "cpu_" + x, cls.cpu_usage[0])
            else:
                getattr(cls, "cpu_" + x).append(
                    ceil(getattr(cpu_times_percent, getattr(CONFIG, "cpu_graph_" + x)))
                )
            if len(getattr(cls, "cpu_" + x)) > Term.width * 4:
                del getattr(cls, "cpu_" + x)[0]

        for n, thread in enumerate(psutil.cpu_percent(percpu=True), start=1):
            cls.cpu_usage[n].append(ceil(thread))
            if len(cls.cpu_usage[n]) > Term.width * 2:
                del cls.cpu_usage[n][0]
        try:
            if CONFIG.show_cpu_freq and hasattr(psutil.cpu_freq(), "current"):
                freq: float = psutil.cpu_freq().current
                cls.cpu_freq = round(freq * (1 if freq > 10 else 1000))
            elif cls.cpu_freq > 0:
                cls.cpu_freq = 0
        except Exception as e:
            if not cls.freq_error:
                cls.freq_error = True
                errlog.error("Exception while getting cpu frequency!")
                errlog.exception(f"{e}")
            else:
                pass
        cls.load_avg = [round(lavg, 2) for lavg in psutil.getloadavg()]
        cls.uptime = (
            str(timedelta(seconds=round(time() - psutil.boot_time(), 0)))[:-3]
            .replace(" days,", "d")
            .replace(" day,", "d")
        )

        if CONFIG.check_temp and cls.got_sensors:
            cls._collect_temps()

    @classmethod
    def _collect_temps(cls):
        temp: int = 1000
        cores: List[int] = []
        core_dict: Dict[int, int] = {}
        entry_int: int = 0
        cpu_type: str = ""
        c_max: int = 0
        s_name: str = "_-_"
        s_label: str = "_-_"
        if cls.sensor_method == "psutil":
            try:
                if CONFIG.cpu_sensor != "Auto":
                    s_name, s_label = CONFIG.cpu_sensor.split(":", 1)
                for name, entries in psutil.sensors_temperatures().items():
                    for num, entry in enumerate(entries, 1):
                        if name == s_name and (
                            entry.label == s_label or str(num) == s_label
                        ):
                            if entry.label.startswith("Package"):
                                cpu_type = "intel"
                            elif entry.label.startswith("Tdie"):
                                cpu_type = "ryzen"
                            else:
                                cpu_type = "other"
                            if getattr(entry, "high", None) != None and entry.high > 1:
                                cls.cpu_temp_high = round(entry.high)
                            else:
                                cls.cpu_temp_high = 80
                            if (
                                getattr(entry, "critical", None) != None
                                and entry.critical > 1
                            ):
                                cls.cpu_temp_crit = round(entry.critical)
                            else:
                                cls.cpu_temp_crit = 95
                            temp = round(entry.current)
                        elif (
                            entry.label.startswith(("Package", "Tdie"))
                            and cpu_type in ["", "other"]
                            and s_name == "_-_"
                            and hasattr(entry, "current")
                        ):
                            if (
                                not cls.cpu_temp_high
                                or cls.sensor_swap
                                or cpu_type == "other"
                            ):
                                cls.sensor_swap = False
                                if (
                                    getattr(entry, "high", None) != None
                                    and entry.high > 1
                                ):
                                    cls.cpu_temp_high = round(entry.high)
                                else:
                                    cls.cpu_temp_high = 80
                                if (
                                    getattr(entry, "critical", None) != None
                                    and entry.critical > 1
                                ):
                                    cls.cpu_temp_crit = round(entry.critical)
                                else:
                                    cls.cpu_temp_crit = 95
                            cpu_type = (
                                "intel"
                                if entry.label.startswith("Package")
                                else "ryzen"
                            )
                            temp = round(entry.current)
                        elif (
                            entry.label.startswith(("Core", "Tccd", "CPU"))
                            or (name.lower().startswith("cpu") and not entry.label)
                        ) and hasattr(entry, "current"):
                            if entry.label.startswith(("Core", "Tccd")):
                                entry_int = int(
                                    entry.label.replace("Core", "").replace("Tccd", "")
                                )
                                if entry_int in core_dict and cpu_type != "ryzen":
                                    if c_max == 0:
                                        c_max = max(core_dict) + 1
                                    if (
                                        c_max < THREADS // 2
                                        and (entry_int + c_max) not in core_dict
                                    ):
                                        core_dict[(entry_int + c_max)] = round(
                                            entry.current
                                        )
                                    continue
                                elif entry_int in core_dict:
                                    continue
                                core_dict[entry_int] = round(entry.current)
                                continue
                            elif cpu_type in ["intel", "ryzen"]:
                                continue
                            if not cpu_type:
                                cpu_type = "other"
                                if not cls.cpu_temp_high or cls.sensor_swap:
                                    cls.sensor_swap = False
                                    if (
                                        getattr(entry, "high", None) != None
                                        and entry.high > 1
                                    ):
                                        cls.cpu_temp_high = round(entry.high)
                                    else:
                                        cls.cpu_temp_high = (
                                            60 if name == "cpu_thermal" else 80
                                        )
                                    if (
                                        getattr(entry, "critical", None) != None
                                        and entry.critical > 1
                                    ):
                                        cls.cpu_temp_crit = round(entry.critical)
                                    else:
                                        cls.cpu_temp_crit = (
                                            80 if name == "cpu_thermal" else 95
                                        )
                                temp = round(entry.current)
                            cores.append(round(entry.current))
                if core_dict:
                    if not temp or temp == 1000:
                        temp = sum(core_dict.values()) // len(core_dict)
                    if not cls.cpu_temp_high or not cls.cpu_temp_crit:
                        cls.cpu_temp_high, cls.cpu_temp_crit = 80, 95
                    cls.cpu_temp[0].append(temp)
                    if cpu_type == "ryzen":
                        ccds: int = len(core_dict)
                        cores_per_ccd: int = CORES // ccds
                        z: int = 1
                        for x in range(THREADS):
                            if x == CORES:
                                z = 1
                            if CORE_MAP[x] + 1 > cores_per_ccd * z:
                                z += 1
                            if z in core_dict:
                                cls.cpu_temp[x + 1].append(core_dict[z])
                    else:
                        for x in range(THREADS):
                            if CORE_MAP[x] in core_dict:
                                cls.cpu_temp[x + 1].append(core_dict[CORE_MAP[x]])

                elif len(cores) == THREADS / 2:
                    cls.cpu_temp[0].append(temp)
                    for n, t in enumerate(cores, start=1):
                        try:
                            cls.cpu_temp[n].append(t)
                            cls.cpu_temp[THREADS // 2 + n].append(t)
                        except IndexError:
                            break

                else:
                    cls.cpu_temp[0].append(temp)
                    if len(cores) > 1:
                        for n, t in enumerate(cores, start=1):
                            try:
                                cls.cpu_temp[n].append(t)
                            except IndexError:
                                break
            except Exception as e:
                errlog.exception(f"{e}")
                cls.got_sensors = False
                CpuBox._calc_size()

        else:
            try:
                if cls.sensor_method == "coretemp":
                    temp = max(
                        0,
                        int(
                            subprocess.check_output(
                                ["coretemp", "-p"], universal_newlines=True
                            ).strip()
                        ),
                    )
                    cores = [
                        max(0, int(x))
                        for x in subprocess.check_output(
                            "coretemp", universal_newlines=True
                        ).split()
                    ]
                    if len(cores) == THREADS / 2:
                        cls.cpu_temp[0].append(temp)
                        for n, t in enumerate(cores, start=1):
                            try:
                                cls.cpu_temp[n].append(t)
                                cls.cpu_temp[THREADS // 2 + n].append(t)
                            except IndexError:
                                break
                    else:
                        cores.insert(0, temp)
                        for n, t in enumerate(cores):
                            try:
                                cls.cpu_temp[n].append(t)
                            except IndexError:
                                break
                    if not cls.cpu_temp_high:
                        cls.cpu_temp_high = 85
                        cls.cpu_temp_crit = 100
                elif cls.sensor_method == "osx-cpu-temp":
                    temp = max(
                        0,
                        round(
                            float(
                                subprocess.check_output(
                                    "osx-cpu-temp", universal_newlines=True
                                ).strip()[:-2]
                            )
                        ),
                    )
                    if not cls.cpu_temp_high:
                        cls.cpu_temp_high = 85
                        cls.cpu_temp_crit = 100
                elif cls.sensor_method == "vcgencmd":
                    temp = max(
                        0,
                        round(
                            float(
                                subprocess.check_output(
                                    ["vcgencmd", "measure_temp"],
                                    universal_newlines=True,
                                ).strip()[5:-2]
                            )
                        ),
                    )
                    if not cls.cpu_temp_high:
                        cls.cpu_temp_high = 60
                        cls.cpu_temp_crit = 80
            except Exception as e:
                errlog.exception(f"{e}")
                cls.got_sensors = False
                CpuBox._calc_size()
            else:
                if not cores:
                    cls.cpu_temp[0].append(temp)

        if not core_dict and len(cores) <= 1:
            cls.cpu_temp_only = True
        if len(cls.cpu_temp[0]) > 5:
            for n in range(len(cls.cpu_temp)):
                if cls.cpu_temp[n]:
                    del cls.cpu_temp[n][0]

    @classmethod
    def _draw(cls):
        CpuBox._draw_fg()
