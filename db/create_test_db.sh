#!/bin/bash
# Bryant Hansen
# GPLv3

# The Democratic DJ - a critter list of entertainment


ME="$(basename "$0")"
DB="critters.db.$(dt)"

CONF="./critters.conf"

add_tables() {
    local DB="$1"
    sqlite3 "$DB" "CREATE TABLE storage_devices (id INTEGER PRIMARY KEY, name VARCHAR(256), label VARCHAR(64), uuid VARCHAR(64), type VARCHAR(12), partuuid VARCHAR(64));"
    sqlite3 "$DB" "CREATE TABLE files (id INTEGER PRIMARY KEY, storage_device INTEGER, path VARCHAR(256), filename VARCHAR(1024));"
    sqlite3 "$DB" "CREATE TABLE playlist (id INTEGER PRIMARY KEY, trackId INTEGER, playOrder INTEGER, yaes INTEGER, nahs INTEGER);"
    sqlite3 "$DB" "CREATE TABLE voters (id INTEGER PRIMARY KEY, name VARCHAR(256), status INTEGER);"
    sqlite3 "$DB" "CREATE TABLE votes (id INTEGER PRIMARY KEY, trackId INTEGER, voterId INTEGER, vote INTEGER, votedOn DATETIME);"
    sqlite3 "$DB" "CREATE TABLE sessions (id INTEGER PRIMARY KEY, name VARCHAR(256), voterId INTEGER, ip VARCHAR(20), mac VARCHAR(30), startTime DATETIME, endTime DATETIME, status INTEGER);"
    sqlite3 "$DB" "CREATE TABLE playHistory (id INTEGER PRIMARY KEY, trackId INTEGER, playedOn DATETIME, result INTEGER, comment VARCHAR(1024));"
    sqlite3 "$DB" "CREATE TABLE playResults (id INTEGER PRIMARY KEY, description VARCHAR(256));"
}

create_playlist() {
    local playlist_name="$1"
    echo "${DB}: INSERT INTO playlists (name, description, parent_id) VALUES ('${playlist_name}', 'Auto-generated Playlist from ${ME} on $(dt)', '0');"
    sqlite3 $DB "INSERT INTO playlists (name, description, parent_id) VALUES ('${playlist_name}', 'Auto-generated Playlist from ${ME} on $(dt)', '0');"
}

get_playlist_id() {
    local playlist_name="$1"
    records="$(sqlite3 $DB "SELECT id FROM playlists WHERE name = '${playlist_name}';" | head -n 1)"
    if [[ "$records" ]] ; then
        echo "$records"
        return 0
    else
        echo "get_playlist_id: failed to return any records for playlists matching '${playlist_name}'" >&2
        echo "0"
        return 1
    fi
}

create_random_playlist() {
    local playlist_name="$1"
    local max_tracks="$2"
    echo "create_playlist($playlist_name)" >&2
    create_playlist "$playlist_name"
    playlistId="$(get_playlist_id "$playlist_name")"
    if [[ "$playlistId" -gt 0 ]] ; then
        sqlite3 "$DB" "SELECT id FROM tracks" \
        | sort -R \
        | head -n $max_tracks \
        | while read trackId ; do
            echo "INSERT INTO playlist_tracks (playlist_id, track_num) VALUES ('${playlistId}', '${trackId}');"
        done \
        | sqlite3 "$DB"
    else
        echo "no playlist found for playlistId $playlistId" >&2
        echo "cannot create playlist" >&2
    fi
    return $?
}

# Description:
#   Takes a device
#   Determines relative parameters via the blkid call
#   Checks for existing record in the db
#   If no record matches exactly, then add a new record
# sample blkid output:
# /dev/sdb3: LABEL="DATA_005" UUID="0f6706f2-3bc6-41a8-a636-f423c84bdc70" TYPE="xfs" PARTUUID="547e0e9d-d994-4aa8-89d5-bd883861534b"
add_device() {
    # TODO: use  path as an argument, rather than the device
    echo "$ME: $0 $1" >&2

    local name="$1"
    local info="$(blkid | grep "^${name}.*$")"
    local lines="$(echo "$info" | wc -l)"
    local dev=""
    local label=""
    local uuid=""
    local partuuid=""
    local fstype=""
    case $lines in
    0)
        echo "No data found for device $name" >&2
        return 2
        ;;
    1)
        echo "$name params: $info"
        for l in $info ; do
            [[ ! "$l" ]] && continue
            l="${l//\"/}"
            [[ ! "${l%%/*}" ]] && [[ ! "${l##*:}" ]] && dev="${l%:}"
            [[ ! "${l%%LABEL=*}" ]] && label="${l#LABEL=}"
            [[ ! "${l%%UUID=*}" ]] && uuid="${l#UUID=}"
            [[ ! "${l%%TYPE=*}" ]] && fstype="${l#TYPE=}"
            [[ ! "${l%%PARTUUID=*}" ]] && partuuid="${l#PARTUUID=}"
        done
        # first check for a record that matches exactly; if it doesn't exist, add a new one
        #echo "sqlite3 $DB \"SELECT * FROM storage_devices WHERE name LIKE '${name}' AND label LIKE '${label}' AND uuid LIKE '${uuid}' AND type LIKE '${fstype}' AND partuuid LIKE '${partuuid}'\""
        records="$(sqlite3 $DB "SELECT * FROM storage_devices WHERE name LIKE '${name}' AND label LIKE '${label}' AND uuid LIKE '${uuid}' AND type LIKE '${fstype}' AND partuuid LIKE '${partuuid}'";)"
        if [[ "$records" ]] ; then
            echo -e "records exist: $records" >&2
        else
            #echo "sqlite3 $DB \"INSERT INTO storage_devices (name, label, uuid, type, partuuid) VALUES (${name}, ${label}, ${uuid}, ${fstype}, ${partuuid});\""
            echo "${DB}: adding $name" >&2
            sqlite3 $DB "INSERT INTO storage_devices (name, label, uuid, type, partuuid) VALUES ('${name}', '${label}', '${uuid}', '${fstype}', '${partuuid}');"
        fi
        ;;
    *)
        echo "ERROR: $lines lines found.  Expected only 1!" >&2
        echo -e "lines: $info" >&2
        ;;
    esac
}


########################
# Main

[[ "$1" ]] && DB="$1"

if [[ -f "$DB" ]] ; then
    echo "DB $DB already exists.  Exiting." >&2
    exit 0
fi

TMPDIR="."
TMPDB="${TMPDIR}/mysql_dump_and_convert.db.tmp"
./import_amarok_db_to_sqlite.sh "$TMPDB"
sqlite3 "$DB" < "$TMPDB"
rm "$TMPDB"
add_tables "$DB"

create_random_playlist "test playlist $(dt)" 50

chgrp apache "$DB"
chmod g+w "$DB"

exit 0
