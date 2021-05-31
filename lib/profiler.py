from time import time


class Profiler:
    def __init__(self):
        """
        TODO: add setting for output of profiler into file/terminal
        """

        self.functions_running_time = {}

    def profile(self, func):
        def wrapper(*args, **kwargs):
            begin = time()
            func(*args, **kwargs)
            end = time()
            self.functions_running_time[func] = end - begin

        return wrapper

    def print_results(self):
        nested_funcs_run_time = 0

        for func, running_time in list(self.functions_running_time.items()):
            print(func.__name__ + ':', end='\n\t')
            print('Running time without other profiling functions calls:',
                  round((running_time - nested_funcs_run_time) * 1000, 2), 'ms')
            print('\tAbsolute running time:', round(running_time * 1000, 2), 'ms')
            nested_funcs_run_time += running_time
