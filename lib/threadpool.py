from typing import List
from threading import Thread
from queue import Queue, Empty
from traceback import format_exc


class Worker:
    def __init__(self, tp_instance: 'ThreadPool', index=0):
        self.tp_instance = tp_instance
        self._running = False
        self.thread = Thread(target=self.executor, name=f'Worker #{index}')

    def executor(self):
        while self._running:
            try:
                func, args, kwargs = self.tp_instance.tasks.get(timeout=1)
            except Empty:
                continue

            try:
                func(*args, **kwargs)
            except Exception as exc:
                print('[THREADPOOL] An unhandled error occurred in', self.thread.name)
                print(format_exc())

    def start(self):
        self._running = True
        self.thread.start()

    def stop(self):
        self._running = False

    def __del__(self):
        self.stop()


class ThreadPool:
    def __init__(self, workers=10):
        if not isinstance(workers, int) or workers < 1:
            self.add_task = self.run_task
            self.singlethread_mode = True
        else:
            self.singlethread_mode = False

        self.workers_count = workers
        self.workers: List[Worker] = []

        self.tasks = Queue(maxsize=0)

    def add_task(self, func, args=(), kwargs=None):
        self.tasks.put((func, args, kwargs or {}))

    def run_task(self, func, args=(), kwargs=None):
        func(*args, **(kwargs or {}))

    def start(self):
        if not self.singlethread_mode:
            for index in range(1, self.workers_count + 1):
                worker = Worker(self, index)
                worker.start()
                self.workers.append(worker)

    def stop(self):
        for worker in self.workers:
            worker.stop()

    def __del__(self):
        self.stop()
