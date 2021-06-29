# Rush v2

Simple Webserver on python3, like Flask, but not Flask. I wanna make it as fast as I can (without using asynchronous code). Additional description will be provided later, when I'll be able to release first beta version

---

In master-branch I'm currently working on Rush-v2

Rush-v2 is a tiny web-server (currently about ~1000 lines of code) with processor-scalability using self forks. Also implements responsing with file, smart in-memory cache.

Unfortunataly, web-server is build on epoll, and by this reason only Linux is supported. Also using SO_REUSEPORT socket option, so Linux 3.9 and higher is supported in case of
web-server process forking feature usage. WSL is also not supported because currently doesn't support SO_REUSEPORT option

Full requirements:
- Python 3.6+
- Linux 3.9+ ONLY
- Installed packages:
  - `inotify` (for smart cache)
  - `http_parser` (for parsing http requests)

--- 

Rush v2.3.0 benchmarks:

- Testing configuration:
  - Linux Mint Cinnamon 20
  - Python 3.8.5
  - Ryzen 5 2600x 6 cores/12 threads
  - 32gb ram 2133 mHz
  - SSD Samsung 970 evo+
  - Using 12 web-server processes
  - Testing with wrk
- Results:
  - Static redirect:
      Running 1m test @ http://localhost:9090/easter
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     4.70ms    2.34ms 199.95ms   91.66%
          Req/Sec    18.30k     2.00k   50.05k    86.97%
        13112754 requests in 1.00m, 1.39GB read
      Requests/sec: 218206.37
      Transfer/sec:     23.72MB

  - Static cached file:
      Running 1m test @ http://localhost:9090/
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     4.94ms    1.84ms 145.08ms   92.56%
          Req/Sec    17.12k     1.12k   60.62k    91.21%
        12268091 requests in 1.00m, 3.61GB read
      Requests/sec: 204221.07
      Transfer/sec:     61.54MB

  - Simple response with parsing url parameters:
      Running 1m test @ http://localhost:9090/hello?name=bill
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     6.12ms    2.25ms 168.92ms   94.33%
          Req/Sec    13.85k   747.67    40.04k    90.15%
        9920047 requests in 1.00m, 0.90GB read
      Requests/sec: 165167.13
      Transfer/sec:     15.28MB

 
 During all the tests, processor was loaded on 99.7-100%
 
 ---
 
 Contacts:
  - I always check my [Telegram](https://t.me/floordiv) (or just by username: @floordiv)
    - My native language is _Russian_, but you can talk with me in _English_
