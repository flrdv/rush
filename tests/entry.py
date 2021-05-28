from timeit import timeit

print(timeit('enums.EnumClass.connect', number=1000000, setup='import enums'))
print(timeit('enums.CONNECT', number=1000000, setup='import enums'))


"""
results:
    number=10_000:
        0.0003347000000000003 (enum)
        0.00024480000000000335 (global variable)
    number=100_000:
        0.0032958999999999974
        0.0024050000000000044
    number=1_000_000:
        0.033072700000000003
        0.024235800000000002
        
Enum is too slow for webserver, readability in this case does not worth it
"""
