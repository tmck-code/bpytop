class Collector:
    """Data collector master class
    * .start(): Starts collector thread
    * .stop(): Stops collector thread
    * .collect(*collectors: Collector, draw_now: bool = True, interrupt: bool = False): queues up collectors to run"""

    stopping: bool = False
    started: bool = False
    draw_now: bool = False
    redraw: bool = False
    only_draw: bool = False
    thread: threading.Thread
    collect_run = threading.Event()
    collect_idle = threading.Event()
    collect_idle.set()
    collect_done = threading.Event()
    collect_queue: List = []
    collect_interrupt: bool = False
    proc_interrupt: bool = False
    use_draw_list: bool = False
    proc_counter: int = 1

    @classmethod
    def start(cls):
        cls.stopping = False
        cls.thread = threading.Thread(target=cls._runner, args=())
        cls.thread.start()
        cls.started = True

    @classmethod
    def stop(cls):
        if cls.started and cls.thread.is_alive():
            cls.stopping = True
            cls.started = False
            cls.collect_queue = []
            cls.collect_idle.set()
            cls.collect_done.set()
            try:
                cls.thread.join()
            except:
                pass

    @classmethod
    def _runner(cls):
        """This is meant to run in it's own thread, collecting and drawing when collect_run is set"""
        draw_buffers: List[str] = []
        debugged: bool = False
        try:
            while not cls.stopping:
                if CONFIG.draw_clock and CONFIG.update_ms != 1000:
                    Box.draw_clock()
                cls.collect_run.wait(0.1)
                if not cls.collect_run.is_set():
                    continue
                draw_buffers = []
                cls.collect_interrupt = False
                cls.collect_run.clear()
                cls.collect_idle.clear()
                cls.collect_done.clear()
                if DEBUG and not debugged:
                    TimeIt.start("Collect and draw")
                while cls.collect_queue:
                    collector = cls.collect_queue.pop()
                    if not cls.only_draw:
                        collector._collect()
                    collector._draw()
                    if cls.use_draw_list:
                        draw_buffers.append(collector.buffer)
                    if cls.collect_interrupt:
                        break
                if DEBUG and not debugged:
                    TimeIt.stop("Collect and draw")
                    debugged = True
                if cls.draw_now and not Menu.active and not cls.collect_interrupt:
                    if cls.use_draw_list:
                        Draw.out(*draw_buffers)
                    else:
                        Draw.out()
                if CONFIG.draw_clock and CONFIG.update_ms == 1000:
                    Box.draw_clock()
                cls.collect_idle.set()
                cls.collect_done.set()
        except Exception as e:
            errlog.exception(f"Data collection thread failed with exception: {e}")
            cls.collect_idle.set()
            cls.collect_done.set()
            clean_quit(1, thread=True)

    @classmethod
    def collect(
        cls,
        *collectors,
        draw_now: bool = True,
        interrupt: bool = False,
        proc_interrupt: bool = False,
        redraw: bool = False,
        only_draw: bool = False,
    ):
        """Setup collect queue for _runner"""
        cls.collect_interrupt = interrupt
        cls.proc_interrupt = proc_interrupt
        cls.collect_idle.wait()
        cls.collect_interrupt = False
        cls.proc_interrupt = False
        cls.use_draw_list = False
        cls.draw_now = draw_now
        cls.redraw = redraw
        cls.only_draw = only_draw

        if collectors:
            cls.collect_queue = [*collectors]
            cls.use_draw_list = True
            if ProcCollector in cls.collect_queue:
                cls.proc_counter = 1

        else:
            cls.collect_queue = list(cls.__subclasses__())
            if CONFIG.proc_update_mult > 1:
                if cls.proc_counter > 1:
                    cls.collect_queue.remove(ProcCollector)
                if cls.proc_counter == CONFIG.proc_update_mult:
                    cls.proc_counter = 0
                cls.proc_counter += 1

        cls.collect_run.set()
