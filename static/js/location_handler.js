// Function to update the WYSIWYG preview with location
function updateLocationPreview(locationName) {
    const postFooter = document.getElementById("post-footer");
    if (!postFooter) return;

    // Find or create the location paragraph
    let locationP = postFooter.querySelector('.location-preview');
    if (!locationP) {
        locationP = document.createElement('p');
        locationP.className = 'location-preview';
        postFooter.insertBefore(locationP, postFooter.firstChild);
    }

    if (locationName) {
        locationP.innerHTML = `
            <div class="d-flex align-items-center text-muted">
                <i class="fa fa-map-marker me-2"></i>
                <small>${locationName}</small>
            </div>`;
        locationP.style.display = 'block';
    } else {
        locationP.style.display = 'none';
    }
}

// Add this function at the top
function updateLocationData(locationName, coordinates, locationId = null) {
    // Update hidden form fields
    document.getElementById('geo_coordinates').value = coordinates;
    document.getElementById('geo_name').value = locationName;
    if (locationId) {
        document.getElementById('geo_id').value = locationId;
    }

    // Update preview
    updateLocationPreview(locationName);

    // Update the JSON data structure if it exists
    if (window.entryData) {
        window.entryData.geo = {
            coordinates: coordinates.split(',').map(Number),
            name: locationName,
            location_id: locationId,
            raw_location: `geo:${coordinates}`
        };
    }
}

// Get device location and update fields
async function getCurrentLocation() {
    if (!navigator.geolocation) {
        console.error('Geolocation is not supported by this browser');
        return;
    }

    try {
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject);
        });

        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        const coordinates = `${lat},${lng}`;

        // Get place name from coordinates
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
            { headers: { 'User-Agent': 'YourWebsite/1.0' } }
        );
        const data = await response.json();

        if (data.display_name) {
            const locationInput = document.getElementById('location_input');
            locationInput.value = data.display_name;
            updateLocationData(data.display_name, coordinates);
        }
    } catch (error) {
        console.error('Error getting location:', error);
    }
}

// Initialize location functionality
document.addEventListener('DOMContentLoaded', function () {
    const locationInput = document.getElementById('location_input');
    const searchBtn = document.getElementById('location_search_btn');

    if (locationInput && searchBtn) {
        let timeoutId;

        // Get initial location on page load if no location is set
        if (!locationInput.value) {
            getCurrentLocation();
        } else {
            // If location exists, update preview
            updateLocationPreview(locationInput.value);
        }

        function closeAllLists() {
            const lists = document.getElementsByClassName("autocomplete-items");
            for (let i = 0; i < lists.length; i++) {
                lists[i].parentNode.removeChild(lists[i]);
            }
        }

        // Toggle search functionality
        searchBtn.addEventListener('click', function () {
            const isEnabled = locationInput.disabled;
            locationInput.disabled = !isEnabled;

            if (isEnabled) {
                // Enable search mode
                locationInput.focus();
                searchBtn.innerHTML = '<i class="fa fa-location-arrow"></i>';
            } else {
                // Disable search mode and get current location
                getCurrentLocation();
                searchBtn.innerHTML = '<i class="fa fa-search"></i>';
            }
        });

        // Search functionality
        locationInput.addEventListener('input', function () {
            if (locationInput.disabled) return;

            clearTimeout(timeoutId);
            closeAllLists();

            if (!this.value) return;

            timeoutId = setTimeout(async () => {
                try {
                    const response = await fetch(
                        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(this.value)}&limit=5`,
                        {
                            headers: {
                                'Accept': 'application/json',
                                'User-Agent': 'YourWebsite/1.0'
                            }
                        }
                    );
                    const places = await response.json();

                    if (places && places.length > 0) {
                        const dropdownDiv = document.createElement("DIV");
                        dropdownDiv.setAttribute("class", "autocomplete-items");
                        this.parentNode.appendChild(dropdownDiv);

                        places.forEach(place => {
                            const itemDiv = document.createElement("DIV");
                            itemDiv.innerHTML = place.display_name;

                            itemDiv.addEventListener("click", () => {
                                locationInput.value = place.display_name;
                                updateLocationData(place.display_name, `${place.lat},${place.lon}`);
                                closeAllLists();

                                // Disable input and switch button back
                                locationInput.disabled = true;
                                searchBtn.innerHTML = '<i class="fa fa-search"></i>';
                            });

                            dropdownDiv.appendChild(itemDiv);
                        });
                    }
                } catch (error) {
                    console.error('Error searching location:', error);
                }
            }, 500);
        });

        // Close dropdown when clicking outside
        document.addEventListener("click", function (e) {
            if (e.target !== locationInput) {
                closeAllLists();
            }
        });
    }
});