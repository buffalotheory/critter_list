# various settings

from os import sep

servername = 'localhost'
port = 17000
auth_key = b'super_secret_auth_key__CHANGEME'

fifo_dir = "/tmp"
fifo_dir = "/projects/critter_list/fifo"

url = ""
ififo = fifo_dir + "/mplayer.stdin.fifo"
log = "/projects/critter_list/log/mplayer.log"

pidfile = '/run/pyplayer/pyplayer.pid'

#LOGDIR = '/projects/critter_list/log'
LOGDIR = "/var/log/pyplayer"
LOGFILE = ("%s%s%s" % (LOGDIR, sep, 'pyplayer.log'))
stdout_file = ("%s%s%s" % (LOGDIR, sep, "pyplayer.out"))
stderr_file = ("%s%s%s" % (LOGDIR, sep, "pyplayer.err"))


