var x = document.getElementById("geo_coord");

function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(showPosition);
    } else {
        x.innerHTML = "Geolocation is not supported by this browser.";
    }
}

function showPosition(position) {
    x.innerHTML = "geo:" + position.coords.latitude +
    "," + position.coords.longitude;
}

var form = document.getElementById("input");


if (document.getElementById('geo_check').checked && document.getElementById('geo_coord').value == ""){
    getLocation()
}
