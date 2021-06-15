# Rush v2

Simple Webserver on python3, like Flask, but not Flask. I wanna make it as fast as I can (without using asynchronous code). Additional description will be provided later, when I'll be able to release first beta version

---

In master-branch I'm currently working on Rush-v2

Rush-v2 is a tiny web-server (currently about ~1000-1500 lines of code) with processor-scalability using self forks. Also implements responsing with file, smart in-memory cache.

Unfortunataly, web-server is build on epoll, and by this reason only Linux is supported. Also using SO_REUSEPORT socket option, so Linux 3.9 and higher is supported in case of
web-server process forking feature usage. WSL is also not supported because currently doesn't support SO_REUSEPORT option

Full requirements:
- Python 3.6+
- Linux 3.9+
- Installed packages:
  - `inotify` (for smart cache)

In first public beta-release, I'll try to use `selectors` to get rid of platform-dependency on Linux and make web-server cross-platform. But I'm not sure, I don't really know how does this lib works

--- 

Current perfomance:

- Testing configuration:
  - Linux Mint Cinnamon 20
  - Ryzen 5 2600x 6 cores/12 threads
  - 32gb ram 2133 mHz
  - SSD Samsung 970 evo+
  - Using 12 web-server processes
- Results:
  - Static redirect: 180k RPS
  - Static file from cache: 175k RPS
  - Simple response with parsing url parameters: 155k RPS
 
 During tests, processor was loaded on 100%
 
 ---
 
 Contacts:
  - I always check my [Telegram](https://t.me/floordiv) (or just by username: @floordiv)
    - My native language is _Russian_, but you can talk with me in _English_
