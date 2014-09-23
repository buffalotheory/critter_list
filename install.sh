#!/bin/bash
# Bryant Hansen

SOURCE_DIR="/project/critter_list"
INSTALL_DIR="/var/www/localhost/htdocs/mod_wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/admin.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/config.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/critter.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/debug.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/delete_track.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/delete_voter.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/delete_vote.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/docs.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/files.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/logout.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/player.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/playlist.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/stats.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/tally.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/tracks.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/vote.wsgi"
ln -s "$DIR/mod_wsgi/critter.wsgi" "$INSTALL_DIR/votes.wsgi"

ln -s "$DIR/critter.css" "$INSTALL_DIR/critter.css"
ln -s "$DIR/critters.db" "$INSTALL_DIR/critters.db"
ln -s "$DIR/template" "$INSTALL_DIR/template"
ln -s "$DIR/test.css" "$INSTALL_DIR/test.css"
ln -s "$DIR/vote.js" "$INSTALL_DIR/vote.js"

home="~"
[[ "$HOME" ]] && home="$HOME"
[[ ! -d "$home"/run/pyplayer ]] && mkdir -p "$home"/run/pyplayer
