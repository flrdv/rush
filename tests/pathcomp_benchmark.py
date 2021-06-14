import timeit

setup = """
import core.utils.pathcomp
comp_paths = core.utils.pathcomp.compare_paths
"""

print(timeit.timeit("comp_paths('hello/<name>/wassup', 'hello/bill/wassup')", setup=setup, number=1_000))
