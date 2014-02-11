"""
critter.py - a dynamic voting system

@author: Bryant Hansen
@license: GPLv3
"""

from mod_python import apache

import sqlite3
import sys
import os
import time
import re
from random import randint, choice
import StringIO
import subprocess

DIR='/var/www/localhost/htdocs/mod_python'

sessionId = 123456789;
voterId = 3
debuglog = StringIO.StringIO()

def TRACE(msg):
    debuglog.write(time.strftime("%H:%M:%S") + ": " + str(msg) + "\n");

def get_voter(con, voterId):
    cur = con.cursor()
    cur.execute(
        "SELECT id, name FROM voters "
        "WHERE id = '" + str(voterId)  + "'"
    )
    rows = cur.fetchall()
    if len(rows) >= 1:
        return rows[0][1]
    else:
        return ""

def add_voter(con, votername):
    cur = con.cursor()
    cur.execute(
        "INSERT INTO voters (name) VALUES ('" + votername + "');"
    )
    con.commit()

def get_voterId(con, votername):
    cur = con.cursor()
    cur.execute(
        "SELECT id, name FROM voters "
        "WHERE " +
            "name = '" + votername + "'"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        return 0
    else:
        return rows[0][0]

def get_or_add_voter(con, votername):
    id = get_voterId(con, votername)
    if id == 0:
        add_voter(con, votername)
    id = get_voterId(con, votername)
    if id == 0:
        TRACE("ERROR adding voter " + str(votername))
    return id

def invent_random_voter():
    TRACE("inventing random voter")
    return choice([ "Mr.", "Ms." ]) + str(unichr(randint(65,65+26)))

def discover_voter(req, con):

    mac = "not found"
    try:
        ip = req.get_remote_host(apache.REMOTE_NOLOOKUP)
        if str(ip) == "::1" or str(ip) == "127.0.0.1" or str(ip) == "localhost":
            mac="01:02:03:04:05:06"
        if (len(ip) > 0):
                arp = tuple(open('/proc/net/arp', 'r'))
                for l in arp:
                    a = l.split()
                    if a[0] == ip:
                        mac = a[3]
                        break
    except Exception as inst:
        TRACE("Exception fetching voter IP & MAC")
        req.write(
            "<div id='ERROR'>\n" +
            "<p>Exception in critter.py / vote() - failed to parse vote</p>\n" +
            #"<p>" + type(inst) + "</p>\n" +   # the exception instance
            #"<p>" + inst.args + "</p>\n" +    # arguments stored in .args
            #"<p>" + inst + "</p>\n" +         # __str__ allows args to printed directly
            #"<p>sys.exc_info()[0]: " + str(sys.exc_info()[0]) + "</p>\n" +
            "</div>\n"
        )

    TRACE("  voter ip: " + str(ip))
    TRACE(" voter mac: " + str(mac))

    # parse url for voterId
    votestr = req.parsed_uri[7]

    if votestr:
        votedict = dict([ x.split('=') for x in votestr.split('&') ])
        if len(votedict['voterId']) > 0:
            TRACE("voterId indicated in URL: " + votedict['voterId'])
            voterId = get_voter(con, votedict['voterId'])
            if len(voterId) > 0:
                TRACE("voterId exists in db as " + voterId)
                return voterId
            else:
                TRACE("voter not found in voter db for id " + votedict['voterId'])

    # TODO: try to get this from MAC address, IP address, cookie or even sessionId?
    return invent_random_voter()

def new_session(voterId):
    pass

def dump_tracks_table(req, cur, voterId):
    req.write("<table id='tracks' class='db_table'>\n")
    cur.execute(
        "SELECT tracks.id, tracks.filename, votes.voterId, votes.vote "
        "FROM tracks LEFT JOIN votes "
        "ON tracks.id = votes.trackId "
        "AND " + str(voterId) + " = votes.voterId"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No tracks are available</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th colspan='4'>Tracks</th></tr>\n"
            "<tr>"
            "<th rowspan='2'>filename</th>\n"
            "<th colspan='2'>Votes</th>\n"
            "</tr>\n"
            "<tr>\n"
            "<th>Yae</th>\n"
            "<th>Nay</th>\n"
            #"<th>Debug</th>\n"
            "</tr>\n"
        )
        for row in rows:
            trackId = str(row[0])
            title = str(row[1])
            trackvoterId = str(row[2])
            vote = str(row[3])
            title = os.path.basename(title)
            req.write(
                "<tr>\n"
                "<td>" + title + "</td>\n"
            )
            vote_yae_class = "class=\"vote\""
            vote_nay_class = "class=\"vote\""
            if str(trackvoterId) == str(voterId):
                if vote == "1" or vote == "yae":
                    vote_yae_class = "class=\"votedyae\""
                if vote == "0" or vote == "nay":
                    vote_nay_class = "class=\"votednay\""
            req.write(
                "<td " + vote_yae_class + ">"
                "<a id=\"track_" + trackId + "\" " + vote_yae_class + " onclick=\"vote_yae('" + 
                str(title) + "', " + str(sessionId) + ", " + str(trackId) + ", " + str(voterId) + 
                ")\"><img src=\"./up_arrow2.png\" />"
                "</a>"
                "</td>\n"

                "<td " + vote_nay_class + ">"
                "<a id=\"track_" + trackId + "\" " + vote_nay_class + " onclick=\"vote_nay('" + 
                str(title) + "', " + str(sessionId) + ", " + str(trackId) + ", " + str(voterId) + 
                ")\"><img src=\"./down_arrow2.png\" />"
                "</a>"
                "</td>\n"

                #"<td>" + str(voterId) + ", " + str(trackvoterId) + ", " + str(vote) + "</td>\n"
            )
            req.write("</tr>\n")
    req.write("</table>\n")

def dump_voters_table(req, cur, voterId):
    req.write("<table id='voters' class='db_table'>\n")
    cur.execute("SELECT id, name FROM voters")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No<br />voters<br />have<br />been<br />registered</th></tr>\n")
    else:
        req.write(
            "<tr><th>Voters</th></tr>\n"
            "<tr>\n"
            "<th>" + str(cur.description[0][0]) + "</th>\n"
            "</tr>\n"
        )
        for row in rows:
            lVoterId = row[0]
            selectedVoterClass = ""
            if voterId == lVoterId:
                selectedVoterClass = "class='voterCell'"
            req.write("<tr><td " + str(selectedVoterClass) + ">"
                      "<a href=\"critter.py?voterId=" + str(row[0]) + "\">" + str(row[1]) + "</a>\n"
                      "</td></tr>\n"
            )
    req.write("</table>\n")

def dump_sessions_table(req, cur):
    req.write("<table id='voters' class='db_table'>\n")
    cur.execute("SELECT name FROM sessions")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>Sessions</th></tr>\n")
        req.write("<tr><td>No<br />sessions<br />have<br />been<br />registered</td></tr>\n")
    else:
        cols = len(rows[0])
        req.write("<tr><th colspan='" + str(cols) + "'>Sessions</th></tr>\n")
        req.write("<tr>\n")
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>\n")
        for row in rows:
            req.write("<tr>\n")
            for col in range(cols):
                req.write("<td>" + str(row[col]) + "</td>\n")
            req.write("</tr>\n")
    req.write("</table>\n")

def dump_votes_table(req, cur):
    req.write("<table id='votes' class='db_table'>\n")
    cur.execute("SELECT tracks.filename, voters.name, vote FROM votes JOIN tracks ON votes.trackId = tracks.id JOIN voters ON votes.voterId = voters.id")
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No<br />votes<br />have<br />been<br />registered</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th colspan='" + str(cols) + "'>Votes</th></tr>\n"
            "<tr>\n"
        )
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>\n")
        for row in rows:
            req.write("<tr>\n")
            for col in range(cols):
                if row[col] == None:
                    req.write("<td>&nbsp;\n")
                else:
                    if str(cur.description[col][0]) == 'filename':
                        req.write("<td>")
                        title = str(row[col])
                        title = os.path.basename(title)
                        req.write(title)
                    elif str(cur.description[col][0]) == 'vote':
                        if str(row[col]) == '1' or str(row[col]) == 'yae':
                            req.write(
                                "<td class='yaevote'>"
                                "<img src=\"template/thumbs_up.png\" />"
                            )
                        elif str(row[col]) == '0' or str(row[col]) == 'nay':
                            req.write(
                                "<td class='nayvote'>"
                                "<img src=\"template/thumbs_down.png\" />"
                            )
                        else:
                            req.write(
                                "<td>" +
                                str(row[col])
                            )
                    else:
                        req.write(
                            "<td>" +
                            str(row[col])
                        )
                req.write("</td>\n")
            req.write("</tr>\n")
    req.write("</table>\n")

def dump_tally_table(req, cur):
    req.write("<table id='tally' class='db_table'>\n")
    # major query: this is where the magic happens
    # this retreives the tally, including the score/ranking of every song
    cur.execute(
        "SELECT \
        ( \
            COUNT(CASE WHEN vote = '1' THEN vote END) \
          - COUNT(CASE WHEN vote = '0' THEN vote END) \
        ) AS score, \
        tracks.filename, \
        COUNT(CASE when vote = '1' THEN vote END) AS yaes, \
        COUNT(CASE when vote = '0' THEN vote END) AS nahs \
        FROM tracks \
        LEFT JOIN votes ON votes.trackId=tracks.id \
        GROUP BY tracks.id \
        ORDER BY score DESC, yaes;"
    )
    rows = cur.fetchall()
    if len(rows) < 1:
        req.write("<tr><th>No tracks are available</th></tr>\n")
    else:
        cols = len(rows[0])
        req.write(
            "<tr><th colspan='" + str(cols) + "'>Tally</th></tr>\n"
            "<tr>\n"
        )
        for col in range(cols):
            req.write("<th>" + str(cur.description[col][0]) + "</th>\n")
        req.write("</tr>\n")
        for row in rows:
            req.write("<tr>\n")
            for col in range(cols):
                req.write("<td>")
                if row[col] == None:
                    req.write("&nbsp;\n")
                else:
                    # TODO: reference col by description, rather than position
                    # consider converting database results to dict objects
                    if col == 1:
                        title = str(row[col])
                        title = os.path.basename(title)
                        req.write(title)
                    else:
                        req.write(str(row[col]))
                req.write("</td>\n")
            req.write("</tr>\n")
    req.write("</table>\n")

def dump_vote_tables(req, con, voterId):

    cur = con.cursor()

    req.write("<div id='voters' class='db_table'>\n")
    dump_voters_table(req, cur, voterId)
    req.write("</div>\n")

    req.write("<div id='sessions' class='db_table'>\n")
    dump_sessions_table(req, cur)
    req.write("</div>\n")

    req.write("<div id='tracks' class='db_table'>\n")
    dump_tracks_table(req, cur, voterId)
    req.write("</div>\n")

    req.write("<div id='votes' class='db_table'>\n")
    dump_votes_table(req, cur)
    req.write("</div>\n")

    req.write("<div id='tally' class='db_table'>\n")
    dump_tally_table(req, cur)
    req.write("</div>\n")

    req.write("<div id='footer'>\n"
        "<p class='footer'>Generated on " + time.strftime("%Y-%m-%d %H:%M:%S %Z") + "</p>\n"
        "<p class='copyright'>(c)2014 Bryant Hansen</p>\n"
        "</div>\n"
    )

    req.write("<div id='debug'>\n")
    req.write("<h4>Debugging Info</h4>\n")
    #req.write("referrer1: " + req.get_remote_host(apache.REMOTE_NOLOOKUP) + "<br />\n")
    #req.add_common_vars()
    #req.write("referrer2: " + req.subprocess_env['REMOTE_ADDR'] + "<br />\n")
    #for attr in dir(req):
    #    req.write("req.%s = %s<br />\n" % (attr, getattr(req, attr)))
    req.write("</div>\n")

    req.write (
        "<H3 id='debugTextboxLabel'>mod_python Debug Messages</H3>\n"
        "<TEXTAREA id='pyDebugTextbox' rows='20' cols='80'>\n"
        + str(debuglog.getvalue()) + "\n"
        "</TEXTAREA>\n"
    )

    req.write (
        "<H3 id='debugTextboxLabel'>Javascript Debug Messages</H3>\n"
        "<TEXTAREA id='jsDebugTextbox' rows='20' cols='80'>\n"
        "</TEXTAREA>\n"
    )
    """
    req.write (
        "<SCRIPT TYPE=\"text/javascript\">\n"
            "document.write(\"<H3 id='debugTextboxLabel'>Javascript Debug Messages</H3>\");\n"
            "document.write(\"<TEXTAREA id='jsDebugTextbox' rows='20' cols='80'>\");\n"
            "document.write(\"uninitialized textbox\\n\");\n"
            "document.write(\"</TEXTAREA>\");\n"
        "</SCRIPT>\n"
    )
    """

def dump_critter_page(req, con, voterId):

    # TODO: create page buffer!

    req.content_type = "text/html"
    req.write(
        "<html>\n"

        "<head>\n"
        "<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=ISO-8859-1\">\n"
        "<title>Critter List - a Dechromatic Playist</title>\n"
        "<LINK REL=StyleSheet HREF=\"critter.css\" TYPE=\"text/css\" MEDIA=screen>\n"
        "<META name=\"description\" content=\"Critter List\">\n"
        "<META name=\"keywords\" content=\"Bryant, Hansen, Bryant Hansen, critter\">\n"
        "<script type=\"text/javascript\" src=\"vote.js\"></script>\n"
        "</head>\n"

        #"<body onLoad=\"loadPage()\">"
        "<body>"

        "<table id='header'><tr><td>"
        "<h1>Critter List</h1>\n"
        "</td><td>\n"
        "<h2>Welcome, " + str(get_voter(con, voterId)) + "!</h2>\n"
        "</td></tr>\n"
        "</table>\n"

        "<div id='TODO'>\n"
        "<h4>TODO</h4>\n"
        "<ul>\n"
        "<li>Port from mod_python to mod_wsgi\n"
        "<li>Get ID3 tags - parse ID3 tags and display the info instead of filename\n"
        "<li>Amarok integration - automate conversion and finish linking queries to this\n"
        "<li>Date/Time for votes, plus expiration feature.  Link to sessions\n"
        "<li>Create separate Voting and Viewing pages\n"
        "<li>Login screen\n"
        "<li>Separate screens: Voter Client, Admin, Dev, ???\n"
        "<li>Tab bar on top to access various views\n"
        "<li>Test on Mobile phones\n"
        "<li>Clear votes\n"
        "</ul>\n"
        "</div>\n"

        "<div id='tables'>\n"
    )

    dump_vote_tables(req, con, voterId)

    req.write(
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )

    return apache.OK

def dump_debug_page(req, con, voterId):

    # TODO: create page buffer!

    req.content_type = "text/html"
    req.write(
        "<html>\n"

        "<head>\n"
        "<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=ISO-8859-1\">\n"
        "<title>Critter List - a Dechromatic Playist</title>\n"
        "<LINK REL=StyleSheet HREF=\"critter.css\" TYPE=\"text/css\" MEDIA=screen>\n"
        "<META name=\"description\" content=\"Critter List\">\n"
        "<META name=\"keywords\" content=\"Bryant, Hansen, Bryant Hansen, critter\">\n"
        "<script type=\"text/javascript\" src=\"vote.js\"></script>\n"
        "</head>\n"

        "<body onLoad=\"loadPage(image1.id)\">"

        "<h1>Critter DeBUG Page</h1>\n"
        "<h2>voterId = " + str(voterId) + "</h2>\n"
    )

    req.write (
        "<H3 id='debugTextboxLabel'>mod_python Debug Messages</H3>\n"
        "<TEXTAREA id='debugTextbox' rows='20' cols='80'>\n"
        + debuglog.getvalue() + "\n"
        "</TEXTAREA>\n"
    )

    req.write (
        "<SCRIPT TYPE=\"text/javascript\">\n"
            "document.write(\"<H3 id='debugTextboxLabel'>Javascript Debug Messages</H3>\");\n"
            "document.write(\"<TEXTAREA id='jsDebugTextbox' rows='20' cols='80'>\");\n"
            "document.write(\"    First line of initial text.\\n\");\n"
            "document.write(\"    Second line of initial text.\");\n"
            "document.write(\"</TEXTAREA>\");\n"
        "</SCRIPT>"
    )
    req.write(
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )

    return apache.OK

def do_vote(req, con, voterId):

    TRACE("enter vote")

    req.content_type = "text/plain"

    # this is the extra params on the URL after the question mark (?)
    # as is conventional, each param is delimited by the ampersand (&)
    votestr = req.parsed_uri[7]

    try:
        # this is an elegant 1-liner to convert the typical command line to a python dict object
        votedict = dict([ x.split('=') for x in votestr.split('&') ])
    except Exception as inst:
        # dump an excessive amount of information
        req.write(
            "<div id='ERROR'>\n" +
            "<p>Exception in critter.py / vote() - failed to parse vote</p>\n" +
            "<p>" + type(inst) + "</p>\n" +   # the exception instance
            "<p>" + inst.args + "</p>\n" +    # arguments stored in .args
            "<p>" + inst + "</p>\n" +         # __str__ allows args to printed directly
            "<p>sys.exc_info()[0]: " + sys.exc_info()[0] + "</p>\n" +
            "</div>\n"
        )
        return 2

    vote = votedict['vote']
    if vote == "yae" or vote == "nay":
        if vote == "yae":
            ivote = 1
        elif vote == "nay":
            ivote = 0
        else:
            req.write("critter.py: vote of " + str(vote) + " no understood")
        os.chdir(DIR)
        cur = con.cursor()
        cur.execute(
            "SELECT id, trackId, voterId, vote FROM votes "
            "WHERE " +
                "voterId = '" + votedict['voterId']  + "' AND " +
                "trackId = '" + votedict['trackId']     + "';"
        )
        rows = cur.fetchall()
        if len(rows) < 1:
            # no records exist matching the voterId and the trackId
            #pass
            try:
                cur.execute(
                    "INSERT INTO votes "
                        "(voterId,                     trackId,                       vote) "
                    "VALUES ('" + 
                        votedict['voterId'] + "', '" + votedict['trackId'] + "', '" + str(ivote) + 
                    "');"
                )
            except:
                # TODO: determine why this is ineffective; sys.exc_info()[0] reference kill all output
                req.write(
                    "<div id='ERROR'>\n" +
                    "<p>Exception in critter.py / vote() - failed to parse vote</p>\n" +
                    #"<p>" + type(inst) + "</p>\n" +   # the exception instance
                    #"<p>" + inst.args + "</p>\n" +    # arguments stored in .args
                    #"<p>" + inst + "</p>\n" +         # __str__ allows args to printed directly
                    #"<p>sys.exc_info()[0]: " + sys.exc_info()[0] + "</p>\n" +
                    "</div>\n"
                )
                return apache.OK
        else:
            # TODO: if the vote exists, delete it
            # req.write("<p>str(ivote)=" + str(ivote) + ", str(rows[0][2])=" + str(rows[0][2]) + "")
            if str(ivote) == str(rows[0][3]):
                cur.execute("DELETE FROM votes " + 
                            "WHERE "
                                "voterId = '" + votedict['voterId'] + "' AND "
                                "trackId = '" + votedict['trackId'] + "';")
            else:
                cur.execute("UPDATE votes " + 
                            "SET vote = '" + str(ivote) + "' "
                            "WHERE "
                                "voterId = '" + votedict['voterId'] + "' AND "
                                "trackId = '" + votedict['trackId'] + "';")
        con.commit()
        cur = con.cursor()
        dump_vote_tables(req, con, voterId)
    else:
        req.write("<p>your vote of " + str(req.parsed_uri) + " was not understood</p>\n")
        for attr in dir(req):
            req.write("req.%s = %s<br />\n" % (attr, getattr(req, attr)))

    return apache.OK


######################
# Main

def handler(req):

    os.chdir(DIR)
    con = sqlite3.connect('critters.db')

    req.content_type = "text/html"
    TRACE("enter handler.")
    voter = discover_voter(req, con)
    TRACE("voter = " + str(voter))
    voterId = get_or_add_voter(con, voter)
    TRACE("voterId = " + str(voterId))

    #result = dump_debug_page(con, req, voterId)
    #return result

    if req.uri == "/mod_python/critter.py":
        result = dump_critter_page(req, con, voterId)
    elif req.uri == "/mod_python/vote.py":
        result = do_vote(req, con, voterId)
    else:
        TRACE(req.uri + " was not found")
        result = apache.HTTP_NOT_FOUND

    con.close()
    return result

