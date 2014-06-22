#!/usr/bin/env python3
# daemon.py

"""
from the Python Cookbook (version 3)
  11.8. Implementing Remote Procedure Calls

TODO: determine overhead; can a new instance be loaded for each web request?
...or must it be static?
"""

import json
from multiprocessing.connection import Client

class RPCProxy:
    def __init__(self, connection):
        self._connection = connection
    def __getattr__(self, name):
        def do_rpc(*args, **kwargs):
            self._connection.send(json.dumps((name, args, kwargs)))
            result = json.loads(self._connection.recv())
            return result
        return do_rpc

"""
example:
c = Client(('localhost', 17000), authkey=b'super_secret_auth_key')
proxy = RPCProxy(c)
proxy = pyplayerc.RPCProxy(c)
proxy.add(2, 3)
"""

