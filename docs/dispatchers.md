Dispatchers - are a layer between core and user. Dispatchers are meant to handle requests 
just as they want. Of course, their purpose is to be kinda interface for a user, but 
nothing prevents them of handling in some specific way. For example, it's a way to integrate
Rush webserver with another languages, or even make compatibility with nginx configs.

Dispatchers should be a class that implements such a methods:
- async handle_request
  - conn: socket.socket, client connection
  - response: callable, callback to send a response bytestring to response stream
  - http_version: bytes, bytestring in format "<major>.<minor>"
  - headers: CaseInsensetiveDict[bytes, bytes], request headers
  - method: bytes, GET, POST, PUT, ...
  - url: bytes, decoded request path
  - parameters: dict[bytes, list[bytes]], url parameters that are dict, in which all the keys are bytes, and all the values - are lists of bytestrings to match rfc
  - fragment: bytes, page fragment
  - body: bytes, request body