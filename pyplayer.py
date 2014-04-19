#!/usr/bin/python3.3 -u
# Bryant Hansen

# https://mplayerhq.hu/DOCS/tech/slave.txt

import sys
import os
import signal
import subprocess
from time import sleep


#####################################################
# Defaults

url = "/data/media/radio/Science Friday/files/scifri201402211.mp3"
ififo = "/projects/critter_list/mplayer.stdin.fifo"
ofifo = "/projects/critter_list/mplayer.stdout.fifo"
log = "/projects/critter_list/log/mplayer.log"


#####################################################
# Constants

get_strings = [
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
    "get_sub_visibility",
    "get_time_length",
    "get_time_pos",
    "get_vo_fullscreen",
    "get_video_bitrate",
    "get_video_codec",
    "get_video_resolution"
]

properties = [
    "osdlevel",
    "speed",
    "loop",
    "pause",
    "filename",
    "path",
    "demuxer",
    "stream_pos",
    "stream_start",
    "stream_end",
    "stream_length",
    "stream_time_pos",
    "titles",
    "chapter",
    "chapters",
    "angle",
    "length",
    "percent_pos",
    "time_pos",
    "metadata",
    "metadata/*",
    "volume",
    "balance",
    "mute",
    "audio_delay",
    "audio_format",
    "audio_codec",
    "audio_bitrate",
    "samplerate",
    "channels",
    "switch_audio",
    "switch_angle",
    "switch_title",
    "capturing",
    "fullscreen",
    "deinterlace",
    "ontop",
    "rootwin",
    "border",
    "framedropping",
    "gamma",
    "brightness",
    "contrast",
    "saturation",
    "hue",
    "panscan",
    "vsync",
    "video_format",
    "video_codec",
    "video_bitrate",
    "width",
    "height",
    "fps",
    "aspect",
    "switch_video",
    "switch_program",
    "sub",
    "sub_source",
    "sub_file",
    "sub_vob",
    "sub_demux",
    "sub_delay",
    "sub_pos",
    "sub_alignment",
    "sub_visibility",
    "sub_forced_only",
    "sub_scale",
    "tv_brightness",
    "tv_contrast",
    "tv_saturation",
    "tv_hue",
    "teletext_page",
    "teletext_subpage",
    "teletext_mode",
    "teletext_format",
    "teletext_half_page"
]

def dump_output(stdout, expect = ""):
    retstr = ""
    try:
        output = stdout.readline().decode("utf-8")
    except:
        output = ""
    if len(output) < 1:
        sys.stderr.write("no data in stdout buffer\n")
    else:
        while len(output) > 0:
            #sys.stderr.write("output: " + output)
            try:
                output = stdout.readline().decode("utf-8")
            except:
                output = ""
            output = output.rstrip()
            if output == 'ANS_ERROR=PROPERTY_UNAVAILABLE':
                continue
            if len(output) < 1:
                continue
            sys.stderr.write("dump_output: output = '" + output + "'\n")
            if len(expect) > 0:
                split_output = output.split(expect + '=', 1)
                if len(split_output) == 2 and split_output[0] == '': # we have found it
                    if len(retstr) > 0:
                        sys.stderr.write(
                            "multiple values exist matching '%s'.  "
                            "changing result from '%s' to '%s'\n"
                            % (expect, retstr, split_output[1])
                        )
                    retstr = split_output[1]
            else:
                if len(retstr) > 0:
                    retstr += '\n'
                retstr += output
        return retstr

def perform_command(mplayerIn, mplayerOut, cmd, expect = ""):
    #print("perform_command: sending cmd " + cmd)
    os.write(mplayerIn, (cmd + '\n').encode(encoding='UTF-8'))
    sleep(0.1)
    output = dump_output(mplayerOut, expect)
    return output

def set_stdout_nonblocking(p):
    import fcntl
    filemode = fcntl.fcntl(p.stdout.fileno(), fcntl.F_GETFL)
    print("filemode = " + str(filemode))
    filemode |= os.O_NONBLOCK
    print("filemode = " + str(filemode))
    ret = fcntl.fcntl(p.stdout.fileno(), fcntl.F_SETFL, filemode)
    print("filemode set.  ret = " + str(ret))

def get_all_information(mplayerIn, mplayerOut):
    for s in get_strings:
        a = perform_command(mplayerIn, mplayerOut, s)
        print("get_all_information: parameter " + s + " = '" + str(a) + "'")
    for s in properties:
        os.write(mplayerIn, ("get_property " + s + '\n').encode(encoding='UTF-8'))
        a = perform_command(mplayerIn, mplayerOut, "get_property " + s)
        print("get_all_information: property " + s + " = '" + str(a) + "'")

def stop():
    os.write(io, 'stop\n'.encode(encoding='UTF-8'))

def pause():
    os.write(io, 'pause\n'.encode(encoding='UTF-8'))

def playurl(url):
    command = [
                "mplayer", 
                "-vo", "null", 
                "-ao", "alsa", 
                "-slave",
                "-input", "file=" + ififo, 
                "-quiet", 
                "-loop", "0", 
                url
            ]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    set_stdout_nonblocking(p)
    return p



#####################################################
# Main

if __name__ == "__main__":

    url = sys.argv[1]
    sys.stderr.write("launched %s with url %s" 
        % (sys.argv[0], sys.argv[1]))
    mplayerIn = os.open(ififo, os.O_WRONLY | os.O_NONBLOCK)
    #mplayerOut = os.open(ofifo, os.O_RDWR | os.O_NONBLOCK)
    p = playurl(url)
    mplayerOut = p.stdout
    sleep(5.0)
    dump_output(mplayerOut)
    get_all_information(mplayerIn, mplayerOut)
    os.close(mplayerIn)
    sleep(10.0)

