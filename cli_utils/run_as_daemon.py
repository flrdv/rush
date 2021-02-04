import threading


def run_function(func, args=(), kwargs=None):
    if kwargs is None:
        kwargs = {}

    thread = threading.Thread(target=func, args=args,
                              kwargs=kwargs, daemon=True)
    thread.start()

    return thread
