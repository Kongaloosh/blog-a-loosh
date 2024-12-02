
var text = "";
var img = "";

function setIMG(loc){
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
   	if (x === text) {

    } else {
        getHTMLFromMD(x)
    }
    text = x
}, 1000);

setInterval(function(){
	var x = document.getElementById("img_loc").value;
   	if (x === img) {

    } else {
        setIMG(x)
    }
    img = x
}, 1000);