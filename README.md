# Rush

Simple Webserver on python3, like Flask, but not Flask. I wanna make it as fast as I can (without using asynchronous code). Additional description will be provided later, when I'll be able to release first alpha version

Branches:
  - master - main branch where all the features appear first
  - release-x.x.x - releases of webserver
  - for-history - old triple-rank system, that doesn't seems to be workable (I didn't test it completely)
  - remake - new Rush iteration (like major versions)

Rush v.2: in progress
  What will be done:
    - improved perfomance
    - improved architecture
    - improved api (current is too poor and miserable)
    - added regular paths routing (like `/some/<path>` in flask)
    - improved loader: cache will be updating in realtime by detecting file changes
