#!/usr/bin/env python3
# Bryant Hansen

# TODO: unit test

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
        print("proxy.add(2, 3): %d" % proxy.add(2, 3))

if __name__ == '__main__':
    unittest.main()

