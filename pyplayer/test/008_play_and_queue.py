#!/usr/bin/env python3
# Bryant Hansen

# USAGE:
#    sys.argv[0] media_file 
# where media_file full path/filename to mplayer-compatible file on the local
# system
#
# initial conditions: pyplayerd is running

import os
import sys
from time import sleep
import traceback


import pyplayer_config as config
import pyplayerc
from multiprocessing.connection import Client

#####################################################
# Main

if __name__ == "__main__":
    USAGE = sys.argv[0] + "  media_file"
    host = 'localhost'
    port = 17000

    if not os.path.exists(config.pidfile):
        raise RuntimeError('pyplayerd pidfile %s not found; it appears to not be running.  (tip: execute "path-to/pyplayerd start")' % config.pidfile)

    # TODO: check for python process running

    try:
        c = Client(
                (host, port),
                authkey=b'super_secret_auth_key__CHANGEME')
    except ConnectionRefusedError:
        print("Connection Refused on %s:%d.  Is the daemon running?"
              % (host, port))
        sys.exit(2)
    except:
        print("*** print_exc:")
        traceback.print_exc()
        sys.exit(3)
    proxy = pyplayerc.RPCProxy(c)
    result = proxy.add_url_to_queue(sys.argv[2])
    result = proxy.playurl(sys.argv[1])

