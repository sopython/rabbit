// ==UserScript==
// @name        Extended User Notes
// @namespace   .
// @include     http://chat.stackoverflow.com/rooms/6/python
// @version     1
// @grant       none
// ==/UserScript==

var TOKEN = "deadbeef";

var UserInfoBoxTemplate = '' + 
'<div style="height:90%;width:90%;position:fixed;bottom:5%;right:5%;overflow:auto;border:2px solid black; z-index:99999; background-color:white">' + 
'' + 
'    <table style="width:100%">' + 
'        <tbody><tr>' + 
'            <td style="width:164px">' + 
'                <img class="avatar" src="test_files/3df6fdde70a4d2590b9b8494f3edfb56.png" style="width:164px;height:164px">' + 
'            </td>' + 
'            <td style="padding:10px;vertical-align:top">' + 
'                <h1 class="name">Kevin</h1>' + 
'                <h3>Kicks: <span class="kick_count">0</span></h3>' + 
'                <h3>Flags: <span class="flag_count">0</span></h3>' + 
'            </td>' + 
'            <td style="width:20px;vertical-align:top">' + 
'                <a class="close_button" style="font-size:32">[X]</a>' + 
'            </td>' + 
'        </tr>' + 
'    </tbody></table>' + 
'' + 
'    <br><br><br>' + 
'' + 
'    <table style="width:100%">' + 
'        <tbody><tr>' + 
'            <td style="width:50%;vertical-align:top">' + 
'                <h1>Previous Names</h1>' + 
'                <span class="no_previous_names_message">None.</span>' +
'                <ul class="previous_names_list">' + 
'                </ul>' + 
'            </td>' + 
'            <td style="width:50%;vertical-align:top">' + 
'                <h1>Previous Avatars</h1>' + 
'                <span class="no_previous_avatars_message">None.</span>' +
'                <span class="previous_avatars_list">' + 
'                </span>' + 
'            </td>' + 
'        </tr>' + 
'    </tbody></table>' + 
'' + 
'    <br><br><br>' + 
'' + 
'    <h1>Annotations</h1>' + 
'' + 
'    <span class="annotations">' + 
'' + 
'    </span>' + 
'    <span class="annotation_submission">' + 
'        <textarea class="submit_text_area" style="height:150px; width:90%; left:5%; position:relative"></textarea>' + 
'        <br/>' + 
'        <input class="submit" type="button" value="Submit" style="left:5%; position:relative"></input>' + 
'    </span>' + 
'' + 
'</div>';

var annotationTemplate = '' + 
'        <div style="background-color:gray;width:90%;left:5%;position:relative">' + 
'            <h4><span class="comment_username"></span> said:</h4>' + 
'            <span class="comment_body"></span>' + 
'            <h5>Posted <span class="comment_date"></span> at <span class="comment_time"></span></h5>' + 
'        </div>';


//courtesy of http://shebang.brandonmintern.com/foolproof-html-escaping-in-javascript/
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

//if `node` has exactly one descendant with the class name `className`, return it.
//otherwise, raise an exception.
function getOneElementByClassName(node, className){
    nodes = node.getElementsByClassName(className);
    if (nodes.length == 1){
        return nodes[0];
    }
    else{
        throw "Expected 1 node with className " + className + ", got " + nodes.length + " instead.";
    }
}

function removeChildNodes(node){
    while(node.childNodes.length > 0){
        node.removeChild(node.childNodes[0]);
    }
}

var UserInfoBox = function(username, avatar_url){
    this.element = document.createElement("span");
    this.element.innerHTML = UserInfoBoxTemplate;
    this.submitButtonListeners = [];
    this.hasEverBeenUpdatedByServer = false;

    self = this; // so we can access it inside these callbacks

    getOneElementByClassName(this.element, "close_button").onclick = function(){
        self.element.hidden = true;
    }

    getOneElementByClassName(this.element, "submit").onclick = function(){
        textbox = getOneElementByClassName(self.element, "submit_text_area");
        if (textbox.value.length == 0){return;}
        self.submitButtonListeners.forEach(function(listener){
            listener(textbox.value);
        })
        textbox.value = "";
    }

    this.bindOnSubmit(function(value){console.log(value);});

    this.names = [username]; //all names the user had, in order from least recent to most recent
    this.avatars = [avatar_url]; //all avatars the user had, in order from least recent to most recent.
    this.updateNameAndAvatarElements();

}

//update the html elements representing the user's name and avatar (both current and previous)
UserInfoBox.prototype.updateNameAndAvatarElements = function(){
    currentUsername = this.names[this.names.length-1];
    currentAvatar = this.avatars[this.avatars.length-1];
    previousUsernames = this.names.slice(0, this.names.length-1);
    previousAvatars = this.avatars.slice(0, this.avatars.length-1);

    //update current name/avatar
    getOneElementByClassName(this.element, "name").innerHTML = escapeHtml(currentUsername);
    getOneElementByClassName(this.element, "avatar").src = currentAvatar;

    previous_names_list = getOneElementByClassName(this.element, "previous_names_list")
    previous_avatars_list = getOneElementByClassName(this.element, "previous_avatars_list")
    //clear out previous name/avatar entries
    removeChildNodes(previous_names_list);
    removeChildNodes(previous_avatars_list);
    
    //update "no previous (username | avatar)" message
    getOneElementByClassName(this.element, "no_previous_names_message").hidden = (previousUsernames.length > 0);
    getOneElementByClassName(this.element, "no_previous_avatars_message").hidden = (previousAvatars.length > 0);

    //update previous username/avatar lists
    for(var i = 0; i < previousUsernames.length; i+=1){
        this.addPreviousName(previousUsernames[i]);
    }
    for(var i = 0; i < previousAvatars.length; i+=1){
        this.addPreviousAvatar(previousAvatars[i]);
    }
    //todo: make sure that these are being inserted in chronological order. Might be backwards right now.

}

UserInfoBox.prototype.addPreviousName = function(name){
    var item = document.createElement("li");
    item.innerHTML = escapeHtml(name);
    getOneElementByClassName(this.element, "previous_names_list").appendChild(item);
    getOneElementByClassName(this.element, "no_previous_names_message").hidden = true;
}

UserInfoBox.prototype.addPreviousAvatar = function(avatar_url){
    var img = document.createElement("img");
    img.src = avatar_url;
    img.style = "width:32px;height:32px;padding:5px";
    getOneElementByClassName(this.element, "previous_avatars_list").appendChild(img);
    getOneElementByClassName(this.element, "no_previous_avatars_message").hidden = true;
}

UserInfoBox.prototype.setKickCount = function(count){
    getOneElementByClassName(this.element, "kick_count").innerHTML = count;
}

UserInfoBox.prototype.setFlagCount = function(count){
    getOneElementByClassName(this.element, "flag_count").innerHTML = count;
}

UserInfoBox.prototype.addAnnotation = function(annotation){
    var target = getOneElementByClassName(this.element, "annotations");
    target.appendChild(annotation.element);
    target.appendChild(document.createElement("br"));
}

UserInfoBox.prototype.bindOnSubmit = function(callback){
    this.submitButtonListeners.push(callback);
}

UserInfoBox.prototype.updateWithServerData = function(d){
    updates = d["updates"];
    if (!this.hasEverBeenUpdatedByServer){
        //now that we're getting "official" name/avatar data from the server,
        //we can clear out the placeholder values we were using.
        this.names = [];
        this.avatars = [];
    }
    shouldRefreshNameOrAvatarList = false;
    for (var i = 0; i < updates.length; i+=1){
        update = updates[i];
        if (update["update_type"] == "kicks"){
            this.setKickCount(update["value"]);
        }
        else if (update["update_type"] == "flags"){
            this.setFlagCount(update["value"]);
        }
        else if (update["update_type"] == "name"){
            this.names.push(update["value"]);
            shouldRefreshNameOrAvatarList = true;
        }
        else if (update["update_type"] == "avatar"){
            this.avatars.push(update["value"]);
            shouldRefreshNameOrAvatarList = true;
        }
    }

    if (shouldRefreshNameOrAvatarList){
        this.updateNameAndAvatarElements();
    }

    this.hasEverBeenUpdatedByServer = true;
}

var Annotation = function(name, text, date, time){
    this.element = document.createElement("span");
    this.element.innerHTML = annotationTemplate;
    getOneElementByClassName(this.element, "comment_username").innerHTML = escapeHtml(name);
    getOneElementByClassName(this.element, "comment_body").innerHTML = escapeHtml(text);
    getOneElementByClassName(this.element, "comment_date").innerHTML = escapeHtml(date);
    getOneElementByClassName(this.element, "comment_time").innerHTML = escapeHtml(time);
}

var popups = {};

function updatePopup(box){
    //at this point, we know the standard user popup is open, and it doesn't yet have an extended notes link yet.
    var links = box.getElementsByTagName("A");
    if(links.length == 0){ throw "Expected at least one link in user box, got 0"; }
    var user_id = parseInt(links[0].href.split("/")[4]);

    var user_name = box.getElementsByClassName("username")[0].innerHTML;
    var avatar_url = box.getElementsByTagName("IMG")[0].src;
    avatar_url = avatar_url.replace("s=48", "s=164");

    var link = document.createElement("a");
    link.className = "user_notes_link";
    link.innerHTML = "Rap sheet";

    console.log("size: " + box.getElementsByClassName("last-dates").length);
    box.insertBefore(link, box.getElementsByClassName("last-dates")[0].nextSibling.nextSibling.nextSibling);

    link.onclick = function(){
        if(!(user_id in popups)){
            userInfoBox = new UserInfoBox(
                user_name, 
                avatar_url
            );
            popups[user_id] = userInfoBox;
            userInfoBox.element.hidden = true;
            document.body.appendChild(userInfoBox.element);

            ws.send(JSON.stringify({
                "event_type": "register_interest",
                "user_id": user_id
            }));

            userInfoBox.bindOnSubmit(function(text){
                console.log("Sending annotation to server...");
                ws.send(JSON.stringify({
                    "event_type": "create_annotation",
                    "user_id": user_id,
                    "text": text,
                }));
                console.log("sent.");
            });
        }
        popups[user_id].element.hidden = false;
    }
}

//periodically scan the page for open popup boxes, and if we find any, add in extended links
function scanPopups(){
    try{
    var boxes = document.getElementsByClassName("popup user-popup");
    if (boxes.length == 0){return;}
    var box = boxes[0];
    if (box.getElementsByClassName("user_notes_link").length > 0){return;}
    updatePopup(box);
    }catch(e){console.log(e);}
}

setInterval(scanPopups, 500);

try{
    console.log("Sending request...");

    var ws = new WebSocket("ws:127.0.0.1:8000/");
    ws.onopen = function(event){
        console.log("Connected. Sending handshake...");
        handshake = JSON.stringify({
            "protocol_version": "1",
            "user_id": 0,
            "token": "deadbeef"
        })
        console.log(handshake);
        ws.send(handshake);
        console.log("Sent greeting.")
    }

    ws.onmessage = function(event){
        try{
        console.log("Got reply from server.");
        console.log(event.data);
        d = JSON.parse(event.data);
        if (d["event_type"] == "create_annotation"){
            console.log("Got create_annotation event. Adding annotation...");
            console.log(popups);
            popups[d["user_id"]].addAnnotation(new Annotation(
                d["author_name"],
                d["text"],
                d["date"],
                d["time"]
            ));
        }
        else if (d["event_type"] == "update_user_info"){
            console.log("updating user info for user with id " + d["user_id"]);
            popups[d["user_id"]].updateWithServerData(d);
        }
        }catch(e){console.log(e);}
    }

    console.log("Sent request.")
}
catch(e){
    console.log(e);
}