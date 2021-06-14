'Timers for testing and debugging'

from time import time
from typing import Dict
from logging import Logger

class TimeIt:
    timers: Dict[str, float] = {}
    paused: Dict[str, float] = {}
    errlog: Logger

    @classmethod
    def start(cls, name):
        cls.timers[name] = time()

    @classmethod
    def pause(cls, name):
        if name in cls.timers:
            cls.paused[name] = time() - cls.timers[name]
            del cls.timers[name]

    @classmethod
    def stop(cls, name):
        if name in cls.timers:
            total: float = time() - cls.timers[name]
            del cls.timers[name]
            if name in cls.paused:
                total += cls.paused[name]
                del cls.paused[name]
            cls.errlog.debug(f"{name} completed in {total:.6f} seconds")


def timeit_decorator(errlog):
    def wrapper(func):
        def timed(*args, **kw):
            ts = time()
            out = func(*args, **kw)
            errlog.debug(f"{func.__name__} completed in {time() - ts:.6f} seconds")
            return out
        return timed
    return wrapper

