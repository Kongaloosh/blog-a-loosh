async function getCandidatePlaces(str) {
  console.log('Fetching places for:', str);
  try {
    const url = '/geonames/' + encodeURIComponent(str);
    console.log('Making request to:', url);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
      }
    });
    console.log('Response status:', response.status);

    const json = await response.json();
    console.log('Response data:', json);

    return json.geonames || [];
  } catch (error) {
    console.error('Error fetching places:', error);
    return [];
  }
}

function autocomplete(inp) {
  if (!inp) {
    console.error('No input element provided to autocomplete');
    return;
  }
  console.log('Initializing autocomplete for:', inp.id);

  /*the autocomplete function takes two arguments,
  the text field element and an array of possible autocompleted values:*/
  var currentFocus;
  /*execute a function when someone writes in the text field:*/
  inp.addEventListener("input", async function (e) {
    console.log('Input event fired for:', inp.id);
    console.log('Current value:', this.value);
    var a, b, i, val = this.value;

    if (!val) {
      console.log('Empty value, skipping search');
      return false;
    }

    try {
      const places = await getCandidatePlaces(val);
      console.log('Got places:', places);

      if (!places || places.length === 0) {
        console.log('No places found');
        return;
      }

      // Create dropdown container
      a = document.createElement("DIV");
      a.setAttribute("id", this.id + "autocomplete-list");
      a.setAttribute("class", "autocomplete-items");
      this.parentNode.appendChild(a);

      places.forEach((place, i) => {
        console.log('Adding place to dropdown:', place.title);

        // Create dropdown item
        b = document.createElement("DIV");
        b.innerHTML = place.title;

        // Add click handler to set both location name and geo coordinates
        b.addEventListener("click", function (e) {
          inp.value = place.title;
          // Find the corresponding geo input by looking at the parent form-id div
          const formDiv = inp.closest('.form-id');
          if (formDiv) {
            const geoInput = formDiv.querySelector('input[name="geo[]"]');
            if (geoInput) {
              geoInput.value = `geo:${place.lat},${place.lng}`;
              console.log('Set geo value:', geoInput.value);
            } else {
              console.error('Could not find geo input in form div');
            }
          } else {
            console.error('Could not find parent form-id div');
          }
          closeAllLists();
        });

        a.appendChild(b);
      });
    } catch (error) {
      console.error('Error in autocomplete handler:', error);
    }
  });
  /*execute a function presses a key on the keyboard:*/
  inp.addEventListener("keydown", function (e) {
    var x = document.getElementById(this.id + "autocomplete-list");
    if (x) x = x.getElementsByTagName("div");
    if (e.keyCode == 40) {
      /*If the arrow DOWN key is pressed,
      increase the currentFocus variable:*/
      currentFocus++;
      /*and and make the current item more visible:*/
      addActive(x);
    } else if (e.keyCode == 38) { //up
      /*If the arrow UP key is pressed,
      decrease the currentFocus variable:*/
      currentFocus--;
      /*and and make the current item more visible:*/
      addActive(x);
    } else if (e.keyCode == 13) {
      /*If the ENTER key is pressed, prevent the form from being submitted,*/
      e.preventDefault();
      if (currentFocus > -1) {
        /*and simulate a click on the "active" item:*/
        if (x) x[currentFocus].click();
      }
    }
  });
  function addActive(x) {
    /*a function to classify an item as "active":*/
    if (!x) return false;
    /*start by removing the "active" class on all items:*/
    removeActive(x);
    if (currentFocus >= x.length) currentFocus = 0;
    if (currentFocus < 0) currentFocus = (x.length - 1);
    /*add class "autocomplete-active":*/
    x[currentFocus].classList.add("autocomplete-active");
  }
  function removeActive(x) {
    /*a function to remove the "active" class from all autocomplete items:*/
    for (var i = 0; i < x.length; i++) {
      x[i].classList.remove("autocomplete-active");
    }
  }
  function closeAllLists(elmnt) {
    /*close all autocomplete lists in the document,
    except the one passed as an argument:*/
    var x = document.getElementsByClassName("autocomplete-items");
    for (var i = 0; i < x.length; i++) {
      if (elmnt != x[i] && elmnt != inp) {
        x[i].parentNode.removeChild(x[i]);
      }
    }
  }

  /*execute a function when someone clicks in the document:*/
  document.addEventListener("click", function (e) {
    closeAllLists(e.target);
  });
}

