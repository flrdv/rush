# Rush v2

Simple Webserver on python3, like Flask, but not Flask. I wanna make it as fast as I can (without using asynchronous code). Additional description will be provided later, when I'll be able to release first beta version

---

In master-branch I'm currently working on Rush-v2

Rush-v2 is a tiny web-server (currently about ~1000-1500 lines of code) with processor-scalability using self forks. Also implements responsing with file, smart in-memory cache.

--- 

Current perfomance:

- testing configuration:
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
  - I always check my [Telegram](https://t.me/floordiv)
    - My native language is _Russian_, but you can talk with me in _English_
