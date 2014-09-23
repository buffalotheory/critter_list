#!/usr/bin/python3.3 -u
# @author: Bryant Hansen
# @license: GPLv3

"""
A wrapper for mplayer using the slave interfacet
https://mplayerhq.hu/DOCS/tech/slave.txt

This is intended to be used as a library (ie. imported into other python
scripts).  ie.
  import pyplayer
  self.mplif = pyplayer.MPlayerIF()
  mplif.playurl(url)
But may be run independently with an argument.  Example:
  ./pyplayer path-to/my_music_file.mp3

This command launches one thread for the mplayer output monitor and one
thread for mplayer itself.  The current thread continues, exits immediately
and can be used to control and monitor the 2 threads that have been launched.
This allows the main thread to control and monitor the other 2 threads, issuing
play, pause, stop, get_length, get_position, etc. commands and requests.  It
may listen for external commands and requests, interpret them, control the
state of the system and provide feedback.

pyplayerd imports this module and acts as a network-based server, receiving
commands via the network (a json-based interface over TCP/HTTPS)

pyplayer as a library been tested with ipython; and running from the command
line
The main work starts with the playurl() function

It is functional, but requires static state information, which is not
so convenient for the web server application that this designed to interface
with.

A redesign may be necessary in order to connect to an existing instance of
mplayer, without any static information on startup.  This might work like so:
  - mplayer writes stdout and stderr files
  - on startup, look for processes named mplayer
  - check each mplayer process for open files in the /proc/<pid>/ tree
  - verify that the intended files are open
  - seek to the end of stdout(and/or stderr); mplayer normally responds in
    slave mode on stdout
  - send the command to the fifo (or directly to stdin, if possible)
  - get the response from new data from stdout
  - 

This version should become a separate branch before new development

Alternative Option: Daemon Design (local server)
  - implement daemon in background
  - launches, monitors, controls, kills, mplayer subprocess
  - use json for RPC

TODO: consider any queuing mechanisms that should be in place for the
      mplayer interface (either in or out)

"""

import sys
import stat
import os
import signal
import subprocess
import logging
from time import sleep
from datetime import datetime, timedelta
from threading import Thread, Event


#####################################################
# Defaults

fifo_dir = "/tmp"
fifo_dir = "/projects/critter_list/fifo"

url = ""
ififo = fifo_dir + "/mplayer.stdin.fifo"
log = "/projects/critter_list/log/mplayer.log"

LOGDIR = '/projects/critter_list/log'
LOGFILE = ("%s/%s.log" % (LOGDIR, 'player'))

#####################################################
# Constants


# see https://mplayerhq.hu/DOCS/tech/slave.txt for a description of arguments
# data types, and return values that can be expected from the following
# commands
commands = [
    "af_add",
    "af_clr",
    "af_cmdline",
    "af_del",
    "af_switch",
    "alt_src_step",
    "audio_delay",
    "[brightness|contrast|gamma|hue|saturation]",
    "capturing",
    "change_rectangle",
    "dvb_set_channel",
    "dvdnav",
    "edl_loadfile",
    "edl_mark",
    "frame_drop",
    "gui",
    "screenshot",
    "key_down_event",
    "loadfile",
    "loadlist",
    "loop",
    "menu",
    "set_menu",
    "mute",
    "osd",
    "osd_show_progression",
    "osd_show_property_text",
    "osd_show_text",
    "panscan",
    "pause",
    "frame_step",
    "pt_step",
    "pt_up_step",
    "quit",
    "radio_set_channel",
    "radio_set_freq",
    "radio_step_channel",
    "radio_step_freq",
    "seek",
    "seek_chapter",
    "switch_angle",
    "set_mouse_pos",
    "set_property",
    "speed_incr",
    "speed_mult",
    "speed_set",
    "step_property",
    "stop",
    "sub_alignment",
    "sub_delay",
    "sub_load",
    "sub_log",
    "sub_pos",
    "sub_remove",
    "sub_select",
    "sub_source",
    "sub_file",
    "sub_vob",
    "sub_demux",
    "sub_scale",
    "vobsub_lang",
    "sub_step",
    "sub_visibility",
    "forced_subs_only",
    "switch_audio",
    "switch_angle",
    "switch_ratio",
    "switch_title",
    "switch_vsync",
    "teletext_add_digit",
    "teletext_go_link",
    "tv_start_scan",
    "tv_step_channel",
    "tv_step_norm",
    "tv_step_chanlist",
    "tv_set_channel",
    "tv_last_channel",
    "tv_set_freq",
    "tv_step_freq",
    "tv_set_norm",
    "tv_set_brightness",
    "tv_set_contrast",
    "tv_set_hue",
    "tv_set_saturation",
    "use_master",
    "vo_border",
    "vo_fullscreen",
    "vo_ontop",
    "vo_rootwin",
    "volume",
    "overlay_add",
    "overlay_remove",

    "get_audio_bitrate",
    "get_audio_codec",
    "get_audio_samples",
    "get_file_name",
    "get_meta_album",
    "get_meta_artist",
    "get_meta_comment",
    "get_meta_genre",
    "get_meta_title",
    "get_meta_track",
    "get_meta_year",
    "get_percent_pos",
    "get_property",
    "get_sub_visibility",
    "get_time_length",
    "get_time_pos",
    "get_vo_fullscreen",
    "get_video_bitrate",
    "get_video_codec",
    "get_video_resolution",
]

"""
a dictionary of strings that mplayer should answer
the key is the string, the value is the tag of the expected answer
example:
  when mplayer receives the string, "get_audio_bitrate" via its fifo, it should
  respond with the answer:ANS_AUDIO_BITRATE=<value>
  where <value> is a number representing the bitrate
"""
get_strings = {
    "get_audio_bitrate"     : "ANS_AUDIO_BITRATE",
    "get_audio_codec"       : "ANS_AUDIO_CODEC",
    "get_audio_samples"     : "ANS_AUDIO_SAMPLES",
    "get_file_name"         : "ANS_FILENAME",
    "get_meta_album"        : "ANS_META_ALBUM",
    "get_meta_artist"       : "ANS_META_ARTIST",
    "get_meta_comment"      : "ANS_META_COMMENT",
    "get_meta_genre"        : "ANS_META_GENRE",
    "get_meta_title"        : "ANS_META_TITLE",
    "get_meta_track"        : "ANS_META_TRACK",
    "get_meta_year"         : "ANS_META_YEAR",
    "get_percent_pos"       : "ANS_PERCENT_POSITION",
    "get_sub_visibility"    : "",
    "get_time_length"       : "ANS_LENGTH",
    "get_time_pos"          : "ANS_TIME_POSITION",
    "get_vo_fullscreen"     : "",
    "get_video_bitrate"     : "ANS_VIDEO_BITRATE",
    "get_video_codec"       : "ANS_VIDEO_CODEC",
    "get_video_resolution"  : "ANS_VIDEO_RESOLUTION",
}

# answer to properties are alway ANS_property_name, with property_name in all
# lower case, like the original and unlike the get_ commands
properties = {
    "osdlevel"              : "",
    "speed"                 : "",
    "loop"                  : "",
    "pause"                 : "",
    "filename"              : "",
    "path"                  : "",
    "demuxer"               : "",
    "stream_pos"            : "",
    "stream_start"          : "",
    "stream_end"            : "",
    "stream_length"         : "",
    "stream_time_pos"       : "",
    "titles"                : "",
    "chapter"               : "",
    "chapters"              : "",
    "angle"                 : "",
    "length"                : "",
    "percent_pos"           : "",
    "time_pos"              : "",
    "metadata"              : "",
    "metadata/*"            : "",
    "volume"                : "",
    "balance"               : "",
    "mute"                  : "",
    "audio_delay"           : "",
    "audio_format"          : "",
    "audio_codec"           : "",
    "audio_bitrate"         : "",
    "samplerate"            : "",
    "channels"              : "",
    "switch_audio"          : "",
    "switch_angle"          : "",
    "switch_title"          : "",
    "capturing"             : "",
    "fullscreen"            : "",
    "deinterlace"           : "",
    "ontop"                 : "",
    "rootwin"               : "",
    "border"                : "",
    "framedropping"         : "",
    "gamma"                 : "",
    "brightness"            : "",
    "contrast"              : "",
    "saturation"            : "",
    "hue"                   : "",
    "panscan"               : "",
    "vsync"                 : "",
    "video_format"          : "",
    "video_codec"           : "",
    "video_bitrate"         : "",
    "width"                 : "",
    "height"                : "",
    "fps"                   : "",
    "aspect"                : "",
    "switch_video"          : "",
    "switch_program"        : "",
    "sub"                   : "",
    "sub_source"            : "",
    "sub_file"              : "",
    "sub_vob"               : "",
    "sub_demux"             : "",
    "sub_delay"             : "",
    "sub_pos"               : "",
    "sub_alignment"         : "",
    "sub_visibility"        : "",
    "sub_forced_only"       : "",
    "sub_scale"             : "",
    "tv_brightness"         : "",
    "tv_contrast"           : "",
    "tv_saturation"         : "",
    "tv_hue"                : "",
    "teletext_page"         : "",
    "teletext_subpage"      : "",
    "teletext_mode"         : "",
    "teletext_format"       : "",
    "teletext_half_page"    : "",
}


class MPlayerStates():
    INVALID = 0
    ERROR = 1
    IDLE = 2
    LOADING = 3
    PLAYING = 4
    PAUSED = 5


#####################################################
# Functions

def TRACE(msg):
    m = ("%s: %s" % (datetime.now().strftime("%H:%M:%S.%f")[0:-3], msg))
    logging.info(m)
    print(m)

class MPlayerIF:

    mplthread = None
    player_state = 0
    mplproc = None
    read_thread = None
    fifo = ififo
    mpl_fifo_fd = None

    def __init__(self):
        logging.basicConfig(filename=LOGFILE, level=logging.DEBUG)

    def flush_output(self, stdouterr):
        # TODO: implement me!
        pass

    def __set_stdout_nonblocking(self, p):
        import fcntl
        filemode = fcntl.fcntl(p.stdout.fileno(), fcntl.F_GETFL)
        TRACE("filemode = %s" % hex(filemode))
        filemode |= os.O_NONBLOCK
        TRACE("filemode = %s" % hex(filemode))
        ret = fcntl.fcntl(p.stdout.fileno(), fcntl.F_SETFL, filemode)
        TRACE("filemode set.  ret = " + str(ret))

    def __set_stdout_blocking(self, p):
        import fcntl
        filemode = fcntl.fcntl(p.stdout.fileno(), fcntl.F_GETFL)
        TRACE("filemode = %s" % hex(filemode))
        # try the ^= operator to toggle the specific bit
        # TODO: verify that this works
        filemode ^= os.O_NONBLOCK
        TRACE("filemode = %s" % hex(filemode))
        ret = fcntl.fcntl(p.stdout.fileno(), fcntl.F_SETFL, filemode)
        TRACE("filemode set.  ret = " + str(ret))

    def __subprocess_output_readline(self, stdouterr, expect=""):
        """
        This function dumps all pending data from the mplayer stdout or stderr
        buffers and will optionally match the "expect" string.
        Note: file blocking mode has an effect on this function

        @param stdout - the subprocess.stdout (or .stderr) member when created
        with stdout=subprocess.PIPE and/or stderr=subprocess.PIPE options
        @param expect - the name of the variable that we're looking for in the
        output.  this is the expectation that the output will contain a
            var=...
        example:
            write:
            ANS_volume=87.909088
        """
        retstr = ""
        try:
            # TODO: determine how to make this blocking
            output = stdouterr.readline().decode("utf-8")
        except:
            TRACE(
                "Exception in __subprocess_output_readline: %s"
                % str(sys.exc_info())
            )
            TRACE(
                "Exception str(stdouterr) = %s"
                % str(stdouterr)
            )
            return "Exception"
        output = output.rstrip()
        if output == 'ANS_ERROR=PROPERTY_UNAVAILABLE':
            return "PROPERTY_UNAVAILABLE"
        if len(output) < 1:
            return ""
        TRACE("__subprocess_output_readline: output = %s" % output)
        if len(expect) > 0:
            split_output = output.split(expect + '=', 1)
            # we have found it
            # FIXME: does the split_output[0] param need a whitespace trim?
            if len(split_output) == 2 and split_output[0] == '':
                if len(retstr) > 0:
                    TRACE(
                        "multiple values exist matching '%s'.  "
                        "changing result from '%s' to '%s'"
                        % (expect, retstr, split_output[1])
                    )
                retstr = split_output[1]
        else:
            retstr = output
        return retstr

    def __mplayer_output_loop(self, expect=""):
        """
        This function dumps all pending data from the mplayer stdout buffer and
        will optionally match the "expect" string.
        Note: file blocking mode has an effect on this function

        mplproc.stdout - the subprocess.stdout (or .stderr) member when created
        with stdout=subprocess.PIPE and/or stderr=subprocess.PIPE options

        @param expect - the name of the variable that we're looking for in the
        output.  this is the expectation that the output will contain a
            var=...
        example:
            write:
            ANS_volume=87.909088
        """
        retstr = ""
        output = "_default_"
        while len(output) > 0:
            TRACE("__mplayer_output_loop: mplayer returned '%s'.  " % (output))
            try:
                # TODO: determine how to make this blocking
                output = mplproc.stdout.readline().decode("utf-8")
            except:
                output = ""
            output = output.rstrip()
            if output == 'ANS_ERROR=PROPERTY_UNAVAILABLE':
                continue
            if len(output) < 1:
                continue
            TRACE("__mplayer_output_loop: output = %s" % output)
            if len(expect) > 0:
                split_output = output.split(expect + '=', 1)
                # we have found it
                if len(split_output) == 2 and split_output[0] == '':
                    if len(retstr) > 0:
                        TRACE(
                            "multiple values exist matching '%s'.  "
                            "changing result from '%s' to '%s'"
                            % (expect, retstr, split_output[1])
                        )
                    retstr = split_output[1]
            else:
                if len(retstr) > 0:
                    retstr += '\n'
                retstr += output
        return retstr

    def get_state(self):
        """
        TODO: this should return the state psuedo-enum, rather than process
        status
        """
        return self.mplproc.poll()

    def perform_command(self, cmd, expect=""):
        TRACE("perform_command: sending cmd '%s'" % cmd)
        res = os.write(self.mpl_fifo_fd, (cmd + '\n').encode(encoding='UTF-8'))
        """
        TRACE(
            "perform_command: %s (type(result) = %s, val(result = %s))"
            % (cmd, str(type(res)), str(res))
        )
        """
        sleep(0.05)
        output = self.__mplayer_output_loop(expect)
        if len(output) > 0:
            TRACE(
                "perform_command: mplayer output returned '%s'"
                % output
            )
        else:
            TRACE(
                "perform_command: __mplayer_output_loop returned a zero-length "
                "string"
            )
        return output

    def get_current_time(self):
        return self.perform_command('get_time_pos')

    def get_percent_pos(self):
        return self.perform_command('get_percent_pos')

    def get_track_length(self):
        return self.perform_command('get_time_length')

    def get_title(self):
        return self.perform_command('get_meta_title')

    def get_artist(self):
        return self.perform_command('get_meta_artist')

    def get_album(self):
        return self.perform_command('get_meta_album')

    def get_track(self):
        return self.perform_command('get_meta_track')

    def get_genre(self):
        return self.perform_command('get_meta_genre')

    def get_year(self):
        return self.perform_command('get_meta_year')

    def get_volume1(self):
        return self.perform_command('volume')

    def get_volume2(self):
        return self.perform_command('get_property volume')

    def set_current_pos(self, position):
        return self.perform_command('seek %d 2' % position)

    def seek(self, reltime):
        return self.perform_command('seek %d 0' % reltime)

    def seek_start(self):
        return self.perform_command('seek 0 2')

    def seek_end(self):
        return self.perform_command('seek 100 1')

    def stop(self):
        return self.perform_command('stop')

    def quit(self):
        return self.perform_command('quit')

    def pause(self):
        return self.perform_command('pause')

    def do_command(self, command):
        return self.perform_command(command)

    def get_all_information(self):
        for s in get_strings.keys():
            a = self.perform_command(s)
            TRACE("get_all_information: parameter %s = '%s'" % (s, str(a)))
        for s in properties.keys():
            os.write(
                self.mpl_fifo_fd,
                ("get_property %s\n" % s).encode(encoding='UTF-8')
            )
            a = perform_command(
                    "get_property %s" % s
                )
            TRACE(
                "get_all_information: property %s = '%s'"
                % (s, str(a))
            )
        TRACE("get_all_information: all strings and properties queried.")

    def mplayer_thread(self, threadName, mplayer_start_event, url):
        """
        This is a thread which is a wrapper for the process
        The thread further isolates the mplayer process from the main
        python process.
        One goal is so that signals passed to the python process are not
        automatically propogated to the mplayer process; this can be seen
        running ipython and pressing ctrl-C after which mplayer is running.
        Hopefully the thread insulates this.

        TODO: consider tempfile/directory handling like this:
        http://stackoverflow.com/questions/1430446/create-a-temporary-fifo-named-pipe-in-python
        """
        event_set = False
        TRACE("enter mplayer_thread; launching %s" % url)
        command = [
                    "mplayer",
                    "-vo", "null",
                    "-ao", "alsa",
                    "-slave",
                    "-input",
                    "file=" + self.fifo,
                    "-quiet",
                    url
                  ]
        try:
            self.mplproc = subprocess.Popen(
                                command,
                                shell=False,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                           )
            #self.__set_stdout_blocking(self.mplproc)
            self.mpl_fifo_fd = os.open(self.fifo, os.O_WRONLY)
            TRACE(
                "launched mplayer process.  process id = %s  "
                "process poll() / exit code = %s"
                % (str(self.mplproc.pid), str(self.mplproc.poll()))
            )
            mplayer_start_event.set()
            event_set = True
            self.mplproc.wait()
            TRACE("self.mplproc.wait() completed")
        except:
            TRACE("player(%s) ERROR: failed to create read thread" % url)
            e = sys.exc_info()
            TRACE("exception info: %s" % str(e))
            if not event_set:
                mplayer_start_event.set()

    def launch_player(self, url):
        if not self.__verifyFifoPath(fifo_dir):
            TRACE(
                "playurl(%s): failed to verify the path to the fifos (%s)"
                % (url, fifo_dir)
            )
            return False

        if not self.__verifyFifo(self.fifo):
            TRACE(
                "playurl(%s): failed to __verifyFifos.  Exiting abnormally" % url
            )
            return False
        mplayer_start_event = Event()
        # start the mplayer thread, which will contain the mplayer process
        self.mplthread = Thread(
                    target = self.mplayer_thread,
                    args = ("mplayerThread", mplayer_start_event, url)
                )
        self.mplthread.start()
        mplayer_start_event.wait()
        #self.__set_stdout_nonblocking(self.mplproc)
        TRACE("launch_player: mplayer thread started")
        if self.mplproc == None:
            TRACE("launch_player ERROR: self.mplproc not set.")
            return False
        else:
            if self.mplproc.poll() == None:
                return True
            else:
                return False

    def __verifyFifoPath(self, fifo_dir):
        if os.path.exists(fifo_dir):
            if os.path.isdir(fifo_dir):
                TRACE("__verifyFifoPath: %s exists" % fifo_dir)
                return True
            else:
                TRACE(
                    "__verifyFifoPath: %s exists, but not as a directory.  "
                    "Cannot continue."
                    % fifo_dir
                )
                return False
        else:
            TRACE("__verifyFifoPath: %s does not exist.  Creating..." % fifo_dir)
            try:
                os.mkdir(fifo_dir)
            except:
                TRACE(
                    "__verifyFifoPath: exception creating fifo directory %s: %s"
                    % (fifo_dir, str(sys.exc_info()))
                )
            if os.path.isdir(fifo_dir):
                return True
            else:
                TRACE(
                    "__verifyFifoPath: failed to create fifo directory %s"
                    % fifo_dir
                )
                return False

    def __verifyFifo(self, fifo):
        if os.path.exists(fifo):
            # if it exists, but it not a fifo, then also show an error
            if not stat.S_ISFIFO(os.stat(ififo).st_mode):
                TRACE(
                    "playurl ERROR: file %s is not a fifo!  "
                    " Exiting abnormally"
                    % (ififo)
                )
                return False
            else:
                TRACE(
                    "__verifyFifo: fifo %s already exists in the filesystem and "
                    "is indeed a fifo.  We must delete the old one."
                    % (fifo)
                )
                try:
                    os.remove(fifo)
                    if os.path.exists(fifo):
                        TRACE(
                            "__verifyFifo ERROR: failed to remove old fifo %s"
                            % fifo
                        )
                        return False
                except:
                    TRACE("Exception in __verifyFifo: %s" % str(sys.exc_info()))
                    return False
        try:
            TRACE(
                "playurl: creating fifo %s..."
                % (fifo)
            )
            # TODO: figure out how to set mode here; never seemed to work
            #       0644, O644 and '0644' were all tried, with no success
            #os.mkfifo(fifo, mode=O644)
            os.mkfifo(fifo)
            if not os.path.exists(fifo):
                TRACE("ERROR: __verifyFifo: Failed to create fifo %s" % fifo)
                return False
        except:
            TRACE(
                "__verifyFifo ERROR: failed to create fifo %s.  "
                "Description: %s  %s"
                "Exiting abnormally"
                % (fifo, sys.exc_info()[0], str(sys.exc_info()))
            )
            return False
        return True

    def __subproc_output_monitor(self, threadName, stdouterr):
        empty_count = 0
        TRACE(
            "start read loop.  change to blocking reads for efficiency.  "
            "str(stdouterr) = %s" % str(stdouterr)
        )
        while True:
            try:
                out = self.__subprocess_output_readline(stdouterr)
                TRACE(
                    "__subproc_output_monitor: mplayer output = '%s'"
                    % str(out)
                )
                if len(out) > 0:
                    empty_count = 0
                else:
                    procstat = self.mplproc.poll()
                    empty_count += 1
                    if procstat == None:
                        TRACE(
                            "__subproc_output_monitor: "
                            "Empty output #%d received from "
                            "subprocess.readline()."
                            "  subprocess.poll() = %s.  type(procstat) = %s  "
                            "Continuing read loop"
                            % (empty_count, str(procstat), str(type(procstat)))
                        )
                    else:
                        TRACE("Terminating mplayer read loop")
                        return 1
                if empty_count >= 3:
                    TRACE(
                        "__subproc_output_monitor: 3 empties in a row.  "
                        "bailing out."
                    )
                    return 1
                # TODO: this should update a dictionary of vars (with timestamps)
            except:
                TRACE(
                    "__subproc_output_monitor: Exception in read loop: %s.  "
                    "Terminating."
                    % str(sys.exc_info())
                )
                break
            sleep(0.1)
        return 0

    def playurl(self, url):
        self.launch_player(url)
        """
        out = self.__mplayer_output_loop(self.mplproc.stdout)
        TRACE("playurl: cmd = '%s', out = '%s'" % (cmd, str(out)))

        """
        # start the read thread
        try:
            self.read_thread = Thread(
                        target = self.__subproc_output_monitor,
                        args = ("mplayerStdoutMonitor", self.mplproc.stdout, )
                    )
            # wait for the read thread to complete
            self.read_thread.start()
            TRACE(
                "launched mplayerStdoutMonitor.  str(read_thread) = %s  "
                "self.mplproc.stdout = %s"
                % (str(self.read_thread), str(self.mplproc.stdout))
            )
        except:
            TRACE("player(%s) ERROR: failed to create read thread" % url)
            e = sys.exc_info()
            TRACE("exception info: %s" % str(e))
            return False
        return True

    def cleanup(self):
        try:
            os.remove(self.fifo)
        except:
            TRACE(
                "Exception cleaning up on return: %s.  Aborting."
                % str(sys.exc_info())
            )
            return 5
        return 0

    def test_sub2(self, x, y):
        sys.stdout.write("test_sub2(%d, %d)\n" % (x, y))
        sys.stdout.flush()
        return x - y



#####################################################
# Main
# Run in the case of testing
# ./pyplayer.py my_music_file.mp3

if __name__ == "__main__":
    sys.stderr.write("launched %s with url %s\n" % (sys.argv[0], sys.argv[1]))
    mplif = MPlayerIF()
    mplif.playurl(sys.argv[1])
    sys.stderr.write("mplif.read_thread = %s\n" % str(mplif.read_thread))
    mplif.read_thread.join()
    sys.stderr.write("completed %s(%s)\n" % (sys.argv[0], sys.argv[1]))
    mplif.cleanup()
    sys.exit(0)

