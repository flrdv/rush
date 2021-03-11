from time import sleep
from threading import Thread


class PeriodicEvent:
    def __init__(self, timeout, func, args=(), kwargs=None):
        self.timeout = timeout
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}

    def start(self, threaded=False):
        if threaded:
            return Thread(target=self.start, kwargs={'threaded': False}).start()

        while True:
            sleep(self.timeout)
            self.func(*self.args, **self.kwargs)


class PeriodicEventsExecutor:
    def __init__(self):
        self.events = []

    def add_event(self, timeout, func, args=(), kwargs=None):
        self.events.append(PeriodicEvent(timeout, func, args, kwargs))

        return self

    def add_event_obj(self, event: PeriodicEvent):
        self.events.append(event)

        return self

    def start(self):
        """
        Start all the events. Has to be called after every adding events
        """

        for event in self.events:
            event.start(threaded=True)

        self.events.clear()
