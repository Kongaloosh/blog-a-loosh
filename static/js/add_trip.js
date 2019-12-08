var i = 0;

function increment() {
  i += 1;
}

function removeElement(elementId){
    var element = document.getElementById(elementId);
    element.parentNode.removeChild(element);
}


function remove_trip(i) {
    removeElement("geo_"+i);
    removeElement("origin_"+i);
    removeElement("datetime_"+i);
    removeElement("remove_"+i);
    removeElement("break_"+i);
    removeElement("form-id_"+i);
}

function addFieldFunction() {
  var r = document.createElement('div');
  r.setAttribute("class", "form-id");
  r.setAttribute("id", "form-id_"+i)

  var a_x = document.createElement("INPUT");
  var a_y = document.createElement("INPUT");
  var a_z = document.createElement("INPUT");
  var remove_icon = document.createElement("a");
  var br = document.createElement("BR");

  a_x.setAttribute("type", "hidden")
  a_x.setAttribute("id", "geo_"+i);
  a_y.setAttribute("class", "dash-input");
  a_y.setAttribute("type", "text");
  a_y.setAttribute("placeholder", "Origin");
  a_y.setAttribute("id", "origin_"+i);
  a_z.setAttribute("class", "dash-input");
  a_z.setAttribute("type", "datetime-local");
  a_z.setAttribute("id", "datetime_"+i);
  a_z.setAttribute("placeholder", "dt-departure");

  remove_icon.innerHTML = '<i class="fa fa-minus-circle"></i>'
  remove_icon.setAttribute("id","remove_"+i)
  remove_icon.setAttribute("onclick","remove_trip("+i+")")

  br.setAttribute("id", "break_"+i)

  a_x.setAttribute("name", "geo[]"); //Keep attribute in lower case
  a_y.setAttribute("name", "location[]"); //Keep attribute in lower case
  a_z.setAttribute("name", "date[]");
//  a_z.setAttribute("value", "2000-07-01T12:00")

  r.appendChild(a_x);
  r.appendChild(a_z);
  r.appendChild(a_y);
  r.appendChild(remove_icon);
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