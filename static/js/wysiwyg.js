
var text = "";
var img = "";
var title = "";
var summary = "";

function setIMG(loc){
    if (!loc.startsWith("/")) {
        loc = "/" + loc
    }
    $('#blah').attr('src', loc);
}


function getHTMLFromMD(val) {
    fetch('/md_to_html', {
            method: 'POST',
            headers: {
                'Accept': 'application/json, application/xml, text/plain, text/html, *.*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
            },
            body: val
        }).then(function (response) {
                return response.json();

            })
            .then(function (result) {
                document.getElementById("wysiwyg").innerHTML = result['html'];

            })
        .catch(function(error) {
    // If there is any error you will catch them here
    });
}

setInterval(function(){
	var x = document.getElementById("text_input").value;
   	if (x !== text) {
        getHTMLFromMD(x)
    }
    text = x
}, 1000);

setInterval(function(){
	var x = document.getElementById("img_loc").value;
   	if (x !== img && x !== 'None') {
        setIMG(x)
    }
    img = x
}, 1000);


setInterval(function(){
	var x = document.getElementById("title_form").value;
    if (x !== title && x !== 'None') {
        document.getElementById("title_format").innerHTML = x;
    }
    title = x
}, 1000);


setInterval(function(){
	var x = document.getElementById("summary_form").value;
   	if (x !== summary && x !== 'None') {
        document.getElementById("summary_format").innerHTML = x;
    }
    img = summary
}, 1000);