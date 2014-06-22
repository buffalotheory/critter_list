#!/usr/bin/env python3
# Bryant Hansen

# USAGE:
#    sys.argv[0]
# (no args)
#
# initial conditions: pyplayerd is running

import os
import sys
from time import sleep

import pyplayerc
from multiprocessing.connection import Client

import unittest

class TestSequenceFunctions(unittest.TestCase):

    def test_sample(self):
        c = Client(('localhost', 17000), authkey=b'super_secret_auth_key')
        proxy = pyplayerc.RPCProxy(c)
        result = proxy.add(2, 3)
        self.assertEqual(result, 5)
        print("proxy.add(2, 3): %d" % result)
        result = proxy.sub(10, 4)
        self.assertEqual(result, 6)
        print("proxy.sub(10, 4): %d" % result)
        result = proxy.test_sub2(20, 12)
        self.assertEqual(result, 8)
        print("proxy.test_sub2(20, 12): %s" % str(result))

        # at the moment, this is a bit puzzling; it looks like some of the
        # result in an error case is truncated
        result = proxy.doesnt_exist(1, 2, 3)
        self.assertEqual(result, "'doesnt_exist'")
        print("proxy.doesnt_exist(1, 2, 3): %s" % str(result))

    def test_speed(self):
        c = Client(('localhost', 17000), authkey=b'super_secret_auth_key')
        proxy = pyplayerc.RPCProxy(c)

        iterations = 100
        for n in range(iterations):
            result = proxy.add(2, 3)
            sys.stdout.write("proxy.add(2, 3): %d - " % result)
            result = proxy.sub(10, 4)
            sys.stdout.write("proxy.sub(10, 4): %d - " % result)
            result = proxy.test_sub2(20, 12)
            sys.stdout.write("proxy.test_sub2(20, 12): %s - " % str(result))
        sys.stdout.write("\n")

    def test_player(self):
        c = Client(('localhost', 17000), authkey=b'super_secret_auth_key')
        proxy = pyplayerc.RPCProxy(c)

        result = proxy.playurl(sys.argv[1])
        sleep(5)
        result = proxy.get_percent_pos()
        sys.stdout.write("proxy.get_percent_pos(): %s\n" % result)


#####################################################
# Main

if __name__ == "__main__":
    unittest.main()
