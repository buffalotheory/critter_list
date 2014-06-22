#!/usr/bin/env python3
# daemon.py

"""
originally from the Python Cookbook (version 3)
  11.8. Implementing Remote Procedure Calls
  12.2. Determining If a Thread Has Started
  12.14. Launching a Daemon Process on Unix
  (perhaps more)
"""

import os
import sys

import atexit
import signal

import json

from multiprocessing.connection import Listener
from threading import Thread

import pyplayer
from inspect import getmembers, isfunction, ismethod


class RPCHandler:

    def __init__(self):
        self._functions = { }
        self.mplif = pyplayer.MPlayerIF()

    def register_function(self, func):
        print(
            "adding function %s (type = %s) isfunction = %s"
            % (str(func.__name__), str(type(func)), str(isfunction(func)))
        )
        self._functions[func.__name__] = func

    def handle_connection(self, connection):
        try:
            while True:
                # Receive a message
                func_name, args, kwargs = json.loads(connection.recv())
                sys.stdout.write(
                    "RPCHandler.handle_connection: (%s) called\n"
                    % (func_name)
                )
                sys.stdout.flush()
                # Run the RPC and send a response
                try:
                    r = self._functions[func_name](*args,**kwargs)
                    sres = json.dumps(r)
                    sys.stdout.write(
                        "RPCHandler.handle_connection: "
                        "function %s result = %s, str(result) = %s type = %s\n"
                        % (func_name, str(r), str(sres), str(type(r)))
                    )
                    connection.send(sres)
                except Exception as e:
                    connection.send(json.dumps(str(e)))
        except EOFError:
            pass

# test function #1
def add(x, y):
    sys.stdout.write("add(%d, %d)\n" % (x, y))
    sys.stdout.flush()
    return x + y

# test function #2
def sub(x, y):
    sys.stdout.write("sub(%d, %d)\n" % (x, y))
    sys.stdout.flush()
    return x - y

def daemonize(pidfile, *,
                        stdin='/dev/null',
                        stdout='/dev/null',
                        stderr='/dev/null'):

    if os.path.exists(pidfile):
        raise RuntimeError('Already running')

    # First fork (detaches from parent)
    try:
        if os.fork() > 0:
            raise SystemExit(0) # Parent exit
    except OSError as e:
        raise RuntimeError('fork #1 failed.')

    os.chdir('/')
    os.umask(0)
    os.setsid()
    # Second fork (relinquish session leadership)
    try:
        if os.fork() > 0:
            raise SystemExit(0)
    except OSError as e:
        raise RuntimeError('fork #2 failed.')

    print('%s started' % DAEMON, file=sys.stderr)

    # Flush I/O buffers
    sys.stdout.flush()
    sys.stderr.flush()

    # Replace file descriptors for stdin, stdout, and stderr
    with open(stdin, 'rb', 0) as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open(stdout, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open(stderr, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stderr.fileno())
    # Write the PID file
    with open(pidfile,'w') as f:
        print(os.getpid(),file=f)

    # Arrange to have the PID file removed on exit/signal
    atexit.register(lambda: os.remove(pidfile))
    # Signal handler for termination (required)

    def sigterm_handler(signo, frame):
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, sigterm_handler)

def rpc_server(handler, address, authkey):
    sock = Listener(address, authkey=authkey)
    while True:
        client = sock.accept()
        t = Thread(target=handler.handle_connection, args=(client,))
        t.daemon = True
        t.start()
        # Some remote functions

def main():
    import time
    sys.stdout.write('Daemon started with pid {}\n'.format(os.getpid()))
    # Register with a handler
    handler = RPCHandler()
    handler.register_function(add)
    handler.register_function(sub)
    for f in getmembers(handler.mplif):
        print(
            "handler.mplif: method %s (type = %s) ismethod = %s"
            % (str(f[1]), str(type(f[1])), str(ismethod(f[1])))
        )
        if ismethod(f[1]) and f[0][0] != '_':
            handler.register_function(f[1])
    # Run the server
    rpc_server(handler, ('localhost', 17000), authkey=b'super_secret_auth_key')

def daemon_start():
    try:
        daemonize(
            PIDFILE,
            stdout='/tmp/daemon.log',
            stderr='/tmp/dameon.log'
        )
        print('%s started' % PIDFILE, file=sys.stderr)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
    main()

def daemon_stop():
    if os.path.exists(PIDFILE):
        with open(PIDFILE) as f:
            os.kill(int(f.read()), signal.SIGTERM)
            # FIXME: don't exit until the process is confirmed dead
        print('%s stopped' % DAEMON, file=sys.stderr)
    else:
        print('Not running', file=sys.stderr)
        raise SystemExit(1)

def daemon_status():
    if not os.path.exists(PIDFILE):
        print('Not running.  %s does not exist.' % PIDFILE, file=sys.stderr)
        raise SystemExit(1)

    pid = int(open(PIDFILE).read())
    # example: cmdlinefile="/projects/6124/cmdline"
    cmdlinefile = "/proc/%d/cmdline" % pid
    if not os.path.exists(cmdlinefile):
        print(
            'Not running.  cmdline file %s does not exist in /proc tree.'
            % cmdlinefile, file=sys.stderr
        )
        raise SystemExit(1)

    s = open(cmdlinefile).readline()
    # example: s='python3\x00./pyplayerd.py\x00start\x00'
    s2 = s.split("\0")[1]
    # example: s2='./pyplayerd.py'
    if not s2.endswith(DAEMON):
        print(
            'Not running.  cmdline file %s indicates %s; expected %s'
            % (cmdlinefile, s2, DAEMON), file=sys.stderr
        )
        raise SystemExit(1)
    print('%s is running (pid=%d)' % (DAEMON, pid), file=sys.stderr)

def daemon_restart():
    try:
        daemon_stop()
    except:
        pass
    daemon_start()


if __name__ == '__main__':
    PIDFILE = '/run/pyplayer/pyplayer.pid'
    DAEMON = sys.argv[0]
    if len(sys.argv) != 2:
        print(
            'Usage: {} [start|stop|restart|status]'.format(sys.argv[0]),
            file=sys.stderr
        )
        raise SystemExit(1)
    if sys.argv[1] == 'start':
        daemon_start()
    elif sys.argv[1] == 'stop':
        daemon_stop()
    elif sys.argv[1] == 'status':
        daemon_status()
    elif sys.argv[1] == 'restart':
        daemon_restart()
    else:
        print('Unknown command {!r}'.format(sys.argv[1]), file=sys.stderr)
        raise SystemExit(1)

