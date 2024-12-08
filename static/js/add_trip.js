var i = 0;

function increment() {
  i += 1;
}

function removeElement(elementId) {
  var element = document.getElementById(elementId);
  element.parentNode.removeChild(element);
}


function remove_trip(index) {
  // Remove the form element
  const element = document.getElementById(`form-id_${index}`);
  if (element) {
    element.remove();
  }

  // Reindex remaining elements
  const formElements = document.querySelectorAll('.form-id');
  formElements.forEach((el, newIndex) => {
    // Update all IDs and names
    el.id = `form-id_${newIndex}`;

    // Update hidden geo input
    const geoInput = el.querySelector('input[name="geo[]"]');
    if (geoInput) geoInput.id = `geo_${newIndex}`;

    // Update date input
    const dateInput = el.querySelector('input[name="date[]"]');
    if (dateInput) dateInput.id = `datetime_${newIndex}`;

    // Update location input
    const locationInput = el.querySelector('input[name="location[]"]');
    if (locationInput) locationInput.id = `origin_${newIndex}`;

    // Update remove button
    const removeBtn = el.querySelector('button');
    if (removeBtn) removeBtn.setAttribute('onclick', `remove_trip(${newIndex})`);
  });

  // Update the global counter
  i = formElements.length;
}

function addFieldFunction() {
  // Create container div
  var r = document.createElement('div');
  r.setAttribute("class", "form-id");
  r.setAttribute("id", "form-id_" + i);

  // Create inputs
  var geoInput = document.createElement("INPUT");
  var dateInput = document.createElement("INPUT");
  var locationContainer = document.createElement("div");
  var locationInput = document.createElement("INPUT");
  var removeBtn = document.createElement("button");

  // Hidden geo input
  geoInput.setAttribute("type", "hidden");
  geoInput.setAttribute("id", "geo_" + i);
  geoInput.setAttribute("name", "geo[]");
  geoInput.setAttribute("value", "");

  // Date input
  dateInput.setAttribute("type", "datetime-local");
  dateInput.setAttribute("class", "form-control mb-2");
  dateInput.setAttribute("id", "datetime_" + i);
  dateInput.setAttribute("name", "date[]");

  // Location container with inline remove button
  locationContainer.setAttribute("class", "autocomplete d-flex align-items-center gap-2");
  locationContainer.style.width = "100%";

  // Location input
  locationInput.setAttribute("type", "text");
  locationInput.setAttribute("class", "form-control");
  locationInput.setAttribute("id", "origin_" + i);
  locationInput.setAttribute("name", "location[]");
  locationInput.setAttribute("placeholder", "Location");

  // Set up location input to update geo field when location is selected
  locationInput.addEventListener('location-selected', function (e) {
    if (e.detail && e.detail.geo) {
      geoInput.value = e.detail.geo;
    }
  });

  // Remove button
  removeBtn.setAttribute("type", "button");
  removeBtn.setAttribute("class", "btn btn-outline-danger btn-sm rounded-circle p-1");
  removeBtn.setAttribute("onclick", "remove_trip(" + i + ")");
  removeBtn.setAttribute("style", "width: 32px; height: 32px; padding: 0 !important;");
  removeBtn.innerHTML = '<i class="fa fa-minus"></i>';

  // Assemble the elements
  locationContainer.appendChild(locationInput);
  locationContainer.appendChild(removeBtn);
  r.appendChild(geoInput);
  r.appendChild(dateInput);
  r.appendChild(locationContainer);

  // Add to form
  document.getElementById("travel_form").appendChild(r);

  // Initialize autocomplete
  autocomplete(locationInput);

  increment();
}