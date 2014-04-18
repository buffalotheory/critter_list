/*
 * Bryant Hansen
 * javascript voting system
 */

var debugCache;

function DebugMessage(newText) {
    var timestamp = new Date().toString().split(" ")[4] + " ";
    debugTextboxObj = document.getElementById("jsDebugTextbox");
    if (debugTextboxObj) {
        debugTextboxObj.value += timestamp + " " + newText + "\n";
        debugCache = debugTextboxObj.value;
      //if ((debugTextboxObj.scrollTop) && (debugTextboxObj.scrollHeight)) {
            debugTextboxObj.scrollTop = debugTextboxObj.scrollHeight;
      //}
    }
}

/*
 * function viewport() from:
 * http://andylangton.co.uk/blog/development/get-viewport-size-width-and-height-javascript
 * 
 * thanks! :)
 * 
 */
function viewport() {
    var e = window, a = 'inner';
    if (!( 'innerWidth' in window )) {
        a = 'client';
        e = document.documentElement || document.body;
    }
    return { width : e[ a+'Width' ] , height : e[ a+'Height' ] }
}

function basename(str) {
   var base = new String(str).substring(str.lastIndexOf('/') + 1); 
    if (base.lastIndexOf(".") != -1)
       base = base.substring(0, base.lastIndexOf("."));
   return base;
}

function fetch_server_debug() {
}

function submitVote(vote, sessionId, trackId, voterId, title) {
    if (window.XMLHttpRequest) {  // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else {  // code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }

    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                location_basename = basename(window.location.pathname)
                DebugMessage("location_basename = " + location_basename);
                if (location_basename == "tracks") {
                    document.getElementById("table_tracks").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#tracks");
                }
                else if (location_basename == "critter") {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#div_tables");
                }
                else {
                    document.getElementById("table_tracks").innerHTML = xmlhttp.responseText;
                    DebugMessage("unknown path " + window.location.pathname + "  updated div#div_tables.  basename = " + location_basename);
                }
                pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
                if (pyDebugTextboxObj) {
                    pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
                }
            }
            else {
                DebugMessage("submitVote xmlhttp.onreadystatechange: xmlhttp.status = " + xmlhttp.status);
            }
        }
        /*
        else {
            DebugMessage("submitVote xmlhttp.onreadystatechange: xmlhttp.readyState = " + xmlhttp.readyState);
        }
        */
    }
    vp = viewport();
    DebugMessage ("vote: vp.width = " + vp.width + ", vp.height = " + vp.height);
    DebugMessage ("vote: window.location = " + window.location);
    url = "vote.wsgi?sessionId=" + sessionId +
                                "&trackId=" + trackId + 
                                "&voterId=" + voterId + 
                                "&width=" + vp.width +
                                "&height=" + vp.height +
                                "&vote=" + vote +
                                "&page=" + window.location.pathname +
                                "&title=" + title,
    DebugMessage ("url = " + url);
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function delete_voter(sessionId, voterId, deletee) {
    DebugMessage("delete_voter: sessionId = " + sessionId + ", voterId = " + voterId + ", voterId(deletee) = " + deletee);
    if (window.XMLHttpRequest) {  // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else {  // code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                location_basename = basename(window.location.pathname)
                DebugMessage("location_basename = " + location_basename);
                //DebugMessage("len(xmlhttp.responseText) = " + len(xmlhttp.responseText));
                if ((location_basename == "critter") || (location_basename == "admin")){
                    // if (len(xmlhttp.responseText) > 0) {
                        document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    //}
                    //else {
                    //    document.getElementById("div_tables").innerHTML = "<br />NO ACTIVE VOTER<br />";
                    //}
                    DebugMessage("updated div#div_tables");
                }
                else {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("unknown path " + window.location.pathname + "  updated div#div_tables.  basename = " + location_basename);
                }
                pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
                if (pyDebugTextboxObj) {
                    pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
                }
            }
            else if (xmlhttp.status == 401) {
                window.location.href=window.location.href
            }
            else {
                DebugMessage("submitVote xmlhttp.onreadystatechange: xmlhttp.status = " + xmlhttp.status);
            }
        }
    }
    vp = viewport();
    DebugMessage ("delete_voter: vp.width = " + vp.width + ", vp.height = " + vp.height);
    DebugMessage ("delete_voter: window.location = " + window.location);
    url = "delete_voter.wsgi?sessionId=" + sessionId +
                                "&page=" + window.location.pathname +
                                "&voterId=" + voterId +
                                "&deletee=" + deletee,
                                "&width=" + vp.width +
                                "&height=" + vp.height
    DebugMessage ("url = " + url);
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function delete_vote(sessionId, voterId, voteId) {
    DebugMessage("delete_vote:: sessionId = " + sessionId + ", voterId = " + voterId + ", voteId = " + voteId);
    if (window.XMLHttpRequest) {  // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else {  // code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                location_basename = basename(window.location.pathname)
                DebugMessage("location_basename = " + location_basename);
                if ((location_basename == "critter") || (location_basename == "admin")){
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#div_tables");
                }
                else {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("unknown path " + window.location.pathname + "  updated div#div_tables.  basename = " + location_basename);
                }
                pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
                if (pyDebugTextboxObj) {
                    pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
                }
            }
            else {
                DebugMessage("submitVote xmlhttp.onreadystatechange: xmlhttp.status = " + xmlhttp.status);
            }
        }
        else {
            DebugMessage("delete_vote xmlhttp.onreadystatechange: xmlhttp.readyState = " + xmlhttp.readyState);
        }
    }
    vp = viewport();
    DebugMessage ("delete_vote: vp.width = " + vp.width + ", vp.height = " + vp.height);
    DebugMessage ("delete_vote: window.location = " + window.location);
    url = "delete_vote.wsgi?sessionId=" + sessionId +
                                "&page=" + window.location.pathname +
                                "&voterId=" + voterId +
                                "&width=" + vp.width +
                                "&height=" + vp.height +
                                "&voteId=" + voteId
    DebugMessage ("url = " + url);
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function delete_track(sessionId, voterId, trackId) {
    DebugMessage("delete_track: sessionId = " + sessionId + ", voterId = " + voterId + ", trackId = " + trackId);
    if (window.XMLHttpRequest) {  // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else {  // code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                location_basename = basename(window.location.pathname)
                DebugMessage("location_basename = " + location_basename);
                //DebugMessage("len(xmlhttp.responseText) = " + len(xmlhttp.responseText));
                if ((location_basename == "critter") || (location_basename == "admin")){
                    // if (len(xmlhttp.responseText) > 0) {
                        document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    //}
                    //else {
                    //    document.getElementById("div_tables").innerHTML = "<br />NO ACTIVE VOTER<br />";
                    //}
                    DebugMessage("updated div#div_tables");
                }
                else {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("unknown path " + window.location.pathname + "  updated div#div_tables.  basename = " + location_basename);
                }
                pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
                if (pyDebugTextboxObj) {
                    pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
                }
            }
            else {
                DebugMessage("delete_track xmlhttp.onreadystatechange: xmlhttp.status = " + xmlhttp.status);
            }
        }
    }
    vp = viewport();
    DebugMessage ("delete_track: vp.width = " + vp.width + ", vp.height = " + vp.height);
    DebugMessage ("delete_track: window.location = " + window.location);
    url = "delete_track.wsgi?sessionId=" + sessionId +
                                "&page=" + window.location.pathname +
                                "&voterId=" + voterId +
                                "&width=" + vp.width +
                                "&height=" + vp.height +
                                "&voteId=" + voteId
    DebugMessage ("url = " + url);
    xmlhttp.open("GET", url, true);




    xmlhttp.send();
}

function vote_yae(sessionId, trackId, voterId, title) {
    DebugMessage("vote_yae: title = " + title + ", sessionId = " + sessionId + ", trackId = " + trackId + ", voterId = " + voterId);
    submitVote("yae", sessionId, trackId, voterId, title);
}

function vote_nay(sessionId, trackId, voterId, title) {
    DebugMessage("vote_nay: title = " + title + ", sessionId = " + sessionId + ", trackId = " + trackId + ", voterId = " + voterId);
    submitVote("nay", sessionId, trackId, voterId, title);
}

function play(sessionId, voterId) {
    if (window.XMLHttpRequest) {  // code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else {  // code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }

    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                location_basename = basename(window.location.pathname)
                DebugMessage("location_basename = " + location_basename);
                if (location_basename == "tracks") {
                    document.getElementById("div_tracks").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#div_tracks");
                }
                else if (location_basename == "critter") {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#div_tables");
                }
                else if (location_basename == "player") {
                    document.getElementById("div_playlist").innerHTML = xmlhttp.responseText;
                    DebugMessage("updated div#div_playlist");
                }
                else {
                    document.getElementById("div_tables").innerHTML = xmlhttp.responseText;
                    DebugMessage("unknown path " + window.location.pathname + "  updated div#div_tables.  basename = " + location_basename);
                }
                pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
                if (pyDebugTextboxObj) {
                    pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
                }
            }
            else {
                DebugMessage("submitVote xmlhttp.onreadystatechange: xmlhttp.status = " + xmlhttp.status);
            }
        }
    }

    vp = viewport();
    url = "control.wsgi?command=play" +
                        "&sessionId=" + sessionId +
                        "&voterId=" + voterId +
                        "&width=" + vp.width +
                        "&height=" + vp.height +
                        "&page=" + window.location.pathname;
    DebugMessage ("url = " + url);
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function loadPage() {

    d = new Date();
    StartTime = d.getTime();

    //is = new Is();

    // Call the args_init () function to set up the args [] array:
    // args_init ();

    if (document.getElementById) {
        debugTextboxObj = document.getElementById("jsDebugTextbox");
    }
    //if (debugTextboxObj) debugTextboxObj.value = "";
    DebugMessage ("loadPage complete");
    DebugMessage ("screen.width = " + screen.width + ", screen.height = " + screen.height);
    DebugMessage ("screen.availWidth = " + screen.availWidth + ", screen.availHeight = " + screen.availHeight);

    vp = viewport();
    DebugMessage ("vp.width = " + vp.width + ", vp.height = " + vp.height);

    pyDebugTextboxObj = document.getElementById("pyDebugTextbox");
    if (pyDebugTextboxObj) {
        pyDebugTextboxObj.scrollTop = pyDebugTextboxObj.scrollHeight;
    }

    // DebugMessage ("loadPage complete, screen.width + " screen.width + ", screen.height = " + screen.height);
    //DebugMessage ("window.location = " + window.location);
    //DebugMessage ("window.location.pathname = " + window.location.pathname);

}