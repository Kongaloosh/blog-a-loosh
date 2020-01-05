//(function () {
//  var script = document.createElement("script");
//  script.type = "text/javascript";
//  script.src  = "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.1/MathJax.js?config=TeX-AMS-MML_HTMLorMML";
//  document.getElementsByTagName("head")[0].appendChild(script);
//})();
MathJax.Hub.Startup.onload()
MathJax.Hub.Config({
  config: ["MMLorHTML.js"],
  jax: ["input/TeX", "output/HTML-CSS", "output/NativeMML"],
  extensions: ["MathMenu.js", "MathZoom.js"]
});

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
                'Content-Type': 'text/plain;charset=UTF-8'
            },
            body: val
        }).then(function (response) {
                return response.json();

            })
            .then(function (result) {
                document.getElementById("wysiwyg").innerHTML = result['html'];
                MathJax.Hub.Queue(["Typeset",MathJax.Hub]);
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