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

import pyplayerc
from multiprocessing.connection import Client

#####################################################
# Main

if __name__ == "__main__":
    USAGE = sys.argv[0] + "  media_file"
    host = 'localhost'
    port = 17000
    try:
        c = Client(
                (host, port),
                authkey=b'super_secret_auth_key__CHANGEME')
    except:
        print("\nUnexpected error:", sys.exc_info()[0])
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("\n*** print_tb:")
        traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        print("\n*** print_exception (limit=2):")
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                limit=2, file=sys.stdout)
        print("\n*** print_exception (no limit):")
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                file=sys.stdout)
        print("\n*** print_exc:")
        traceback.print_exc()
        print("\n*** format_exc, first and last line:")
        formatted_lines = traceback.format_exc().splitlines()
        print(formatted_lines[0])
        print(formatted_lines[-1])
        print("\n*** format_exception:")
        print(repr(traceback.format_exception(exc_type, exc_value,
                                            exc_traceback)))
        print("\n*** extract_tb:")
        print(repr(traceback.extract_tb(exc_traceback)))
        print("\n*** format_tb:")
        print(repr(traceback.format_tb(exc_traceback)))
        print("\n*** tb_lineno:", exc_traceback.tb_lineno)
    proxy = pyplayerc.RPCProxy(c)
    result = proxy.playurl(sys.argv[1])

