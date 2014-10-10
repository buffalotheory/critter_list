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

import pyplayerc
from multiprocessing.connection import Client

#####################################################
# Main

if __name__ == "__main__":
    USAGE = sys.argv[0] + "  media_file"
    c = Client(('localhost', 17000), authkey=b'super_secret_auth_key__CHANGEME')
    proxy = pyplayerc.RPCProxy(c)
    result = proxy.playurl(sys.argv[1])

