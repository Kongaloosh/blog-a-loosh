var i = 0;

function increment() {
  i += 1;
}

function addFieldFunction() {
  var r = document.createElement('div');
  r.setAttribute("class", "form-id")

  var a_x = document.createElement("INPUT");
  var a_y = document.createElement("INPUT");
  var a_z = document.createElement("INPUT");

  var br = document.createElement("BR");

  a_x.setAttribute("type", "hidden")
  a_x.setAttribute("id", "geo_"+i);
  a_y.setAttribute("class", "dash-input");
  a_y.setAttribute("type", "text");
  a_y.setAttribute("placeholder", "Origin");
  a_y.setAttribute("id", "origin_"+i);
  a_z.setAttribute("class", "dash-input");
  a_z.setAttribute("type", "datetime-local");
  a_z.setAttribute("placeholder", "dt-departure");

  a_x.setAttribute("name", "geo[]"); //Keep attribute in lower case
  a_y.setAttribute("name", "location[]"); //Keep attribute in lower case
  a_z.setAttribute("name", "date[]");
  a_z.setAttribute("value", "2000-07-01T12:00")

  r.appendChild(a_x);
  r.appendChild(a_z);
  r.appendChild(a_y);

  r.appendChild(br);

  document.getElementById("form-div").appendChild(r);
  // add autocomplete listeners
  autocomplete(document.getElementById("geo_"+i));
  autocomplete(document.getElementById("origin_"+i));
  increment();
//  if this is the first leg of the trip, we need an additional input to act as the endpoint
  if (i == 1){
    addFieldFunction()
  }
}