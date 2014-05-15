# -- coding: utf-8 --
#!/usr/bin/python3.3 -u

"""
critter.wsgi - a dynamic voting system for playlists

@author: Bryant Hansen
@license: GPLv3
"""

from __future__ import unicode_literals

import sqlite3
import sys
import os
import time
from datetime import datetime, timedelta
import re
from random import randint, choice
import logging
import subprocess

sys.path.append(os.path.dirname(__file__))

import pyplayer

try:
     from io import StringIO
except ImportError:
     from cStringIO import StringIO

try:
     import critter_settings.py
except ImportError:
     pass

from cgi import parse_qs, escape
from traceback import format_exc, print_exc, print_stack
from pprint import pformat

DIR='/var/www/localhost/mod_wsgi'
LOGDIR = '/projects/critter_list/log'
LOGFILE = ("%s/%s.log" % (LOGDIR, 'critter'))

default_url = "player.wsgi"
debuglog = StringIO()

default_sessionId = 123456789
default_voterId = 0
default_playlistId = 1

ONE_MINUTE = 60
FIVE_MINUTES = 300
FIVE_HOURS = 18000
INFINITY = 1000000000
# we will not automatically repeat a song again within this interval, unless
# it's absolutely necessary
MIN_REPEAT_TIME = ONE_MINUTE

#import critter-settings.py


class SessionContext:
    def __init__(
        self,
        sessionId,
        voterId,
        voterName,
        playlistId,
        playlistName,
        environ,
        dbConnection,
        cur,
        url,
        clientWidth,
        clientHeight,
        narrow
    ):
        self.sessionId = sessionId
        self.voterId = voterId
        self.voterName = voterName
        self.playlistId = playlistId
        self.playlistName = playlistName
        self.environ = environ
        self.con = dbConnection
        self.cur = cur
        self.url = url
        self.clientWidth = clientWidth
        self.clientHeight = clientHeight
        self.narrow = narrow

def TRACE(msg):
    m = ("%s: %s" % (datetime.now().strftime("%H:%M:%S.%f")[0:-3], msg))
    debuglog.write(m + "\n")
    logging.info(m)

def dump_todo():
    text = str(
        "<div id='docs_overview' class='docs'>\n"
        "<h3>Overview</h3>\n"
        "<p>This is a web-based application that allows users to vote for tracks in a playlist.</p>\n"
        "<p>Users log in via the browser and can give a &quot;Thumbs-up&quot; or a &quot;Thumbs-down&quot; to the available tracks in the playlist.</p>\n"
        "<p>Each track has a score; tracks with the highest score are played first.</p>\n"
        "</div>\n"
        "<div id='docs_features' class='docs'>\n"
        "<h3>Features</h3>\n"
        "<ul>\n"
        "<li>Allows multiple users to vote on playlist items via the web browser\n"
        "<li>Multi-platform, multi-browser clients (TODO: test & verification; mostly tested under Firefox 24.3.0 for 64-bit Linux)\n"
        "<li>Multiple views of playlists, votes, scores"
        "<li>"
        "</ul>\n"
        "</div>\n"
        "<div id='docs_planned_features' class='docs'>\n"
        "<h3>Planned Features</h3>\n"
        "<ul>\n"
        "<li>Media player integration\n"
        "<li>Playlists taking last-played time into account\n"
        "<li>Session tracking, so that only active sessions have a valid vote; reconnection restores voting record; only those with active, connected sessions influence the voting tally\n"
        "<li>"
        "</ul>\n"
        "</div>\n"
        "<div id='docs_features' class='docs'>\n"
        "<h3>News</h3>\n"
        "<ul>\n"
        "<li>Abandoned MULTIPLE WEB-SERVER COMPATIBILITY feature.  An adaption layer for mod_python to connect to the mostly mod_wsgi-based code.  The feature was nearly complete, but it turned into more code than expected and mod_python is more obsolete than first estimated.  I'm not sure it's likely that it will be ported to python v3\n"
        "</ul>\n"
        "</div>\n"
        "<div id='todo' class='docs'>\n"
        "<h3>TODO</h3>\n"
        "<ul>\n"
        "<li>FIX: admin screen should be updated for smaller displays\n"
        "<li>FIX: the score field on the player page is incorrect; the SQL query must be changed to not count playlistHistory entries\n"
        "<li>PERFORMANCE: terribly-slow with the combination of SSL &amp; the VM; investigate the bottlenecks, which would be related to VirtualBox, Apache, SSL, mod_wsgi or whatever else I'm not aware of\n"
        "<li>MULTIPLE WEB-SERVER COMPATIBILITY: finish the feature to adapt both mod_wsgi with python 3.3 and mod_python with python 2.7\n"
        "<li>LOOK &amp; FEEL: additional skinz to choose from, with config interface to change\n"
        "<li>WIDTH: pass screen width from client and dynamically adjust to it; menu items look terrible when auto-wrapping in small screens right now\n"
        "<li>LIVE UPDATES: Efficient live updates of the tally - do only partial updates\n"
        "<li>COMPLETE SESSION FUNCTIONALITY: Add session functionality; replace ?voterId=NNN url with ?sessionId=NNN\n"
        "<li>EXPIRATION FEATURES: Remove votes from tally that are associated with expired sessions\n"
        "<li>DEPLOYMENT: Safe, secure deployment system in network appliance (make DVD & USB stick versions)\n"
        "<li>ENABLE/DISABLE DEBUG MESSAGES: Turn on and off debug messages from the command line\n"
        "<li>MULTIPLE PLAYLISTS: and a selector for which controls the local audio system\n"
        "<li>MEDIA PLAYER: set up and enable mplayer &amp; mpd controls and create controls on screen\n"
        "<li>ABSTRACTION LAYER FOR SERVER-SIDE API's: Abstraction layer for supporting mod_python and mod_wsgi simultaneously\n"
        "<li>IMPORT: Import direct from filesystem\n"
        "<li>MOBILE PHONE DISPLAY: Fix voting on mobile phones\n"
        "<li>RANDOM ORDER: each user gets a random order of tracks\n"
        "</ul>\n"
        "</div>\n"
    )
    return text

def html_escape(text):
    """Produce entities within text."""
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c,c) for c in text)

def lookup_votername(cur, voterId):
    cur.execute(
        "SELECT id, name FROM voters "
        "WHERE id = '" + str(voterId)  + "'"
    )
    rows = cur.fetchall()
    if len(rows) >= 1:
        return rows[0][1]
    else:
        return ""

def get_playlist_name(cur, playlistId):
    cur.execute(
        "SELECT "
        "playlists.name "
        "FROM tracks "
        "INNER JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "LEFT JOIN playlists ON playlist_tracks.playlist_id = playlists.id "
        "WHERE playlists.id = " + str(playlistId)
    )
    rows = cur.fetchall()
    if len(rows) >= 1:
        return str(rows[1][0])
    else:
        return ""


def add_voter(con, voterName):
    TRACE("adding voter " + voterName + " to db")
    cur = con.cursor()
    cur.execute(
        "INSERT INTO voters (name) VALUES ('" + voterName + "');"
    )
    con.commit()

def lookup_voterId(cur, voterName):
    cur.execute(
        "SELECT id, name FROM voters "
        "WHERE " +
            "name = '" + voterName + "'"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        return 0
    else:
        return rows[0][0]

def random_uppercase_letter():
    return chr(randint(65,65+25))

def invent_random_voter():
    TRACE("inventing random voter")
    return choice([ "Mr. ", "Ms. " ]) + random_uppercase_letter()

def get_client_address(environ):
    try:
        return environ['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()
    except KeyError:
        return environ['REMOTE_ADDR']

def show_env(env, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [
        '%s\r\n\r\nClient Address: %s\r\n' 
        % (pformat(env), get_client_address(env))
        ]

def get_int_param_from_url(urldict, paramName):
    voterId = 0
    vid = urldict.get(paramName,  [''])[0]
    vid = escape(vid)      # Always escape user input to avoid script injection
    if isinstance(vid, str):
        TRACE(
            "get_int_param_from_url: string '%s' specified as '%s'" 
            % (vid, paramName)
            )
        if len(vid) < 1:
            return 0
        try:
            ivid = int(vid)
        except:
            ivid = 0
        #TRACE(
        #   "get_int_param_from_url: returning %d for paramName %s" 
        #   % (ivid, paramName)
        #)
        return ivid
    elif not isinstance(vid, int):
        TRACE(
            "get_int_param_from_url: non-integer '" + str(vid) + 
            "' of type " + str(type(vid)) + 
            " specified as " + paramName)
        return 0
    elif vid > 0:
        TRACE(
            "get_int_param_from_url: %s specified as %d of type %s"
            % (paramName, vid, str(type(vid)))
        )
        return vid
    else:
        return 0

def format_short_string(strin, maxlen = 48):
    s = strin
    if len(strin) < 1:
        return ""
    elif len(strin) > maxlen:
        delim = " ... "
        l = (maxlen - len(delim)) // 2
        s = strin[0:l] + delim + strin[-l:]
        # s += " title='" + strin + "'"
    return s

def get_base_filename_from_env(env, name):
    base_url = ""
    try:
        # default script will be based on name; fallback to HTTP_REFERER
        base_url = env[name].split('?')[0]
    except:
        pass
    base_url = os.path.basename(base_url)
    TRACE("get_base_filename_from_env(%s): returning %s" % (name, base_url))
    return base_url


"""
Figure out who is logged in, so that they don't get a duplicate voter record
and multiple votes

@return: voter name as a string
"""
def discover_voter(env, urldict, con):
    """
    This function must determine some way of finding out if we know this voter
    It currently returns the name, but it should return a valid ID
    """

    voterId = 0
    voterName = ""
    ip = "ip not available"
    mac = "mac not available"

    try:
        ip = get_client_address(env)
        if str(ip) == "::1" or str(ip) == "127.0.0.1" or str(ip) == "localhost":
            mac="01:02:03:04:05:06"
        if (len(ip) > 0):
                arp = tuple(open('/proc/net/arp', 'r'))
                for l in arp:
                    a = l.split()
                    if a[0] == ip:
                        mac = a[3]
                        break
    except:
        e = sys.exc_info()[0]
        TRACE("Exception fetching voter IP & MAC")
        sys.stderr.write(
            "<div id='ERROR'>\n" +
            "<p>Exception in critter.py / vote() - failed to parse vote</p>\n"
            #"<p>" + type(inst) + "</p>\n" +   # the exception instance
            #"<p>" + inst.args + "</p>\n" +    # arguments stored in .args
            #"<p>" + inst + "</p>\n" +         # __str__ allows args to printed directly
            #"<p>sys.exc_info()[0]: " + str(sys.exc_info()[0]) + "</p>\n" +
            "</div>\n"
        )

    TRACE(" voter ip: " + str(ip))
    TRACE(" voter mac: " + str(mac))

    # Returns a dictionary containing lists as values.
    votestr = urldict.get('voterId', [''])[0] # Returns the first voterId value.
    #hobbies = d.get('hobbies', []) # Returns a list of hobbies.

    # Always escape user input to avoid script injection
    voterId = escape(votestr)
    if voterId:
        TRACE("voterId indicated in URL: " + str(voterId))
        voterName = lookup_votername(con.cursor(), voterId)
        if len(voterName) > 0:
            TRACE("voter " + str(voterId) + " exists in db as " + voterName)
        else:
            TRACE("voter not found in voter db for id " + voterId)
            voterId = 0

    # TODO: try to get this from MAC address, IP address, cookie or even sessionId?

    return voterId, voterName

def get_session(cur, voterId):
    cur.execute(
        "SELECT id, name, voterId, ip, mac, starttime, endtime, status"
        "FROM sessions "
        "WHERE voterId = '" + voterId + "' "
        "AND starttime IS NOT NULL "
        "AND endtime IS NULL"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        TRACE("No active session found for voter #%d" % voterId)
        return None
    elif len(rows) > 1:
        TRACE(
            "ERROR: multiple active sessions found for voter #%d.  "
            "Returning last." 
            % voterId
        )
        return rows[0][cur.rowcount]
    else:
        return rows[0][0]
    fi

def new_session(con, voterId):
    cur = con.cursor()
    cur.execute(
        "SELECT files.id, files.filename, votes.voterId, votes.vote "
        "FROM files LEFT JOIN votes "
        "ON files.id = votes.trackId "
        "AND " + str(voterId) + " = votes.voterId"
    )
    rows = cur.fetchall()
    if len(rows) >= 1:
        TRACE(
            "An active session found for voter #" + 
            str(voterId) + " already exists.  "
            "Doing nothing."
        )
        return rows[0][0]
    else:
        cur.execute(
            "INSERT INTO session ("
                "voterId,"
                "trackId,"
                "vote,"
                "votedon"
            ") VALUES ('" + 
                votedict['voterId'] + "', '" + 
                votedict['trackId'] + "', '" + 
                str(ivote) + "', '" + 
                time.strftime("%Y-%m-%dT%H:%M:%S") +
            "');"
        )
        con.commit()

def dump_menuitem(label, url, selection):
    itemClassUnsel="menuitem_unsel"
    itemClassSel="menuitem_sel"

    itemclass=itemClassUnsel
    if label == selection:
        itemclass=itemClassSel
    return (
        "<li class='" + itemclass + "'>"
        "<a class='" + itemclass + "' href='" + url + "'>"
        + label + 
        "</a></li>\n"
    )

def dump_menu(voterId, selection, narrow = False):
    # TODO: change this to sessionId, rather than voterId
    # make a unique session key
    # verify with IP and/or MAC address and/or cookie
    req = StringIO()

    #narrow = True

    itemClassUnsel="menuitem_unsel"
    itemClassSel="menuitem_sel"
    req.write(
        "<div class='menuouter'>\n"
        "<div class='menu'>\n"
        "<ul class='menu'>\n"
    )

    req.write(
        dump_menuitem(
            "ADMIN", "/mod_wsgi/critter.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "PLAYER", "/mod_wsgi/player.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "TRACKS", "/mod_wsgi/tracks.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "VOTES", "/mod_wsgi/votes.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "TALLY", "/mod_wsgi/tally.wsgi?voterId=%d" % (voterId),
            selection
            )
    )

    if narrow:
        req.write(
            "</ul>\n"
            "</div>\n"
            "</div>\n"
            "<div class='menuouter'>\n"
            "<div class='menu'>\n"
            "<ul class='menu'>\n"
        )

    req.write(
        dump_menuitem(
            "STATS", "/mod_wsgi/stats.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "DOCS", "/mod_wsgi/docs.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "CONFIG", "/mod_wsgi/config.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "VISUALS", "/mod_wsgi/visuals.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "ADD TRACKS", "/mod_wsgi/add_track.wsgi?voterId=%d" % (voterId),
            selection
            ) +
        dump_menuitem(
            "LOGOUT", "/mod_wsgi/%s" % (default_url),
            selection
            )
    )

    req.write(
        "</ul>\n"
        "</div>\n"
        "</div>\n"
        "<div class='clearfloat'></div>\n"
    )
    return req.getvalue()

def dump_html_header():
    return (
        "<!DOCTYPE html>\n"
        "<!-- \n"
        "   generated by ${ME} on $(dt)"
        "   (c) Bryant Hansen"
        "   License: GPLv3\n"
        "-->\n"
        "<html>\n"
        "<head>\n"
        "<META HTTP-EQUIV='Content-Type' CONTENT='text/html; charset=ISO-8859-1'>\n"
        "<title>Critter List - a Dechromatic Playlist</title>\n"
        "<LINK REL=StyleSheet HREF='/css/critter.css' TYPE='text/css' MEDIA=screen>\n"
        #"<meta name=HandheldFriendly' content='true' />\n"
        #"<meta name='viewport' content='width=device-width, height=device-height, user-scalable=yes' />\n"
        "<META name='description' content='Critter List'>\n"
        "<META name='keywords' content='Bryant, Hansen, Bryant Hansen, critter'>\n"
        "<script type='text/javascript' src='/js/vote.js'></script>\n"
        "</head>\n"
    )

def dump_html_footer():
    return (
        "</html>\n"
    )

"""
Dump a table that shows all of the available playlists, the currently-selected 
playlist and allows to select an alternate playlist
"""
def dump_playlists_table(sessionContext, admin = False):

    cur = sessionContext.cur
    url = sessionContext.url
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId

    req = StringIO()
    req.write("<table id='table_playlists' class='db_table'>\n")
    cur.execute("SELECT id, name FROM playlists")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr>"
                "<th>No<br />playlists<br />have<br />been<br />registered</th>"
            "</tr>\n"
        )
    else:
        cols = len(rows[0])
        req.write(
            "<tr>"
                "<th class='topheader' colspan='100%'>"
                    "Select Current Playlist"
                "</th>"
            "</tr>\n"
            "<tr>"
        )
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>")
        for row in rows:
            lPlaylistId = row[0]
            selectedPlaylistClass = ""
            if str(playlistId) == str(lPlaylistId):
                selectedPlaylistClass = "class='playlistCell'"
            else:
                selectedPlaylistClass = "class='unSelectedPlaylistCell'"
            req.write(
                    "<tr>"
                        "<td class='%s'>%s</td>"
                        "<td %s>"
                            "<a href='%s?voterId=%d&playlistId=%d'>%s</a>"
                        "</td>\n"
                    % (
                        cur.description[0][0],
                        row[0],
                        selectedPlaylistClass,
                        url,
                        voterId,
                        row[0],
                        row[1]
                    )
            )
            if admin == True:
                req.write(
                    "<td class='%s'>\n"
                        "<img "
                            "class='delete-playlist' "
                            "src='/css/template/close.button.png' "
                            "onclick='delete_playlist(%d, %d, %d)' "
                        "/>\n"
                    "</td>\n"
                    % (cur.description[0][1], sessionId, voterId, lPlaylistId)
                )
            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_settings_table(sessionContext, admin = False):
    req = StringIO()
    req.write(
        "<table id='table_settings' class='db_table'>\n"
        "<tr>\n"
            "<th class='topheader' colspan='100%'>\n"
                "Settings\n"
            "</th>\n"
        "</tr>\n"
        "<tr>\n"
            "<th>Name</th><th>Value</th>\n"
        "</tr>\n"
    )
    req.write(
        "<tr>"
            "<td>%s</td>"
            "<td>%d seconds</td>"
        "</tr>\n"
        "</table>\n"
        % (
            "MIN_REPEAT_TIME",
            MIN_REPEAT_TIME
        )
    )
    return req.getvalue()

def dump_voters_table(sessionContext, admin = False):

    cur = sessionContext.cur
    url = sessionContext.url
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId

    req = StringIO()
    req.write("<table id='table_voters' class='db_table'>\n")
    cur.execute("SELECT id, name FROM voters")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write (
            "<tr><th>\n"
                "No<br />\n"
                "voters<br />\n"
                "have<br />\n"
                "been<br />\n"
                "registered\n"
            "</th></tr>\n"
        )
    else:
        cols = len(rows[0])
        req.write(
            "<tr>\n"
                "<th class='topheader' colspan='100%'>Voters</th>\n"
            "</tr>\n"
            "<tr>"
        )
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>")
        for row in rows:
            lVoterId = row[0]
            selectedVoterClass = ""
            if voterId == lVoterId:
                selectedVoterClass = "class='voterCell'"
            else:
                selectedVoterClass = "class='unSelectedVoterCell'"
            req.write(
                    "<tr>"
                        "<td class='id'>%03d</td>"
                        "<td %s>"
                            "<a href='%s?voterId=%d'>%s</a>"
                        "</td>\n"
                    % (
                        lVoterId,
                        str(selectedVoterClass),
                        url,
                        row[0],
                        row[1]
                    )
            )
            if admin == True:
                req.write(
                    "<td class='delete-voter'>\n"
                        "<img "
                            "class='delete-voter' "
                            "src='/css/template/close.button.png' "
                            "onclick='delete_voter(%d, %d, %d)' "
                        "/>\n"
                    "</td>\n"
                    % (sessionId, voterId, lVoterId)
                )
            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_tracks_table(sessionContext, admin = False, controls = False):

    env = sessionContext.environ
    cur = sessionContext.cur
    url = sessionContext.url
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId
    narrow = sessionContext.narrow
    currentTrackUrl = ""

    req = StringIO()

    TRACE(
        "dump_tracks_table: voterId = %d, playlistId = %d"
        % (voterId, playlistId)
    )
    req.write("<table id='table_tracks' class='db_table'>\n")
    if (voterId == 0):
        req.write(
            "<tr>"
                "<td>"
                    "ERROR: voterId is null.<br />"
                    "Vote selection is dependent on voterId."
                "</td>"
            "</tr>\n"
        )
    else:
        cur.execute(
            "SELECT "
                "tracks.id AS id, "
                "ltrim(urls.rpath, '.') AS filename, "
                "votes.voterId, "
                "votes.vote, "
                "tracks.title AS title, "
                "artists.name AS artist, "
                "albums.name AS album "
            "FROM playlist_tracks "
            "LEFT JOIN tracks ON tracks.id = playlist_tracks.track_num "
            "LEFT JOIN urls ON tracks.url = urls.id "
            "LEFT JOIN votes "
                "ON tracks.id = votes.trackId AND votes.voterId = '%s' "
            "LEFT JOIN artists ON tracks.artist = artists.id "
            "LEFT JOIN albums ON tracks.album = albums.id "
            "WHERE playlist_tracks.playlist_id = '%s' "
            "ORDER BY playlist_tracks.id "
            "LIMIT 500 " %
            (str(voterId), str(playlistId))
        )
        rows = cur.fetchall()
        if len(rows) < 1:
            req.write("<tr><th>No tracks are available</th></tr>\n")
        else:
            cols = len(rows[0])
            req.write(
                "<tr><th class='topheader' colspan='100%'>Tracks</th></tr>\n"
                "<tr>"
            )
            if narrow:
                req.write(
                    "<th rowspan='2' class='subheader'>Title /\n"
                    "Artist /\n"
                    "Album /\n"
                    "Filename</th>\n"
                )
            else:
                req.write(
                    "<tr><th colspan='100%'>Tracks</th></tr>\n"
                    "<tr>"
                    "<th rowspan='2'>Title</th>\n"
                    "<th rowspan='2'>Artist</th>\n"
                    "<th rowspan='2'>Album</th>\n"
                    "<th rowspan='2'>filename</th>\n"
                )
            req.write(
                "<th colspan='2' class='subheader'>Votes</th>\n"
                "</tr>\n"
                "<tr>\n"
                "<th class='subheader'>Yae</th>\n"
                "<th class='subheader'>Nay</th>\n"
                "</tr>\n"
            )
            currentTrackUrl = str(rows[0][1])
            for row in rows:
                trackId = str(row[0])
                filename = str(row[1])
                trackvoterId = str(row[2])
                vote = str(row[3])
                title = str(row[4])
                artist = str(row[5])
                album = str(row[6])
                filename = os.path.basename(filename)
                if len(title) < 1:
                    title = filename
                if len(artist) < 1:
                    artist = "&lt;artist unknown&gt;"
                if len(album) < 1:
                    album = "&lt;album unknown&gt;"
                if len(filename) > 48:
                    filename = filename[1:24] + " ... " + filename[-24:]

                if narrow:
                    req.write(
                        "<tr><td class='track_info'>"
                        "<span class='title'>%s</span><br />\n"
                        "&nbsp;&nbsp;%s<br />\n"
                        "&nbsp;&nbsp;%s<br />\n"
                        "&nbsp;&nbsp;%s</td>\n" %
                        (title, artist, album, filename)
                    )
                else:
                    req.write(
                        "<tr>"
                        "<td class='track_info'>"
                        "<span class='title'>%s</span>"
                        "</td>\n"
                        "<td>%s</td>\n"
                        "<td>%s</td>\n"
                        "<td>%s</td>\n" %
                        (title, artist, album, filename)
                    )

                vote_yae_class = "vote"
                vote_nay_class = "vote"
                if str(trackvoterId) == str(voterId):
                    if vote == "1" or vote == "yae":
                        vote_yae_class = "votedyae"
                    if vote == "0" or vote == "nay":
                        vote_nay_class = "votednay"

                vote_yae_function = (
                    "vote_yae(%s, %s, %s, \"%s\")"
                    % (sessionId, trackId, voterId, html_escape(filename))
                )
                vote_nay_function = (
                    "vote_nay(%s, %s, %s, \"%s\")"
                    % (sessionId, trackId, voterId, html_escape(filename))
                )

                req.write(
                    "<td class='%s' onclick='%s'>\n"
                        "<a id='track_%s_yae' class='votedyae'>\n"
                            "<img src='/css/template/up_arrow2.png' />"
                        "</a>"
                    "</td>\n"
                    "<td class='%s' onclick='%s'>\n"
                        "<a id='track_%s_nay' class='votednay'>\n"
                            "<img src='/css/template/down_arrow2.png' />"
                        "</a>"
                    "</td>\n"
                    % (
                        vote_yae_class, vote_yae_function, trackId,
                        vote_nay_class, vote_nay_function, trackId
                       )
                )
                if admin == True:
                    req.write(
                        "<td class='delete-voter'>\n"
                            "<img "
                                "class='delete-voter' "
                                "src='/css/template/close.button.png' "
                                "onclick='delete_track(%s, %s, %s)' "
                            "/>\n"
                        "</td>\n" 
                        % (sessionId, voterId, trackId)
                    )
                if controls == True:
                    req.write(
                        "<td class='controls'>\n"
                            "<img "
                                "class='controls' "
                                "src='/css/template/play.png' "
                                "alt='PL' "
                                "onclick='play(%d, %d)' "
                            "/>\n" 
                        "</td>\n"
                        % ( sessionId, voterId )
                    )
                req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_sessions_table(cur, admin = False):
    req = StringIO()
    req.write("<table id='table_sessions' class='db_table'>\n")
    cur.execute("SELECT name FROM sessions")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr><th class='topheader'>Sessions</th></tr>\n"
            "<tr>"
                "<td>No<br />sessions<br />have<br />been<br />registered</td>"
            "</tr>\n"
        )
    else:
        cols = len(rows[0])
        req.write("<tr><th colspan='%d'>Sessions</th></tr>\n" % cols)
        req.write("<tr>\n")
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>\n")
        for row in rows:
            req.write("<tr>\n")
            for col in range(cols):
                req.write("<td class='%s'>%s</td>\n"
                    % str(cur.description[col][0]), str(row[col])
                )
            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_votes_table(sessionContext, admin = False):
    cur = sessionContext.cur
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId
    narrow = sessionContext.narrow

    req = StringIO()
    req.write("<table id='table_votes' class='db_table'>\n")
    cur.execute(
        "SELECT "
            "votes.id AS id, "
            "votes.vote, "
            "tracks.title AS title, "
            "artists.name AS artist, "
            "albums.name AS album, "
            "voters.name, "
            "votes.votedon, "
            "ltrim(urls.rpath, '.') AS filename "
        "FROM votes "
        "LEFT JOIN tracks ON votes.trackId = tracks.id "
        "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "JOIN voters ON votes.voterId = voters.id "
        "LEFT JOIN urls ON tracks.url = urls.id "
        "LEFT JOIN artists ON tracks.artist = artists.id "
        "LEFT JOIN albums ON tracks.album = albums.id "
        "WHERE playlist_tracks.playlist_id = '%d' "
        "ORDER BY votes.votedon DESC "
        "LIMIT 500 " % sessionContext.playlistId
    )

    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr>\n"
                "<th>No<br />votes<br />have<br />been<br />registered</th>\n"
            "</tr>\n"
        )
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th class='topheader' colspan='100%'>Votes</th></tr>\n"
            "<tr>\n"
        )
        if narrow:
            for col in range(1, cols):
                colname = str(cur.description[col][0])
                if colname == 'title':
                    req.write(
                        "<th class='subheader'>Title /\n"
                        "Artist /\n"
                        "Album /\n"
                        "Filename</th>\n"
                    )
                elif       colname == 'artist' \
                        or colname == 'album' \
                        or colname == 'filename':
                    pass
                else:
                    req.write("<th class='subheader'>%s</th>\n" % colname)
        else:
            for col in range(1, cols):
                req.write(
                    "<th class='subheader'>%s</th>\n"
                    % str(cur.description[col][0])
                )
        req.write("</tr>\n")
        for row in rows:
            vote = row[1]
            title = row[2]
            artist = row[3]
            album = row[4]
            votername = row[5]
            datetime = row[6]
            filename = row[7]

            if str(vote) == '1' or str(vote) == 'yae':
                req.write("<tr class='yaevote'>\n")
            elif str(vote) == '0' or str(vote) == 'nay':
                req.write("<tr class='nayvote'>\n")
            else:
                req.write("<tr>\n")

            if len(title) < 1:
                title = filename
            if len(artist) < 1:
                artist = "&lt;artist unknown&gt;"
            if len(album) < 1:
                album = "&lt;album unknown&gt;"

            filename = str(filename)
            filename = os.path.basename(filename)
            if len(filename) > 48:
                filename = filename[1:24] + " ... " + filename[-24:]

            for col in range(1, cols):
                colname = str(cur.description[col][0])
                if row[col] == None:
                    req.write("<td>&nbsp;\n")
                else:
                    if colname == 'filename':
                        if not narrow:
                            req.write("<td>%s" % filename)
                    elif colname == 'title':
                        title = str(title)
                        title = os.path.basename(title)
                        if len(title) > 48:
                            title = title[1:24] + " ... " + title[-24:]
                        if narrow:
                            req.write(
                                "<td class='title'>\n"
                                "<span class='title'>%s</span><br />\n"
                                "&nbsp;&nbsp;%s<br />\n"
                                "&nbsp;&nbsp;%s<br />\n"
                                "&nbsp;&nbsp;%s<br />\n"
                                "</td>\n" %
                                (title, artist, album, filename)
                            )
                        else:
                            req.write("<td class='%s'>%s" 
                                % (cur.description[col][0], title))
                    elif colname == 'artist':
                        if not narrow:
                            req.write("<td>%s" % artist)
                    elif colname == 'album':
                        if not narrow:
                            req.write("<td>%s" % album)
                    elif colname == 'votedon':
                        req.write("<td class='%s'>" % colname)
                        datetime = str(row[col])
                        if narrow:
                            datetime = datetime.replace(" ","<br />", 1)
                        datetime = datetime.replace("T","<br />", 1)
                        req.write(datetime)
                    elif colname == 'vote':
                        if str(row[col]) == '1' or str(row[col]) == 'yae':
                            req.write(
                                "<td class='yaevote'>"
                                "<img src='/css/template/thumbs_up.png' />"
                            )
                        elif str(row[col]) == '0' or str(row[col]) == 'nay':
                            req.write(
                                "<td class='nayvote'>"
                                "<img src='/css/template/thumbs_down.png' />"
                            )
                        else:
                            req.write(
                                "<td class='%s'>%s"
                                % (colname, str(row[col]))
                            )
                    elif colname == 'name':
                        req.write(
                            "<td class='voter'>" +
                            str(row[col])
                        )
                    else:
                        req.write(
                            "<td class='%s'>%s"
                            % (colname, str(row[col]))
                        )
                if not narrow:
                    req.write("</td>\n")
                else:
                    if  colname != 'title' and \
                        colname != 'artist' and \
                        colname != 'album' and \
                        colname != 'filename':
                        req.write("</td>\n")
            if admin == True:
                voteId = row[0]
                req.write(
                    "<td class='delete-vote'>\n"
                    "<img "
                        "class='delete-vote' "
                        "src='/css/template/close.button.png' "
                        "onclick='delete_vote(%d, %d, %d)' "
                    "/>\n"
                    "</td>\n"
                    % ( sessionId, voterId, voteId )
                )
            req.write("</tr>\n")
    req.write("</table>\n")

    return req.getvalue()

def dump_tally_table(cur, playlistId, narrow = True):
    req = StringIO()

    req.write("<table id='table_tally' class='db_table'>\n")
    # major query: this is where the magic happens
    # this retreives the tally, including the score/ranking of every song
    cur.execute(
        "SELECT "
            "( "
            "    COUNT(CASE WHEN vote = '1' THEN vote END) "
            "  - COUNT(CASE WHEN vote = '0' THEN vote END) "
            ") AS score, "
            "COUNT(CASE when vote = '1' THEN vote END) AS yaes, "
            "COUNT(CASE when vote = '0' THEN vote END) AS nahs, "
            "tracks.title AS title, "
            "artists.name AS artist, "
            "albums.name AS album, "
            "ltrim(urls.rpath, '.') AS filename "
        "FROM votes "
        "JOIN tracks ON votes.trackId = tracks.id "
        "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "JOIN voters ON votes.voterId = voters.id "
        "LEFT JOIN urls ON tracks.url = urls.id "
        "LEFT JOIN artists ON tracks.artist = artists.id "
        "LEFT JOIN albums ON tracks.album = albums.id "
        "WHERE playlist_tracks.playlist_id = '%d' "
        "GROUP BY tracks.id "
        "ORDER BY score DESC, yaes "
        "LIMIT 500 "
        ";"
        % playlistId
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No tracks are available</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr>"
                "<th class='topheader' colspan='%d'>Tally</th>"
            "</tr>\n"
            "<tr>\n"
            % cols
        )
        for col in range(cols):
            heading = str(cur.description[col][0])
            if narrow:
                if heading == 'title':
                    req.write(
                        "<th class='subheader'>"
                            "Title / Artist / Album / Filename"
                        "</th>\n"
                    )
                elif heading == 'artist' or \
                    heading == 'yaes' or \
                    heading == 'nahs' or \
                    heading == 'album' or \
                    heading == 'filename':
                        pass
                else:
                   req.write(
                       "<th class='subheader'>%s</th>\n"
                       % str(cur.description[col][0])
                    )
            else:
                req.write(
                    "<th class='subheader'>%s</th>\n"
                    % str(cur.description[col][0])
                )
        req.write("</tr>\n")
        for row in rows:
            # TODO: convert this to dictionary
            score = str(row[0])
            yaes = str(row[1])
            nays = str(row[2])
            title = str(row[3])
            artist = str(row[4])
            album = str(row[5])
            filename = str(row[6])

            filename = format_short_string(os.path.basename(filename))

            if len(title) < 1:
                title = filename
            if len(artist) < 1:
                artist = "&lt;artist unknown&gt;"
            if len(album) < 1:
                album = "&lt;album unknown&gt;"

            req.write("<tr>\n")
            for col in range(cols):
                colname = str(cur.description[col][0])
                if narrow:
                    if colname == 'title':
                        req.write(
                            "<td class='title_narrow'>"
                            "<span class='title'>%s</span><br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s</td>\n" %
                            (title, artist, album, filename)
                        )
                    elif colname == 'score':
                        req.write("<td class='score'><span class='score'>")
                        if len(score) < 1:
                            req.write("&nbsp;\n")
                        else:
                            # TODO: consider converting database results to
                            #       dict objects
                            req.write(
                                "%s </span><br /> %s yaes <br /> %s nahs" 
                                % (score, yaes, nays)
                            )
                        req.write("</td>\n")
                    elif colname == 'artist' or \
                         colname == 'album' or \
                         colname == 'yaes' or \
                         colname == 'nahs' or \
                         colname == 'filename':
                            pass
                    else:
                        req.write("<td>")
                        s = str(row[col])
                        if len(s) < 1:
                            req.write("&nbsp;\n")
                        else:
                            req.write(s)
                        req.write("</td>\n")
                else:
                    req.write("<td>")
                    s = str(row[col])
                    if len(s) < 1:
                        req.write("&nbsp;\n")
                    else:
                        if colname == 'title':
                            req.write(title)
                        elif colname == 'filename':
                            req.write(filename)
                        elif colname == 'artist':
                            req.write(artist)
                        elif colname == 'album':
                            req.write(album)
                        else:
                            req.write(s)
                    req.write("</td>\n")


            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def get_next_track(cur, playlistId):

    next_track_dict = { 
            'score': "",
            'filename': "",
            'yaes': "",
            'nays': "",
            'title': "",
            'artist': "",
            'album': "",
            'last_played': "",
            'time_since_played': "",
            'trackId': ""
    }
    # major query: this is where the magic happens
    # this retreives the tally, including the score/ranking of every song
    cur.execute(
        "SELECT "
            "( "
            "    COUNT(CASE WHEN vote = '1' THEN vote END) "
            "  - COUNT(CASE WHEN vote = '0' THEN vote END) "
            ") AS score, "
            "COUNT(CASE when vote = '1' THEN vote END) AS yaes, "
            "COUNT(CASE when vote = '0' THEN vote END) AS nahs, "
            "tracks.title AS title, "
            "artists.name AS artist, "
            "albums.name AS album, "
            "ltrim(urls.rpath, '.') AS filename, "
            "IFNULL(MAX(playhistory.playedOn), 'never') AS last_played, "
            "CAST("
            "IFNULL( "
            "    strftime('%%s','now') "
            " -  strftime('%%s', SUBSTR(MAX(playhistory.playedOn), 1, 19)) "
            ", 1000000000"
            ") "
            "AS Integer) "
            "AS time_since_played, "
            "tracks.id AS trackId, "
            "strftime('%%s','now') AS now "
        "FROM votes "
        "JOIN tracks ON votes.trackId = tracks.id "
        "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "JOIN voters ON votes.voterId = voters.id "
        "LEFT JOIN urls ON tracks.url = urls.id "
        "LEFT JOIN artists ON tracks.artist = artists.id "
        "LEFT JOIN albums ON tracks.album = albums.id "
        "LEFT JOIN playhistory ON playhistory.trackid = tracks.id "
        "WHERE playlist_tracks.playlist_id = '%d' "
        "GROUP BY tracks.id "
        "ORDER BY score DESC, yaes "
        "LIMIT 1000 "
        ";"
        % playlistId
    )
    row = cur.fetchone()
    if not row:
        TRACE("get_next_track: No Tracks Found\n")
    else:
        while row:
            time_since_played = str(row[8])
            filename = str(row[6])
            now = str(row[10])
            TRACE(
                "get_next_track: time_since_played = %s, now = %s\n"
                % (str(time_since_played), now)
            )
            if int(time_since_played) > MIN_REPEAT_TIME:
                score = str(row[0])
                yaes = str(row[1])
                nays = str(row[2])
                title = str(row[3])
                artist = str(row[4])
                album = str(row[5])
                last_played = str(row[7])
                trackId = str(row[9])
                next_track_dict = {
                    'score': score,
                    'filename': filename,
                    'yaes': yaes,
                    'nays': nays,
                    'title': title,
                    'artist': artist,
                    'album': album,
                    'last_played': last_played,
                    'time_since_played': time_since_played,
                    'trackId': trackId
                }
                TRACE(
                    "get_next_track: returning %s, now = %s, last_played = %s"
                    % (filename, now, last_played)
                )
                break
            else:
                TRACE(
                    "get_next_track: %s was played within the last %d seconds.  "
                    "Trying next..."
                    % (filename, MIN_REPEAT_TIME)
                )
            row = cur.fetchone()
            if not row:
                TRACE("get_next_track: end of records")

    TRACE("next_track_dict: %s" % str(next_track_dict))
    return next_track_dict

def dump_playlist_table(sessionContext):
    currentTrackUrl = ""
    req = StringIO()

    sessionId = sessionContext.sessionId
    voterId =  sessionContext.voterId
    cur = sessionContext.cur
    playlistId = sessionContext.playlistId
    env = sessionContext.environ
    narrow = sessionContext.narrow

    # major query: this is where the magic happens
    # this retreives the tally, including the score/ranking of every song
    # Note: the playlistHistory join corrupts the COUNT
    # This may need to be a sub-query
    try:
        cur.execute(
            "SELECT "
                "( "
                "    COUNT(CASE WHEN vote = '1' THEN vote END) "
                "  - COUNT(CASE WHEN vote = '0' THEN vote END) "
                ") AS score, "
                "COUNT(CASE when vote = '1' THEN vote END) AS yaes, "
                "COUNT(CASE when vote = '0' THEN vote END) AS nahs, "
                "tracks.title AS title, "
                "artists.name AS artist, "
                "albums.name AS album, "
                "ltrim(urls.rpath, '.') AS filename, "
                "IFNULL(MAX(playhistory.playedon), 'never') AS last_played, "
                "IFNULL( "
                "    strftime('%%s','now') "
                " -  strftime('%%s', SUBSTR(MAX(playhistory.playedOn), 1, 19)) "
                ", 1000000000"
                ") "
                "AS time_since_played "
            "FROM votes "
            "JOIN tracks ON votes.trackId = tracks.id "
            "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
            "JOIN voters ON votes.voterId = voters.id "
            "LEFT JOIN urls ON tracks.url = urls.id "
            "LEFT JOIN artists ON tracks.artist = artists.id "
            "LEFT JOIN albums ON tracks.album = albums.id "
            "LEFT JOIN playhistory ON playhistory.trackid = tracks.id "
            "WHERE "
            "   playlist_tracks.playlist_id = '%s' "
            "GROUP BY tracks.id "
            "ORDER BY score DESC, yaes "
            "LIMIT 10 "
            ";"
            % str(playlistId)
        )
        """
            "AND "
            "   time_since_played > '18000 "
            "AND "
            "   CAST(time_since_played as integer) > 18000 "
                ", strftime('%%s','now') AS now,"
                ", strftime('%%s', SUBSTR(MAX(playhistory.playedOn), 1, 19)) as last_played_seconds "
        """
    except:
        e = sys.exc_info()[0]
        TRACE("dump_playlist_table: Exception running " + str(sys.argv[0]))
        print_exc(file=env['wsgi.errors'])
        return str(sys.exc_info()[0]) + "\n" + format_exc(10)

    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<table id='table_playlist' class='db_table'>\n"
            "<tr><th>No playlists are available</th></tr>\n"
        )
    else:
        first = True
        second = True
        req.write("<table id='table_playlist' class='db_table'>\n")
        currentTrackUrl = str(rows[0][6])
        for row in rows:
            score = str(row[0])
            yaes = str(row[1])
            nays = str(row[2])
            title = str(row[3])
            artist = str(row[4])
            album = str(row[5])
            filename = str(row[6])
            last_played = str(row[7])
            time_since_played = str(row[8])
            #now = str(row[9])
            now = ""
            #last_played_seconds = row[10]
            last_played_seconds = ""

            if  int(time_since_played) < 0 \
            or (int(time_since_played) == 0 and time_since_played != "0"):
                TRACE(
                    "FAILED TO RETRIEVE time_since_played: %s for file %s"
                    % (time_since_played, filename)
                )
            elif int(time_since_played) <= MIN_REPEAT_TIME:
                TRACE(
                    "%s has been played %s seconds ago.  Skipping"
                    % (title, time_since_played)
                )
                continue

            t = int(time_since_played)
            # TRACE("dump_playlist_table: time since played = %d" % t)
            if t >= INFINITY:
                time_since_played_string = 'never'
            else:
                time_since_played_string = timedelta(seconds=int(time_since_played))


            if first:
                cols = len(rows[0])
                req.write(
                    "<tr class='playlist_heading'>\n"
                        "<th class='topheader' colspan='100%'>\n"
                            "Now Playing\n"
                        "</th>\n"
                    "</tr>\n"
                    "<tr class='up'>\n"
                        "<td>\n"
                )
                if len(title) < 1:
                    title = "&lt;Unknown Title&gt;"

                # format strings
                # title = format_short_string(os.path.basename(title))
                artist = format_short_string(artist)
                album = format_short_string(os.path.basename(album))
                basefilename = os.path.basename(filename)
                basefilename = format_short_string(basefilename)

                if last_played != 'never':
                    last_played = last_played.replace('T', '  ', 1) + " GMT"

                time_since_played_string = str(time_since_played_string)
                time_since_played_string = time_since_played_string.replace (':', ' hrs, ', 1)
                time_since_played_string = time_since_played_string.replace ('0 hrs, ', '', 1)
                time_since_played_string = time_since_played_string.replace (':', ' min, ', 1)
                time_since_played_string += " sec"

                req.write(
                    "<p class='playlist_title'>%s</p>"
                    "&nbsp;&nbsp;Artist: %s"
                    "<br />&nbsp;&nbsp;Album: %s"
                    "<br />&nbsp;&nbsp;Filename: %s\n"
                    "<br />&nbsp;&nbsp;Score: %s (%s Yaes, %s Nahs)\n"
                    "<br />&nbsp;&nbsp;Last Played: %s GMT\n"
                    "<br />&nbsp;&nbsp;Time Since Last Played: %s "
                    "</td>\n"
                    "</tr>\n"
                    "<tr class='playlist_heading'>"
                        "<td colspan='100%%'>\n"
                            "<div class='controls'>\n"
                                "<img "
                                    "class='controls' "
                                    "src='/css/template/play-previous.png' "
                                    "alt='PL' "
                                "/>\n"
                                "<img "
                                    "class='controls' "
                                    "src='/css/template/play.png' "
                                    "alt='PL' "
                                    "onclick='play(%d, %d)' "
                                "/>\n"
                                "<img "
                                    "class='controls' "
                                    "src='/css/template/play-next.png' "
                                    "alt='PL' "
                                "/>\n"
                            "</div>\n"
                        "</td>\n"
                    "</tr>\n"
                    "</table>\n"
                    "<table id='table_playlist' class='db_table'>\n"
                    "<tr>"
                    "<th class='topheader' colspan='100%%'>Upcoming Tracks</th>"
                    "</tr>\n"
                    "<tr>\n"
                    % (
                        title,
                        artist,
                        album,
                        basefilename,
                        score,
                        yaes,
                        nays,
                        last_played,
                        time_since_played_string,
                        sessionId,
                        voterId
                    )
                )
                for col in range(cols):
                    heading = str(cur.description[col][0])
                    heading = heading.replace('_', ' ')
                    if narrow:
                        if heading == 'title':
                            req.write(
                                "<th class='subheader'>"
                                    "Title / Artist / Album / Filename"
                                "</th>\n"
                            )
                        elif heading == 'artist' or \
                            heading == 'yaes' or \
                            heading == 'nahs' or \
                            heading == 'album' or \
                            heading == 'filename':
                            pass
                        else:
                            req.write(
                                "<th class='subheader'>%s</th>\n"
                                % (heading)
                            )
                    else:
                        req.write(
                            "<th class='subheader'>%s</th>\n"
                            % (heading)
                        )
            else:
                # not first; this is the following table of upcoming tracks
                req.write("<tr>\n")
                title = format_short_string(title)
                artist = format_short_string(artist)
                album = format_short_string(album)
                filename = format_short_string(os.path.basename(filename))
                for col in range(cols):
                    if narrow:
                        if str(cur.description[col][0]) == 'title':
                            req.write(
                                "<td class='title_narrow'>"
                                    "<span class='title'>%s</span><br />\n"
                                    "&nbsp;&nbsp;%s<br />\n"
                                    "&nbsp;&nbsp;%s<br />\n"
                                    "&nbsp;&nbsp;%s"
                                "</td>\n" %
                                (title, artist, album, filename)
                            )
                        elif str(cur.description[col][0]) == 'score':
                            req.write("<td class='score'><span class='score'>")
                            if len(score) < 1:
                                req.write("&nbsp;\n")
                            else:
                                req.write(
                                    "%s </span><br /> %s yaes <br /> %s nahs" 
                                    % (score, yaes, nays)
                                )
                            req.write("</td>\n")
                        elif str(cur.description[col][0]) == 'artist' or \
                            str(cur.description[col][0]) == 'album' or \
                            str(cur.description[col][0]) == 'yaes' or \
                            str(cur.description[col][0]) == 'nahs' or \
                            str(cur.description[col][0]) == 'filename':
                                pass
                        elif str(cur.description[col][0]) == 'last_played':
                            if last_played == None:
                                last_played = 'never'
                            if last_played != 'never':
                                last_played = last_played.replace(
                                                            'T', '<br />', 1
                                                        ) + " GMT"
                            req.write(
                                "<td class='%s'>%s</td>"
                                % (str(cur.description[col][0]), last_played)
                            )
                        elif str(cur.description[col][0]) == 'time_since_played':
                            time_since_played_string = \
                                            str(time_since_played_string) \
                                            + " seconds"
                            time_since_played_string = \
                                            time_since_played_string.replace(
                                                ':', ' hours<br />', 1
                                            )
                            # tip on how to do an efficient, single-pass
                            # multi-string replace:
                            # http://emilics.com/blog/article/multi_replace.html
                            rdict = {
                                 '01 hours<br />': '01 hour<br />',
                                              ':': ' minutes<br />',
                               '01 minutes<br />': '01 minute<br />',
                               '01 seconds<br />': '01 second<br />',
                                             ', ': '<br />',
                                        '<br />0': '<br />'
                            }
                            robj = re.compile('|'.join(rdict.keys()))
                            time_since_played_string = robj.sub (
                                lambda m: rdict[m.group(0)],
                                time_since_played_string
                            )
                            req.write(
                                "<td class='%s'>%s</td>"
                                % (
                                    str(cur.description[col][0]),
                                    time_since_played_string
                                )
                            )
                        else:
                            req.write(
                                "<td class='%s'>"
                                % str(cur.description[col][0])
                            )
                            s = str(row[col])
                            if len(s) < 1:
                                req.write("&nbsp;\n")
                            else:
                                req.write(s)
                            req.write("</td>\n")
                    else:
                        req.write("<td class='%s'>" % cur.description[col][0])
                        if row[col] == None:
                            req.write("&nbsp;\n")
                        else:
                            s = str(row[col])
                            if str(cur.description[col][0]) == 'filename':
                                filename = os.path.basename(s)
                                filename = format_short_string(filename)
                                req.write(filename)
                            else:
                                req.write(s)
                        req.write("</td>\n")
            req.write("</tr>\n")
            first = False
    req.write("</table>\n")
    return req.getvalue()

def dump_misc_stats(cur, playlistId):
    req = StringIO()

    req.write("<table class='misc_stats'><tr><td>\n")
    req.write("<table class='misc_stats_inner'>\n")

    cur.execute(
        "SELECT "
        "COUNT(tracks.id), "
        "playlists.name "
        "FROM tracks "
        "INNER JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "LEFT JOIN playlists ON playlist_tracks.playlist_id = playlists.id"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr>\n"
                "<td colspan='2'>\n"
                    "Could not count the number of tracks in the playlist\n"
                "</td>\n"
            "</tr>\n"
        )
    else:
        req.write(
            "<tr>\n"
                "<th class='misc_stats_label'>Playlist name:</th>\n"
                "<td class='misc_stats_value'>%s</td>\n"
            "</tr>\n"
            "<tr>\n"
                "<th class='misc_stats_label'>"
                    "Number of tracks in playlist:"
                "</th>\n"
                "<td class='misc_stats_value'>%s</td>\n"
            "</tr>\n"
            % (str(rows[0][1]), str(rows[0][0]))
        )

    cur.execute("SELECT COUNT(id) FROM votes ")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr>\n"
                "<td class='misc_stats_value' colspan='2'>"
                    "Could not count the number of votes cast"
                "</td>\n"
            "</tr>\n"
        )
    else:
        answer = rows[0][0]
        req.write(
            "<tr>\n"
                "<th class='misc_stats_label'>Number of votes cast:</th>\n"
                "<td class='misc_stats_value'>%s</td>\n"
            "</tr>\n"
            % answer
        )
    cur.execute("SELECT COUNT(id) FROM tracks ")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write(
            "<tr>\n"
                "<td class='misc_stats_value' colspan='2'>"
                    "Could not count the number of tracks"
                "</td>\n"
            "</tr>\n"
        )
    else:
        answer = rows[0][0]
        req.write(
            "<tr>\n"
                "<th class='misc_stats_label'>"
                    "Number of tracks available: "
                "</th>\n"
                "<td class='misc_stats_value'>%s</td>\n"
            "</tr>\n"
            % answer
        )

    req.write("</table>\n")
    req.write("</td></tr></table>\n")
    return req.getvalue()

def dump_winners_table(cur, playlistId, numrecords = 0, narrow = True):
    req = StringIO()
    req.write("<table class='winners'>\n")
    recordLimit = ""
    if (numrecords > 0):
        recordLimit = "LIMIT " + str(numrecords)
    cur.execute(
        # major query: this is where the magic happens
        # this retreives the tally, including the score/ranking of every song
        "SELECT "
            "( "
            "    COUNT(CASE WHEN vote = '1' THEN vote END) "
            "  - COUNT(CASE WHEN vote = '0' THEN vote END) "
            ") AS score, "
            "COUNT(CASE when vote = '1' THEN vote END) AS yaes, "
            "COUNT(CASE when vote = '0' THEN vote END) AS nahs, "
            "tracks.title AS title, "
            "artists.name AS artist, "
            "albums.name AS album, "
            "ltrim(urls.rpath, '.') AS filename "
        "FROM votes "
        "JOIN tracks ON votes.trackId = tracks.id "
        "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "JOIN voters ON votes.voterId = voters.id "
        "LEFT JOIN urls ON tracks.url = urls.id "
        "LEFT JOIN artists ON tracks.artist = artists.id "
        "LEFT JOIN albums ON tracks.album = albums.id "
        "WHERE playlist_tracks.playlist_id = '%d' "
        "GROUP BY tracks.id "
        "ORDER BY score DESC, yaes "
        "%s;"
        % (playlistId, recordLimit)
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No tracks are available</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th colspan='100%'>Biggest Winners</th></tr>\n"
            "<tr>\n"
        )
        for col in range(cols):
            heading = str(cur.description[col][0])
            if narrow:
                if heading == 'title':
                    req.write("<th>Title / Artist / Album / Filename</th>\n")
                elif heading == 'artist' or \
                    heading == 'yaes' or \
                    heading == 'nahs' or \
                    heading == 'album' or \
                    heading == 'filename':
                    pass
                else:
                    req.write("<th>%s</th>\n" % heading)
            else:
                req.write("<th>%s</th>\n" % heading)
        req.write("</tr>\n")
        for row in rows:
            if row[2] == 0 and row[3] == 0:
                continue
            req.write("<tr>\n")
            for col in range(cols):
                if narrow:
                    score = str(row[0])
                    yaes = str(row[1])
                    nays = str(row[2])
                    title = format_short_string(str(row[3]))
                    artist = format_short_string(str(row[4]))
                    album = format_short_string(str(row[5]))
                    filename = str(row[6])
                    basefilename = os.path.basename(filename)
                    basefilename = format_short_string(basefilename)
                    if str(cur.description[col][0]) == 'title':
                        req.write(
                            "<td class='title_narrow'>"
                            "<span class='title'>%s</span><br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s</td>\n" %
                            (title, artist, album, basefilename)
                        )
                    elif str(cur.description[col][0]) == 'score':
                        # TODO: make this more pythonic, with % args in strings
                        #       and conditional args
                        req.write("<td class='score'><span class='score'>")
                        if len(score) < 1:
                            req.write("&nbsp;\n")
                        else:
                            req.write(
                                "%s </span><br /> %s yaes <br /> %s nahs"
                                % (score, yaes, nays)
                            )
                        req.write("</td>\n")
                    elif str(cur.description[col][0]) == 'artist' or \
                        str(cur.description[col][0]) == 'album' or \
                        str(cur.description[col][0]) == 'yaes' or \
                        str(cur.description[col][0]) == 'nahs' or \
                        str(cur.description[col][0]) == 'filename':
                        pass
                    else:
                        req.write("<td>")
                        s = str(row[col])
                        if len(s) < 1:
                            req.write("&nbsp;\n")
                        else:
                            req.write(s)
                        req.write("</td>\n")
                else:
                    s = str(row[col])
                    if len(s) < 1:
                        s = "&nbsp;\n"
                    elif cur.description[col][0] == 'filename':
                        filename = os.path.basename(s)
                        basefilename = os.path.basename(filename)
                        basefilename = format_short_string(basefilename)
                        s = basefilename
                    req.write(
                        "<td class='%s'>%s</td>\n" % 
                        (cur.description[col][0], s)
                    )
            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_losers_table(cur, playlistId, numrecords = 0, narrow = True):
    req = StringIO()
    req.write("<table class='losers'>\n")
    recordLimit = ""
    if (numrecords > 0):
        recordLimit = "LIMIT " + str(numrecords)
    cur.execute(
        # major query: this is where the magic happens
        # this retreives the tally, including the score/ranking of every song
        "SELECT "
            "( "
            "    COUNT(CASE WHEN vote = '1' THEN vote END) "
            "  - COUNT(CASE WHEN vote = '0' THEN vote END) "
            ") AS score, "
            "COUNT(CASE when vote = '1' THEN vote END) AS yaes, "
            "COUNT(CASE when vote = '0' THEN vote END) AS nahs, "
            "tracks.title AS title, "
            "artists.name AS artist, "
            "albums.name AS album, "
            "ltrim(urls.rpath, '.') AS filename "
        "FROM votes "
        "JOIN tracks ON votes.trackId = tracks.id "
        "LEFT JOIN playlist_tracks ON tracks.id = playlist_tracks.track_num "
        "JOIN voters ON votes.voterId = voters.id "
        "LEFT JOIN urls ON tracks.url = urls.id "
        "LEFT JOIN artists ON tracks.artist = artists.id "
        "LEFT JOIN albums ON tracks.album = albums.id "
        "WHERE playlist_tracks.playlist_id = '%d' "
        "GROUP BY tracks.id "
        "ORDER BY score, nahs "
        "%s;"
        % (playlistId, recordLimit)
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No tracks are available</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th colspan='100%'>Biggest Losers</th></tr>\n"
            "<tr>\n"
        )
        for col in range(cols):
            heading = str(cur.description[col][0])
            if narrow:
                if heading == 'title':
                    req.write("<th>Title / Artist / Album / Filename</th>\n")
                elif heading == 'artist' or \
                    heading == 'yaes' or \
                    heading == 'nahs' or \
                    heading == 'album' or \
                    heading == 'filename':
                    pass
                else:
                    req.write("<th>%s</th>\n" % heading)
            else:
                req.write("<th>%s</th>\n" % heading)
        req.write("</tr>\n")
        for row in rows:
            if row[2] == 0 and row[3] == 0:
                # if there's been neither yaes or nahs, then it's no point
                # reporting them here
                continue
            req.write("<tr>\n")
            for col in range(cols):
                if narrow:
                    score = str(row[0])
                    yaes = str(row[1])
                    nays = str(row[2])
                    title = format_short_string(str(row[3]))
                    artist = format_short_string(str(row[4]))
                    album = format_short_string(str(row[5]))
                    filename = str(row[6])
                    basefilename = os.path.basename(filename)
                    basefilename = format_short_string(basefilename)
                    if str(cur.description[col][0]) == 'title':
                        req.write(
                            "<td class='title_narrow'>"
                            "<span class='title'>%s</span><br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s<br />\n"
                            "&nbsp;&nbsp;%s</td>\n" %
                            (title, artist, album, basefilename)
                        )
                    elif str(cur.description[col][0]) == 'score':
                        req.write("<td class='score'><span class='score'>")
                        if len(score) < 1:
                            req.write("&nbsp;\n")
                        else:
                            req.write(
                                "%s </span><br /> %s yaes <br /> %s nahs" 
                                % (score, yaes, nays)
                            )
                        req.write("</td>\n")
                    elif str(cur.description[col][0]) == 'artist' or \
                        str(cur.description[col][0]) == 'album' or \
                        str(cur.description[col][0]) == 'yaes' or \
                        str(cur.description[col][0]) == 'nahs' or \
                        str(cur.description[col][0]) == 'filename':
                        pass
                    else:
                        req.write("<td>")
                        s = str(row[col])
                        if len(s) < 1:
                            req.write("&nbsp;\n")
                        else:
                            req.write(s)
                        req.write("</td>\n")
                else:
                    s = str(row[col])
                    if len(s) < 1:
                        s = "&nbsp;\n"
                    else:
                        if cur.description[col][0] == 'filename':
                            s = os.path.basename(s)
                        s = format_short_string(s)
                    req.write(
                        "<td class='%s'>%s</td>\n" % 
                        (cur.description[col][0], s)
                    )
            req.write("</tr>\n")
    req.write("</table>\n")
    return req.getvalue()

def dump_playlist_div(sessionContext):
    return (
        "<div id='div_playlist'>\n" +
        dump_playlist_table(sessionContext) +
        "</div>\n"
    )

def dump_tracks_div(cur, sessionId, voterId, playlistId, controls = False):
    return (
        "<div id='div_tracks' class='db_table'>\n" +
        dump_tracks_table(cur, sessionId, voterId, playlistId, controls) +
        "</div>\n"
    )

def dump_config_div(sessionContext):
    return (
        dump_playlists_table(sessionContext) +
        dump_settings_table(sessionContext) +
        "<H3 class='todo'>TODO: add wide/narrow view and other settings</H3>\n"
    )

def dump_debug_div(env, cur):
    env_formatted = ['%s: %s' % (key, value)
                    for key, value in sorted(env.items())]
    env_formatted = '\n'.join(env_formatted)
    python_module = "mod_python"
    return (
        "<div class='clearfloat'></div>\n"
        "<div class='debug_outer'>\n"
        "<div class='debug_container'>\n"
        "<h3 class='debug'>Debugging Info</h3>\n"
        "<h4 id='debugTextboxLabel'>%s Debug Messages</h4>\n"
        "<TEXTAREA id='pyDebugTextbox' rows='20' cols='80'>\n"
        "%s\n"
        "</TEXTAREA>\n"
        "<H4 id='debugTextboxLabel'>Javascript Debug Messages</H4>\n"
        "<TEXTAREA id='jsDebugTextbox' rows='20' cols='80'>\n"
        "</TEXTAREA>\n"
        "<H4>Environment Variables</H4>\n"
        "<p>type(env) = '%s'</p>"
        "<TEXTAREA id='pyDebugTextbox' rows='20' cols='80'>\n"
        "%s\n"
        "</TEXTAREA>\n"
        "</div>\n"
        "</div>\n"
        % (
            python_module,
            str(debuglog.getvalue()),
            escape(str(type(env))),
            env_formatted
        )
    )

def dump_login_div(env, url, con):
    voterName = invent_random_voter()
    TRACE(
        "dump_login_div: random voter name: '%s'.  TODO: discovery" 
        % voterName
        )
    return (
        "<div id='div_login' class='login'>\n"
        "<form action='%s' method='POST'>\n"
        "<p class='login'>"
        "Name: "
        "<input "
            "name='loginname' "
            "id='loginname' "
            "type='text' "
            "size='30' "
            "maxlength='30' "
            "value='%s'"
        ">\n"
        "<input type='submit' name='Enter' value='Enter List'>"
        "</p>\n"
        "<script type='text/javascript'>\n"
            "loginInputObj = document.getElementById('loginname');"
            "if (loginInputObj) {"
                "loginInputObj.select();"
            "}\n"
        "</script>\n"
        "</form>\n"
        "<p class='instructions'>"
            "Please enter a name to be associated with your votes"
        "</p>\n"
        "</div>\n" 
        % (url, voterName)
    )

def dump_vote_tables(sessionContext, admin = False, controls = False):

    url = sessionContext.url
    cur = sessionContext.cur
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId

    sessionContext.narrow = True

    TRACE("dump_vote_tables: "
        "url = " + str(url) + 
        ", sessionId = " + str(sessionId) + 
        ", voterId = " + str(voterId) + 
        ", playlistId = " + str(playlistId))

    return (
        "<div id='div_tables'>\n"

        "<div id='div_voters' class='db_table'>\n" +
        dump_voters_table(sessionContext, admin) +
        "</div>\n"

        "<div id='sessions' class='db_table'>\n" +
        dump_sessions_table(cur, admin) +
        "</div>\n"

        "<div id='div_tracks' class='db_table'>\n" +
        dump_tracks_table(sessionContext, admin, controls) +
        "</div>\n"

        "<div id='div_votes' class='db_table'>\n" +
        dump_votes_table(sessionContext, admin) +
        "</div>\n"

        "<div id='div_tally' class='db_table'>\n" +
        dump_tally_table(cur, playlistId) +
        "</div>\n"

        "</div>\n"
        )

def dump_body_header(voterId, voterName, playlistName):
    return (
        "<body onLoad='loadPage()'>"
        "<div class='hideoverflow'>\n"
        "<div class='outer'>\n"
        "<div class='body'>\n"
        "<table id='table_header'>"
        "<tr>"
        "<td class='logo'>"
        "<a href='/mod_wsgi/critter.wsgi?voterId=%d'>"
        "<img class='logo' src='/css/template/logo/r169_457x256_12869_Critters_3d_fantasy_creatures_picture_image_digital_art.jpg.33.jpg' />"
        "</a>\n"
        "</td>"
        "<td class='header'>"
        "<h1>Critter List</h1>\n"
        "<h3>Welcome, %s!</h3>\n"
        "<h3>Playlist: &quot;%s&quot;</h3>\n"
        "</td>"
        "</tr>\n"
        "</table>\n"
        % (voterId, voterName, playlistName)
    )

def dump_body_login_header():
    return (
        "<body onLoad='loadPage()'>\n"
        "<div class='hideoverflow'>\n"
        "<div class='outer'>\n"
        "<div class='loginbody'>\n"
        "<table id='table_header'>\n"
        "<tr>\n"
        "<td class='logo'>"
        "<a class='logo' href='/mod_wsgi/critter.wsgi'>"
        "<img class='logo' src='/css/template/logo/r169_457x256_12869_Critters_3d_fantasy_creatures_picture_image_digital_art.jpg.33.jpg' />"
        "</a>"
        "</td>\n"
        "<td class='header'>\n"
        "<h1>Critter List</h1>\n"
        "<h3>Welcome!</h3>\n"
        "</td>\n"
        "</tr>\n"
        "</table>\n"
    )

def dump_body_footer():
    return (
        "</div>\n"
        "</div>\n"
        "</div>\n"
        "<div class='outer'>\n"
        "<div id='div_footer' class='copyright'>\n"
        "<p class='footer'>Generated on %s</p>\n"
        "<p class='copyright'>(c)2014 Bryant Hansen</p>\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        % time.strftime("%Y-%m-%d %H:%M:%S %Z")
    )

def dump_login_page(env, url, con):
    TRACE("dump_login_page: url = %s" % url)
    return (
        dump_html_header() +
        dump_body_login_header() +
        dump_login_div(env, url, con) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_admin_page(sessionContext):
    TRACE("dump_admin_page: "
        "url = %s, sessionId = %d, voterId = %d, playlistId = %d"
        % (
            sessionContext.url,
            sessionContext.sessionId,
            sessionContext.voterId,
            sessionContext.playlistId
        )
    )
    sessionContext.narrow = True
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId, 
            voterName, 
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "ADMIN") +
        dump_vote_tables(sessionContext, admin = True) +
        dump_debug_div(sessionContext.environ, sessionContext.cur) +
        dump_body_footer() +
        dump_html_footer()
    )

UNKNOWN_NAME = "<unknown>"
def dump_tracks_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_tracks_page: voterId = %d, voterName = '%s', playlistId = '%d'"
        % (
            sessionContext.voterId,
            sessionContext.voterName,
            sessionContext.playlistId
        )
    )
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "TRACKS") +
        dump_tracks_table(sessionContext, admin = False, controls = False) +
        dump_debug_div(sessionContext.environ, sessionContext.cur) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_player_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(
                        sessionContext.cur, 
                        sessionContext.voterId
                    )
    # TODO: consider sanity-check of voterName/voterId
    TRACE(
        "dump_player_page: voterId = %d, voterName = '%s'"
        % (sessionContext.voterId, sessionContext.voterName)
    )
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "PLAYER") +
        dump_playlist_div(sessionContext) +
        dump_debug_div(sessionContext.environ, sessionContext.cur) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_debug_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE(
            "dump_debug_page: voterId = %d, voterName = '%s'" 
            % (sessionContext.voterId, sessionContext.voterName)
    )
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(voterId, "DEBUG") +
        dump_debug_div(sessionContext.environ, sessionContext.cur) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_docs_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    TRACE(
            "dump_docs_page: voterId = %d, voterName = '%s'" 
            % (sessionContext.voterId, voterName)
    )
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "DOCS") +
        dump_todo() +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_votes_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    TRACE(
            "dump_votes_page: voterId = %d, voterName = '%s'" 
            % (sessionContext.voterId, sessionContext.voterName)
    )
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "VOTES") +
        dump_votes_table(sessionContext) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_config_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_config_page: voterId = " + str(sessionContext.voterId) + ", voterName = '" + sessionContext.voterName + "'")
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "CONFIG") +
        dump_config_div(sessionContext) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_visuals_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_visuals_page: voterId = " + str(sessionContext.voterId) + ", voterName = '" + sessionContext.voterName + "'")
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "VISUALS") +
        "<H3 class='todo'>TODO: make visuals_page</H3>\n" +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_add_track_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_add_track_page: voterId = " + str(sessionContext.voterId) + ", voterName = '" + sessionContext.voterName + "'")
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "ADD TRACKS") +
        "<H3 class='todo'>TODO: make add_track page</H3>\n" +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_tally_page(sessionContext):
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(sessionContext.cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_tally_page: voterId = " + str(sessionContext.voterId) + ", voterName = '" + sessionContext.voterName + "'")
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "TALLY") +
        dump_tally_table(sessionContext.cur, sessionContext.playlistId, narrow = sessionContext.narrow) +
        dump_debug_div(sessionContext.environ, sessionContext.cur) +
        dump_body_footer() +
        dump_html_footer()
    )

def dump_stats_page(sessionContext):
    cur = sessionContext.cur
    voterName = sessionContext.voterName
    if len(voterName) < 1:
        voterName = lookup_votername(cur, sessionContext.voterId)
    # TODO: consider sanity-check of voterName/voterId
    TRACE("dump_stats_page: voterId = " + str(sessionContext.voterId) + ", voterName = '" + voterName + "', playlistId = '" + str(sessionContext.playlistId) + "'")
    return (
        dump_html_header() +
        dump_body_header(
            sessionContext.voterId,
            voterName,
            sessionContext.playlistName
        ) +
        dump_menu(sessionContext.voterId, "STATS") +
        dump_misc_stats(cur, sessionContext.playlistId) +
        dump_winners_table(cur, sessionContext.playlistId, 10, narrow = sessionContext.narrow) +
        dump_losers_table(cur, sessionContext.playlistId, 10, narrow = sessionContext.narrow) +
        dump_body_footer() +
        dump_html_footer()
    )

def is_valid(con, voteStr, voterStr, trackStr, sessionStr, playlistStr):
    try:
        voterId = int(voterStr)
    except:
        voterId = 0
    try:
        trackId = int(trackStr)
    except:
        trackId = 0
    try:
        sessionId = int(sessionStr)
    except:
        sessionId = 0
    try:
        playlistId = int(playlistStr)
    except:
        playlistId = 0

    if voteStr != "yae" and voteStr != "nay":
        TRACE("invalid vote (must be 'yae' or 'nay'): %s" % voteStr)
        return False
    if voterId <= 0:
        TRACE("invalid voter Id: " + str(voterStr))
        return False
    if trackId <= 0:
        TRACE("invalid track Id: " + str(trackStr))
        return False
    #if sessionId <= 0:
    #    TRACE("invalid session Id: " + vote)
    #    return False
    #if playlistId <= 0:
    #    TRACE("invalid playlist Id: " + vote)
    #    return False

    return True

def do_delete_voter(sessionContext, deletee):
    env = sessionContext.environ
    url = sessionContext.url
    con = sessionContext.con
    sessionId = sessionContext.sessionId
    playlistId = sessionContext.playlistId
    deleter = sessionContext.voterId

    if deleter == deletee:
        TRACE("WARNING: you are committing suicide! ;)")
        deleter = 0
    sql = ("DELETE FROM voters " + 
                "WHERE "
                    "id = '" + str(deletee) + "';")
    TRACE(sql)
    con.cursor().execute(sql)
    con.commit()

    testurl = url.split(".")[0]
    TRACE("url = " + url)
    if testurl == "tracks":
        return dump_tracks_table(sessionContext, admin = True, controls = False)
    elif testurl == "critter":
        if deleter == 0:
            return ""
        else:
            return dump_vote_tables(sessionContext, True)
    else:
        return dump_vote_tables(sessionContext, True)

def do_delete_vote(sessionContext, voteId):

    env = sessionContext.environ
    con = sessionContext.con
    url = sessionContext.url
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId

    TRACE("do_delete_vote: "
        "url = " + str(url) + 
        ", sessionId = " + str(sessionId) + 
        ", voterId = " + str(voterId) + 
        ", voteId = " + str(voteId) + 
        ", playlistId = " + str(playlistId))
    sql = ("DELETE FROM votes " + 
                "WHERE "
                    "id = '" + str(voteId) + "';")
    TRACE(sql)
    con.cursor().execute(sql)
    con.commit()

    testurl = url.split(".")[0]
    TRACE("url = " + url)
    if testurl == "tracks":
        return dump_tracks_table(sessionContext, admin = True, controls = False)
    elif testurl == "critter":
        return dump_vote_tables(sessionContext, True)
    else:
        return dump_vote_tables(sessionContext, True)

def do_delete_track(sessionContext, trackId):

    env = sessionContext.environ
    url = sessionContext.url
    con = sessionContext.con
    sessionId = sessionContext.sessionId
    playlistId = sessionContext.playlistId
    deleter = sessionContext.voterId

    TRACE("do_delete_track: "
        "url = " + str(url) + 
        ", sessionId = " + str(sessionId) + 
        ", trackId = " + str(trackId) + 
        ", playlistId = " + str(playlistId))
    sql = ("DELETE FROM playlist_tracks " + 
                "WHERE "
                    "playlist_id = '" + str(playlistId) + 
                    "' AND track_num = '" + str(trackId) + "';")
    TRACE(sql)
    con.cursor().execute(sql)
    con.commit()

    testurl = url.split(".")[0]
    TRACE("AJAX response for url '" + url + "'")
    if testurl == "tracks":
        return dump_tracks_table(sessionContext, admin = True, controls = False)
    elif testurl == "critter":
        return dump_vote_tables(sessionContext, True)
    else:
        return dump_vote_tables(sessionContext, True)


def do_player_command(sessionContext):

    env = sessionContext.environ
    url = sessionContext.url
    con = sessionContext.con
    sessionId = sessionContext.sessionId
    voterId = sessionContext.voterId
    playlistId = sessionContext.playlistId
    deleter = sessionContext.voterId

    cur = con.cursor()

    # check for command

    # if play
        # check state if already playing
        # get next track

    # update last played

    # start player

    # setup callback for finish

    # finish callback
        # update played-track status (finished ok)
        # find and play next track

    # TODO: consider launching mplayer in thread
        # bullet-proof code to limit the number of instances that can be launched (at least 2 should be allowed for optional crossfade)

    #TRACE(sql)
    #con.cursor().execute(sql)
    #con.commit()

    TRACE("enter do_player_command  url = '%s', voterId = %d" % (url, voterId))
    urldict = parse_qs(env['QUERY_STRING'])
    TRACE("do_player_command: env(QUERY_STRING) = " + env['QUERY_STRING'] + 
          ", urldict = " + str(urldict))

    # this is the extra params on the URL after the question mark (?)
    # as is conventional, each param is delimited by the ampersand (&)
    # Returns a dictionary containing lists as values.

    # command=play&sessionId=123456789&voterId=2&width=2560&height=1265&page=/mod_wsgi/player.wsgi
    command    = urldict.get('command',    [''])[0]
    command    = escape(command)          # Always escape user input to avoid script injection
    sessionId = urldict.get('sessionId',  [''])[0]
    sessionId = escape(sessionId)       # Always escape user input to avoid script injection
    voterId = urldict.get('voterId',  [''])[0]
    voterId = escape(voterId)       # Always escape user input to avoid script injection
    TRACE(
        "do_player_command: command = %s, sessionId = %s, voterId = %s"
        % (command, sessionId, voterId)
    )

    if command == 'play':
        # get the current state (playing/paused/stopped)
        # get the track to be played
        # get the set up the command to play the track
        # check the status that it started ok
        # update the database
        # - previous track status
        # - current track status

        # get the track to be played
        track = get_next_track(cur, playlistId)
        trackId = 0
        filename = ""
        try:
            trackId = int(track['trackId'])
        except:
            pass
        try:
            filename = track['filename']
        except:
            pass
        if trackId >= 1:
            TRACE("do_player_command: next track Id = %s" % str(trackId))

            # update the database
            # - current track status
            # sqlite has no zoneinfo handling; all times are in GMT/UTC
            # limited time formats are supported by sqlite; select one that's
            # ISO 8601-compatible (see: http://www.w3.org/TR/NOTE-datetime)
            timestr = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

            # alternative methods:
            #   timestr = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            #   timestr = datetime.now('GMT').strftime("%Y-%m-%dT%H:%M:%S")
            try:
                TRACE(
                    "do_player_command: updating play history: "
                    "track = %s, playedOn = %s" 
                    % (str(trackId), timestr)
                )
                cur.execute(
                    "INSERT INTO playhistory ("
                        "trackId, "
                        "playedOn"
                        ") "
                    "VALUES (%s, '%s');"
                    % (str(trackId), timestr)
                )
                con.commit()
            except:
                e = sys.exc_info()[0]
                TRACE(
                    "do_player_command: Exception running %s" 
                    % str(sys.argv[0])
                )
                print_exc(file=env['wsgi.errors'])
                return str(sys.exc_info()[0]) + "\n" + format_exc(10)
            try:
                TRACE(
                    "do_player_command: attempting to play %s via pyplayer..."
                    % filename
                )
                pyplayer.playurl(filename)
            except:
                e = sys.exc_info()[0]
                TRACE(
                    "do_player_command: Exception running pyplayer.playurl(%s)" 
                    % filename
                )
                print_exc(file=env['wsgi.errors'])
                return str(sys.exc_info()[0]) + "\n" + format_exc(10)
        else:
            TRACE("do_player_command ERROR: get_next_track failed.  "
                  "No track ID")

    testurl = url.split(".")[0]
    TRACE("do_player_command: AJAX response for url '" + url + "'")
    if testurl == "tracks":
        return dump_tracks_table(sessionContext, admin = True, controls = False)
    elif testurl == "critter":
        return dump_vote_tables(sessionContext, True)
    elif testurl == "player":
        TRACE("player response: dump_playlist_div('" + url + "')")
        return dump_playlist_div(sessionContext)
    else:
        return dump_vote_tables(sessionContext, True)


"""
AJAX request - do_vote
returns one or more html tables, but not an entire page
"""
def do_vote(sessionContext):

    env = sessionContext.environ
    url = sessionContext.url
    con = sessionContext.con
    sessionId = sessionContext.sessionId
    playlistId = sessionContext.playlistId
    voterId = sessionContext.voterId

    TRACE("enter do_vote  url = " + str(url) + ", voterId = " + str(voterId))

    urldict = parse_qs(env['QUERY_STRING'])
    TRACE("do_vote: env(QUERY_STRING) = " + env['QUERY_STRING'] + 
          ", urldict = " + str(urldict))

    # this is the extra params on the URL after the question mark (?)
    # as is conventional, each param is delimited by the ampersand (&)
    # Returns a dictionary containing lists as values.

    vote    = urldict.get('vote',    [''])[0]
    vote    = escape(vote)          # Always escape user input to avoid script injection
    voterId = urldict.get('voterId',  [''])[0]
    voterId = escape(voterId)       # Always escape user input to avoid script injection
    trackId = urldict.get('trackId', [''])[0]
    trackId = escape(trackId)       # Always escape user input to avoid script injection

    if vote == "yae" or vote == "nay":
        if vote == "yae":
            ivote = 1
        elif vote == "nay":
            ivote = 0
        else:
            TRACE("ERROR: critter.py: vote of " + str(vote) + " not understood")
            ivote = -1

    # sanity check
    if is_valid(con, vote, voterId, trackId, sessionId, 1):
        TRACE("vote = " + str(urldict))
        cur = con.cursor()
        cur.execute(
            "SELECT id, trackId, voterId, vote "
            "FROM votes "
            "WHERE " +
                "voterId = '" + str(voterId)  + "' AND " +
                "trackId = '" + str(trackId)     + "';"
        )
        rows = cur.fetchall()
        if len(rows) < 1:
            # no records exist matching the voterId and the trackId
            #pass
            try:
                cur.execute(
                    "INSERT INTO votes ("
                        "voterId, "
                        "trackId, "
                        "vote, "
                        "votedon"
                        ") "
                    "VALUES ('" + 
                        str(voterId) + "', '" + 
                        str(trackId) + "', '" + 
                        str(ivote) + "', '" + 
                        time.strftime("%Y-%m-%dT%H:%M:%S") +
                    "');"
                )
            except:
                e = sys.exc_info()[0]
                TRACE("Exception running " + str(sys.argv[0]))
                print_exc(file=environ['wsgi.errors'])
                return str(sys.exc_info()[0]) + "\n" + format_exc(10)
        else:
            db_vote = str(rows[0][3])
            TRACE("do_vote: str(vote) = %s, str(db_vote)=%s" % (str(vote), str(db_vote)))
            if str(ivote) == db_vote:
                sql = ("DELETE FROM votes " + 
                            "WHERE "
                                "voterId = '" + str(voterId) + "' AND "
                                "trackId = '" + str(trackId) + "';")
                TRACE(sql)
                cur.execute(sql)
            else:
                sql = ( "UPDATE votes "   + 
                            "SET vote = '"    + str(ivote) + 
                            "', votedon = '"  + time.strftime("%Y-%m-%dT%H:%M:%S") + "' "
                            "WHERE "
                                "voterId = '" + str(voterId) + "' AND "
                                "trackId = '" + str(trackId) + "';")
                TRACE(sql)
                cur.execute(sql)

        con.commit()

        pagename = os.path.basename(url)
        pagename = pagename.split('.')[0]
        TRACE("pagename = " + pagename + ", url = " + url)
        if pagename == "tracks":
            return dump_tracks_table(sessionContext, admin = False, controls = False)
        elif pagename == "critter":
            return dump_vote_tables(sessionContext, admin = True)
        else:
            return dump_vote_tables(sessionContext, admin = True)
    else:
        TRACE("ERROR: is_valid failed.  The vote appears to be invalid.  Not counting.")
        return "ERROR: is_valid failed.  The vote appears to be invalid.  Not counting."


def get_login_from_env(env):
    loginname = ""
    try:
        a = env['wsgi.input'].read()
        b = parse_qs(a)
        c = b[b'loginname']
        d = c[0].decode('utf-8')
        loginname = d
    except KeyError:
        TRACE("exception referencing dict element loginname")

    # Always escape user input to avoid script injection
    # TODO: figure how how to insert this prior to parsing
    loginname = escape(loginname)

    if len(loginname) > 0:
        TRACE("loginname: " + repr(loginname))
    else:
        TRACE("loginname not specified")
    return loginname

def get_or_add_voter(con, environ, voterName):
    TRACE("get_or_add_voter: voterName = " + voterName)
    cur = con.cursor()
    voterId = 0
    if len(voterName) > 0:
        TRACE("login name specified in environment: " + voterName)
        voterId = lookup_voterId(cur, voterName)
        if voterId > 0:
            TRACE("voterId for " + voterName + " is found as " + str(voterId))
            vn = lookup_votername(cur, voterId)
            if vn != voterName:
                TRACE(
                    "PROGRAM ERROR: DB did not return the same login name "
                    "as was just created.  created = "
                    + str(voterName) + ", returned = "
                    + str(vn))
        else:
            TRACE("no voterId found for voter " + voterName)
            add_voter(con, voterName)
            voterId = lookup_voterId(cur, voterName)
            if voterId <= 0:
                TRACE(
                    "get_or_add_voter  ERROR: failed to create voter record for " + 
                    voterName
                )

    sVoterId = get_int_param_from_url(environ, 'voterId')
    if sVoterId > 0:
        voterId = sVoterId
        TRACE("voterId indicated in URL: " + str(voterId))

        vn = lookup_votername(cur, voterId)
        if len(voterName) > 0 and vn != voterName:
            TRACE(
                "PROGRAM ERROR: voterId specified in URL as " 
                + str(sVoterId) + " This is associated with voter " 
                + str(vn) + 
                " but voterName " 
                + str(voterName) + 
                " specified"
            )

        voterName = lookup_votername(cur, voterId)
        if len(voterName) > 0:
            TRACE("voter " + str(voterId) + " exists in db as " + voterName)
        else:
            TRACE("voter not found in voter db for id " + voterId)
            voterId = 0

    if len(voterName) <= 0:
        add_voter(con, voterName)

    voterId = lookup_voterId(cur, voterName)
    if voterId > 0:
        TRACE("get_or_add_voter: voterId for " + voterName + 
              " is found as " + str(voterId))
    return voterId, voterName


def dump_environ(environ):
    for attr in dir(environ):
        try:
            if str(attr) == "__doc__": continue
            TRACE("environ.%s = '%s'" % (attr, getattr(environ, attr)))
        except:
            # TRACE("Exception running: " + str(sys.exc_info()[0]) + "\n" + str(format_exc(10)))
            pass


######################
# Main (mod_wsgi)
def application(environ, start_response):

    logging.basicConfig(filename=LOGFILE, level=logging.DEBUG)

    sessionId = default_sessionId
    voterId = default_voterId
    playlistId = default_playlistId

    TRACE("os.path.dirname(__file__) = %s" % os.path.dirname(__file__))
    DIR = os.path.dirname(__file__)
    try:
        os.chdir(DIR)
    except:
        TRACE(
            "Failed to change current dir to %s; let's see what happens.  "
            "curdir = %s"
            % (DIR, os.getcwd())
        )

    dbConnection = sqlite3.connect('critters.db')
    dbConnection.text_factory = sqlite3.OptimizedUnicode
    cur = dbConnection.cursor()

    urldict = parse_qs(environ['QUERY_STRING'])
    TRACE(
        "env(QUERY_STRING) = %s , urldict = %s"
        % (environ['QUERY_STRING'], str(urldict))
    )

    sid = get_int_param_from_url(urldict, 'sessionId')
    if isinstance(sid, str):
        sid = 0
    if sid > 0:
        TRACE("application: overriding sessionId %d "
              "with url-specified %d"
              % (sessionId, sid)
        )
        sessionId = sid

    pid = get_int_param_from_url(urldict, 'playlistId')
    if isinstance(pid, str):
        pid = 0
    if pid > 0:
        TRACE("application: overriding playlistId %d "
              "with url-specified %d"
              % (sessionId, sid)
        )
        playlistId = pid

    try:
        # SCRIPT_FILENAME: /var/www/localhost/htdocs/mod_wsgi/critter.wsgi
        # parse from SCRIPT_FILENAME vs REQUEST_URI?
        # HTTP_REFERRER seems to stay current and not updated by the AJAX call
        # we want the base script here
        # SCRIPT_FILENAME must be used after a logout, to restore the default page on login

        script = get_base_filename_from_env(environ, 'SCRIPT_FILENAME')
        referrer =  get_base_filename_from_env(environ, 'HTTP_REFERER')

        voterId = 0
        voterName = ""

        # loginname may come from a POST request (from the login page) indicating the name
        # voterId may come from url line ?voterId=NNN
        # if both arrive, verify that there is not a conflict

        loginname = get_login_from_env(environ)
        urlVoterId = get_int_param_from_url(urldict, 'voterId')
        TRACE("urlVoterId = %s" % str(urlVoterId))
        if len(loginname) > 0:
            voterId, voterName = get_or_add_voter(dbConnection, environ, loginname)
            if urlVoterId > 0 and urlVoterId != voterId:
                TRACE(
                    "application ERROR: voterId = %d"
                    " for voterName '%s'"
                    ", urlVoterId = '%d'"
                    ".  No error handler.  proceeding with voterId %d"
                    % (voterId,  voterName , urlVoterId, voterId)
                )
                voterId = 0
            TRACE(
                "application: voterId = %d, voter lookup: %s" 
                % (voterId, voterName)
            )
        elif urlVoterId > 0:
            voterName = lookup_votername(cur, urlVoterId)
            if len(voterName) < 1:
                TRACE("application ERROR: no voter found for voterId %d" % urlVoterId)
                voterId = 0
            else:
                voterId = urlVoterId
                TRACE("application: voterId = %d, voter lookup: %s" % (voterId, voterName))
        else:
            TRACE(
                "application: no login name specified and no login ID found.  urlVoterId = %d" 
                % urlVoterId
            )

        if environ['REQUEST_METHOD'] == 'POST':
            TRACE("POST DETECTED!")

        playlistName = get_playlist_name(cur, playlistId)

        defaultClientWidth = 1024
        defaultClientHeight = 768

        clientWidth = defaultClientWidth
        clientHeight = defaultClientHeight

        width = get_int_param_from_url(urldict, 'width')
        if width > 0:
            clientWidth = width
            TRACE("width set on command line as %d" % width)

        height = get_int_param_from_url(urldict, 'height')
        if height > 0:
            clientHeight = height
            TRACE("height set on command line as %d" % height)

        narrow = True

        sessionContext = SessionContext(
                                sessionId = sessionId,
                                voterId = voterId,
                                voterName = voterName,
                                playlistId = playlistId,
                                playlistName = playlistName,
                                environ = environ,
                                dbConnection = dbConnection,
                                cur = cur,
                                url = script, 
                                clientWidth = clientWidth,
                                clientHeight = clientHeight,
                                narrow = narrow
                            )

        content_type = 'text/html'
        if voterId <= 0:
            output = dump_login_page(environ, script, dbConnection)
            status = '200 OK' 
        elif script == "critter.wsgi" or script == "admin.wsgi":
            output = dump_admin_page(sessionContext)
            status = '200 OK' 
        elif script == "playlist.wsgi" or  script == "player.wsgi":
            output = dump_player_page(sessionContext)
            status = '200 OK' 
        elif script == "tracks.wsgi" or  script == "files.wsgi":
            output = dump_tracks_page(sessionContext)
            status = '200 OK' 
        elif script == "debug.wsgi":
            output = dump_debug_page(sessionContext)
            status = '200 OK' 
        elif script == "docs.wsgi":
            output = dump_docs_page(sessionContext)
            status = '200 OK' 
        elif script == "votes.wsgi":
            output = dump_votes_page(sessionContext)
            status = '200 OK' 
        elif script == "tally.wsgi":
            output = dump_tally_page(sessionContext)
            status = '200 OK' 
        elif script == "stats.wsgi":
            # output = dump_stats_page(sessionContext)
            output = dump_stats_page(sessionContext)
            status = '200 OK' 
        elif script == "config.wsgi":
            output = dump_config_page(sessionContext)
            status = '200 OK' 
        elif script == "visuals.wsgi":
            output = dump_visuals_page(sessionContext)
            status = '200 OK' 
        elif script == "add_track.wsgi":
            output = dump_add_track_page(sessionContext)
            status = '200 OK' 
        elif script == "logout.wsgi":
            output = dump_login_page(sessionContext)
            status = '200 OK' 

        # AJAX requests
        elif script == "vote.wsgi" or script == "vote.py":
            sessionContext.url = referrer
            output = do_vote(sessionContext)
            status = '200 OK' 
            content_type = 'text/plain'
        elif script == "delete_voter.wsgi" or script == "delete_voter.py":
            deletee = get_int_param_from_url(urldict, 'deletee')
            sessionContext.url = referrer
            output = do_delete_voter(sessionContext, deletee)
            if voterId == deletee:
                status = '401 Unauthorized' 
            else:
                status = '200 OK' 
            content_type = 'text/plain'
        elif script == "delete_track.wsgi" or script == "delete_track.py":
            trackId = get_int_param_from_url(urldict, 'trackId')
            sessionContext.url = referrer
            output = do_delete_track(sessionContext, trackId)
            status = '200 OK' 
            content_type = 'text/plain'
        elif script == "delete_vote.wsgi" or script == "delete_vote.py":
            voteId = get_int_param_from_url(urldict, 'voteId')
            sessionContext.url = referrer
            output = do_delete_vote(sessionContext, voteId)
            status = '200 OK' 
            content_type = 'text/plain'
        elif script == "control.wsgi":
            sessionContext.url = referrer
            output = do_player_command(sessionContext)
            status = '200 OK' 
            content_type = 'text/plain'

        # not found
        else:
            TRACE("%s was not found; script = %s, voterId = %d, " % (environ['SCRIPT_FILENAME'], voterId))
            output = ("File Not Found: uri = %s, script = %s, voterId = %d" % (environ['REQUEST_URI'], script, voterId))
            status = '404 Page Not Found' 
            content_type = 'text/plain'
    except:
        e = sys.exc_info()[0]
        TRACE("Exception running " + str(sys.argv[0]))
        print_exc(file=environ['wsgi.errors'])
        #return HTTPError(500, "Internal Server Error", e, format_exc(10))
        status = '500 Internal Server Error' 
        output = str(sys.exc_info()[0]) + "\n" + format_exc(10)
        content_type = 'text/plain'

    dbConnection.close()

    out = output.encode('utf-8')

    response_headers = [('Content-type', str(content_type)),
                        ('Content-Length', str(len(out)))]

    start_response(status, response_headers)

    return [out]
