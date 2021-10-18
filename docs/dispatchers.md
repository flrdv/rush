Dispatchers - are a layer between core and user. Dispatchers are meant to handle requests 
just as they want. Of course, their purpose is to be kinda interface for a user, but 
nothing prevents them of handling in some specific way. For example, it's a way to integrate
Rush webserver with another languages, or even make compatibility with nginx configs.

Dispatchers should be a class that implements such a methods:
- async def process_request(self, request)
  - receives such arguments:
    - request: `entities.Request`
