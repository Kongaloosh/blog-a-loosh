// Keep all the initialization functions at the top
function initializeTravelData(entryData) {
    console.log('Initializing travel with entry data:', entryData);

    if (entryData?.travel?.trips?.length > 0) {
        console.log('Pre-filling travel data:', entryData.travel.trips);

        // Clear any existing fields first
        const travelForm = document.getElementById('travel_form');
        travelForm.innerHTML = '';

        // Filter out empty trips and create fields only for valid ones
        const validTrips = entryData.travel.trips.filter(trip =>
            trip.location || trip.location_name || trip.date
        );

        console.log('Valid trips:', validTrips);

        // Create and fill all fields
        validTrips.forEach((trip, index) => {
            console.log('Adding field for trip', index);
            window.addFieldFunction();

            // Set the values
            const originInput = document.getElementById(`origin_${index}`);
            const geoInput = document.getElementById(`geo_${index}`);
            const dateInput = document.getElementById(`datetime_${index}`);

            if (originInput && geoInput && dateInput) {
                originInput.value = trip.location_name || '';
                geoInput.value = trip.location || '';
                dateInput.value = trip.date || '';
                autocomplete(originInput);
            } else {
                console.error('Could not find all inputs for trip', index);
            }
        });
    } else {
        // If no trips, create initial empty field
        window.addFieldFunction();
    }
}

// Helper function to create HTML for a trip field
function createTripFieldHtml(index) {
    return `
        <div class="form-id" id="form-id_${index}">
            <input type="hidden" id="geo_${index}" name="geo[]">
            <input type="datetime-local" class="form-control mb-2" id="datetime_${index}" name="date[]">
            <div class="autocomplete d-flex align-items-center gap-2" style="width: 100%;">
                <input type="text" class="form-control" id="origin_${index}" name="location[]" placeholder="Location">
                <button type="button" class="btn btn-outline-danger btn-sm rounded-circle p-1" 
                    onclick="remove_trip(${index})" style="width: 32px; height: 32px; padding: 0 !important;">
                    <i class="fa fa-minus"></i>
                </button>
            </div>
        </div>
    `;
}

function initializeNewField(index) {
    const newInput = document.getElementById(`origin_${index}`);
    if (newInput) {
        autocomplete(newInput);
    }
}

// Single DOM content loaded event listener that handles everything
document.addEventListener('DOMContentLoaded', function () {
    console.log('Initializing travel functionality');

    // Create initial empty field if no entry data
    if (!window.entryData) {
        const travelForm = document.getElementById('travel_form');
        if (travelForm) {
            const html = createTripFieldHtml(0);
            travelForm.innerHTML = html;

            const locationInput = document.getElementById("origin_0");
            if (locationInput) {
                console.log('Initializing autocomplete for first field');
                autocomplete(locationInput);
            }
        }
    } else {
        // Initialize travel data if it exists
        initializeTravelData(window.entryData);
    }
});