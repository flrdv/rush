# Rush v2

Simple Webserver on python3, priority of which one is performance. The aim of the project is to make as much fast web-server, as I can. Actually, I'm planning to write some extensions on C, so I'd like to say that the aim of the project is to make as fast web-server FOR python as I can.

---

In master-branch I'm currently working on Rush-v2

Rush-v2 is a tiny web-server (currently about ~1500 lines of code) with processor-scalability using self forks. Also implements responsing with file, smart in-memory cache.

Unfortunataly, web-server is build on epoll, and by this reason only Linux is supported. Also using SO_REUSEPORT socket option, so Linux 3.9 and higher is supported in case of
web-server process forking feature usage. WSL is also not supported because currently doesn't support SO_REUSEPORT option

Full requirements:
- Python 3.6+
- Linux 3.9+ ONLY
- Installed packages:
  - `inotify` (for smart cache)
  - `httptools` (for parsing http requests)

--- 

Rush v2.3.0 benchmarks:

- Testing configuration:
  - Linux Mint Cinnamon 20
  - Python 3.8.5
  - Ryzen 5 2600x 6 cores/12 threads
  - 32gb ram 2133 mHz
  - SSD Samsung 970 evo+
  - Using 12 web-server processes
  - Testing with wrk (threads: 12, connections: 1000)
- Results:
  - Static redirect:
      ```
      Running 1m test @ http://localhost:9090/easter
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     4.70ms    2.34ms 199.95ms   91.66%
          Req/Sec    18.30k     2.00k   50.05k    86.97%
        13112754 requests in 1.00m, 1.39GB read
      Requests/sec: 218206.37
      Transfer/sec:     23.72MB
      ```

  - Static cached file:
      ```
      Running 1m test @ http://localhost:9090/
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     4.94ms    1.84ms 145.08ms   92.56%
          Req/Sec    17.12k     1.12k   60.62k    91.21%
        12268091 requests in 1.00m, 3.61GB read
      Requests/sec: 204221.07
      Transfer/sec:     61.54MB
      ```

  - Simple response with parsing url parameters:
      ```
      Running 1m test @ http://localhost:9090/hello?name=bill
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     6.12ms    2.25ms 168.92ms   94.33%
          Req/Sec    13.85k   747.67    40.04k    90.15%
        9920047 requests in 1.00m, 0.90GB read
      Requests/sec: 165167.13
      Transfer/sec:     15.28MB
      ```
 
 During all the tests, processor was loaded near to the 100%
 
 
 ---
 
 Rush v2.4.0 benchmarks:

- Testing configuration:
  - Linux Mint Cinnamon 20
  - Python 3.8.5
  - Ryzen 5 2600x 6 cores/12 threads
  - 32gb ram 2133 mHz
  - Using 12 web-server processes
  - Testing with wrk (threads: 12, connections: 1000)
- Results:
  - Static redirect:
      ```
      Running 1m test @ http://localhost:9090/easter
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     3.34ms    3.63ms  73.40ms   87.33%
          Req/Sec    31.51k     6.84k   74.67k    68.34%
        Latency Distribution
          50%    1.86ms
          75%    3.71ms
          90%    8.22ms
          99%   17.59ms
        22570848 requests in 1.00m, 2.46GB read
      Requests/sec: 375573.69
      Transfer/sec:     41.91MB
      ```

  - Static cached file:
      ```
      Running 1m test @ http://localhost:9090/
        12 threads and 1000 connections
        Thread Stats   Avg      Stdev     Max   +/- Stdev
          Latency     3.57ms    3.86ms  63.49ms   87.35%
          Req/Sec    29.13k     6.84k   85.63k    68.54%
        Latency Distribution
          50%    2.04ms
          75%    4.01ms
          90%    8.60ms
          99%   18.74ms
        20851824 requests in 1.00m, 6.18GB read
      Requests/sec: 347009.50
      Transfer/sec:    105.24MB
      ```

  - Simple response with parsing url parameters:
      - Not available in v2.4.0

 ---
 
 Rush v2.4.3 benchmarks:
 
 - Testing configuration:
   - Seagate BarraCuda 7200 RPM
   - 12 web-server processes
 
 - Using: `FileSystemCache`
   - Static cached file with handler (http://localhost/):
   
       ```
       Running 1m test @ http://localhost:9090/
         12 threads and 1000 connections
         Thread Stats   Avg      Stdev     Max   +/- Stdev
           Latency     4.31ms    4.08ms 135.15ms   86.60%
           Req/Sec    23.08k     5.03k   55.78k    67.16%
         Latency Distribution
           50%    2.65ms
           75%    4.92ms
           90%   10.30ms
           99%   19.49ms
         16525533 requests in 1.00m, 5.13GB read
       Requests/sec: 275049.53
       Transfer/sec:     87.35MB
       ```
       
   - 404 error:
       ```
       Running 1m test @ http://localhost:9090/non-existing-page-or-route
         12 threads and 1000 connections
         Thread Stats   Avg      Stdev     Max   +/- Stdev
           Latency     5.72ms    4.75ms 357.85ms   89.13%
           Req/Sec    15.86k     2.28k   42.00k    76.60%
         Latency Distribution
           50%    4.28ms
           75%    6.18ms
           90%   10.73ms
           99%   21.34ms
         11371908 requests in 1.00m, 5.02GB read
       Requests/sec: 189245.85
       Transfer/sec:     85.55MB
       ```
      
  - Using `InMemoryCache`:
    - Static cached file, but with handler:
        ```
        Running 1m test @ http://localhost:9090/
          12 threads and 1000 connections
          Thread Stats   Avg      Stdev     Max   +/- Stdev
            Latency     4.27ms    4.09ms  97.26ms   87.35%
            Req/Sec    22.89k     5.17k   55.44k    71.38%
          Latency Distribution
            50%    2.64ms
            75%    4.73ms
            90%    9.98ms
            99%   19.85ms
          16393029 requests in 1.00m, 5.08GB read
        Requests/sec: 272785.73
        Transfer/sec:     86.63MB
        ```
    
    - 404 error:
        ```
        Running 1m test @ http://localhost:9090/non-existing-page-or-route
          12 threads and 1000 connections
          Thread Stats   Avg      Stdev     Max   +/- Stdev
            Latency     5.36ms    4.13ms 226.25ms   86.84%
            Req/Sec    16.75k     3.18k   52.14k    72.70%
          Latency Distribution
             50%    3.95ms
             75%    5.83ms
             90%   10.52ms
             99%   21.21ms
          11999001 requests in 1.00m, 5.30GB read
        Requests/sec: 199715.42
        Transfer/sec:     90.28MB
        ```
      
 - Some only-server-dependent tests:
   - Static redirect:
       ```
       Running 1m test @ http://localhost:9090/easter
         12 threads and 1000 connections
         Thread Stats   Avg      Stdev     Max   +/- Stdev
           Latency     3.69ms    4.07ms  93.84ms   86.62%
           Req/Sec    29.42k     5.67k   64.14k    70.42%
         Latency Distribution
            50%    2.04ms
            75%    4.03ms
            90%    9.44ms
            99%   19.30ms
         21073603 requests in 1.00m, 2.59GB read
       Requests/sec: 350665.96
       Transfer/sec:     44.14MB
       ```
     
   - Parsing url parameters and responsing:
       ```
       Running 1m test @ http://localhost:9090/hello?name=bill
         12 threads and 1000 connections
         Thread Stats   Avg      Stdev     Max   +/- Stdev
           Latency     4.94ms    4.14ms  94.70ms   87.33%
           Req/Sec    18.88k     3.47k   47.66k    73.48%
         Latency Distribution
            50%    3.52ms
            75%    5.16ms
            90%   10.20ms
            99%   21.60ms
         13534344 requests in 1.00m, 1.12GB read
       Requests/sec: 225197.81
       Transfer/sec:     19.11MB
       ```
            
 During all the tests, processor was loaded near to the 100%
 
 ---
 
 Contacts:
  - I always check my [Telegram](https://t.me/floordiv) (or just by username: @floordiv)
    - My native language is _Russian_, but you can talk with me in _English_
