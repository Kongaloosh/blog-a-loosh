function getRecentPhotos() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (xhttp.readyState == 4 && xhttp.status == 200) {
            document.getElementById("photo_holder").innerHTML = xhttp.responseText;
        }
    };
    xhttp.open("GET", "/recent_uploads", true);
    xhttp.send();
}

function insertAtCaret(areaId,text,img_id) {
var img_loc = document.getElementById(img_id);
var style = img_loc.getAttribute("style");
style += "-webkit-filter: grayscale(100%);-moz-filter: grayscale(100%);-o-filter: grayscale(100%);-ms-filter: grayscale(100%);filter: grayscale(100%); ";
img_loc.setAttribute("style", style);
var txtarea = document.getElementById(areaId);
var scrollPos = txtarea.scrollTop;
var strPos = 0;
var br = ((txtarea.selectionStart || txtarea.selectionStart == '0') ?
    "ff" : (document.selection ? "ie" : false ) );
if (br == "ie") {
    txtarea.focus();
    var range = document.selection.createRange();
    range.moveStart ('character', -txtarea.value.length);
    strPos = range.text.length;
}
else if (br == "ff") strPos = txtarea.selectionStart;

var front = (txtarea.value).substring(0,strPos);
var back = (txtarea.value).substring(strPos,txtarea.value.length);
txtarea.value=front+text+back;
strPos = strPos + text.length;
if (br == "ie") {
    txtarea.focus();
    var range = document.selection.createRange();
    range.moveStart ('character', -txtarea.value.length);
    range.moveStart ('character', strPos);
    range.moveEnd ('character', 0);
    range.select();
}
else if (br == "ff") {
    txtarea.selectionStart = strPos;
    txtarea.selectionEnd = strPos;
    txtarea.focus();
}
txtarea.scrollTop = scrollPos;
}
