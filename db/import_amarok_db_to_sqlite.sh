#!/bin/bash
# Bryant Hansen

# initial 1-liner:
# /bin/sh ./943776/mysql2sqlite.sh -u root -p amarokdb | sed 's/\\\L/L/g;/^PRAGMA\ /d;:a;/\\$/{N;s/\\\n/\ /;ba};s/\"sequenctext/&\"/' > amarok.sqlite.convert.$(dt)

DBOUT="amarok.sqlite.db"
[[ "$1" ]] && DBOUT="$1"

# This joins lines that have a trailing backslash \
#    | sed ':a;/\\$/{N;s/\\\n/\ /;ba}' \
#
# This removes a couple of PRAGMA directives that did not work
#    | sed 's/\\\L/L/g;/^PRAGMA\ /d' \
#
# This is an ugly hack to add a double-quote where mysqldump left one out in a specific instance in a specific database
#    | sed 's/\"sequenctext/&\"/' \
#
# This removes newlines following a trailing comma (joining lines together)
#    | sed ':a;/\,[ \t]*$/{N;s/,[ \t]*\n/,\ /g;ba}' \
#
# This changes instancesd of
#   "id" int(11) NOT NULL
# to
#   id INTEGER PRIMARY KEY
#    | sed 's/\"id\"\ int(11)\ NOT\ NULL/id\ INTEGER\ PRIMARY\ KEY/g' \
#
# This simply removes PRIMARY KEY ("id") instances, which are no longer valid when PRIMARY KEY is already specified in the type
#    | sed 's/\"id\"\ int(11)\ NOT\ NULL/id\ INTEGER\ PRIMARY\ KEY/g;s/PRIMARY\ KEY\ (\"id\")//g' \
#
# This deletes any trailing commas at the end of a line, which must be done for the empty field when  the above "PRIMARY KEY ..." statement is removed
#    | sed 's/\,[ \t]*$/\ /g' \
#

/bin/sh ./943776/mysql2sqlite.sh -u root -p amarokdb \
    | sed 's/\\\L/L/g;/^PRAGMA\ /d;:a;/\\$/{N;s/\\\n/\ /;ba};s/\"sequenctext/&\"/' \
    | sed ':a;/\,[ \t]*$/{N;s/,[ \t]*\n/,\ /g;ba}' \
    | sed 's/\"id\"\ int(11)\ NOT\ NULL/id\ INTEGER\ PRIMARY\ KEY/g;s/PRIMARY\ KEY\ (\"id\")//g' \
    | sed 's/\,[ \t]*$/\ /g' \
    > "$DBOUT"
