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


import pyplayer_config as pyconf
import pyplayerc
from multiprocessing.connection import Client

#####################################################
# Main

if __name__ == "__main__":
    USAGE = sys.argv[0] + "  media_file"
    host = 'localhost'
    port = 17000

    config = {}

    conffile = "/projects/critter_list/pyplayer/test/test.conf"
    try:
        execfile(conffile, config)
        try:
            if len(config["HOST"]) > 0:
                host = config["HOST"]
            if len(config["PORT"]) > 0:
                port = config["PORT"]
        except:
            print("failed to read host from %s" % conffile)
    except:
        print("failed to execfile(%s)" % conffile)

    conffile = "./test.conf"
    try:
        execfile("./test.conf", config)
        try:
            if len(config["HOST"]) > 0:
                host = config["HOST"]
            if len(config["PORT"]) > 0:
                port = config["PORT"]
        except:
            print("failed to read host from %s" % conffile)
    except:
        print("failed to execfile(%s)" % conffile)
        

    if not os.path.exists(pyconf.pidfile):
        raise RuntimeError('pyplayerd pidfile %s not found; it appears to not be running.  (tip: execute "path-to/pyplayerd start")' % pyconf.pidfile)

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
    result = proxy.playurl(sys.argv[1])

