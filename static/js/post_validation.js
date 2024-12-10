// Move validation to a separate function that can be called by travel validation
function validatePost() {
    let errors = [];

    // Get form elements
    const title = document.querySelector('input[name="title"]')?.value?.trim();
    const content = document.querySelector('textarea[name="content"]')?.value?.trim();
    const photos = document.querySelector('input[type="file"]')?.files;
    const tags = document.querySelector('input[name="tags"]')?.value?.trim();
    const syndication = document.querySelector('input[name="syndication"]')?.value?.trim();

    // Content Validation
    if (!content && !title) {
        errors.push("Either content or title is required");
    }

    // Event validation
    const eventErrors = validateEvent();
    if (eventErrors.length > 0) {
        errors = errors.concat(eventErrors);
    }

    // Photo Validation
    if (photos && photos.length > 0) {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

        for (const photo of photos) {
            if (!allowedTypes.includes(photo.type)) {
                errors.push(`Invalid file type for ${photo.name}. Allowed types: JPEG, PNG, GIF, WEBP`);
            }
        }
    }

    // Tags Validation
    if (tags) {
        const tagList = tags.split(',').map(tag => tag.trim());

        // Check for empty tags
        if (tagList.some(tag => tag.length === 0)) {
            errors.push("Empty tags are not allowed");
        }
    }

    // URL Validations
    const urlInputs = document.querySelectorAll('input[type="url"], input[name="in_reply_to"], input[name="syndication"]');
    for (const input of urlInputs) {
        if (input.value.trim()) {
            try {
                const url = new URL(input.value.trim());
                if (!['http:', 'https:'].includes(url.protocol)) {
                    errors.push(`Invalid URL protocol: ${input.value} (must be http or https)`);
                    input.classList.add('is-invalid');
                }
            } catch (e) {
                errors.push(`Invalid URL format: ${input.value}`);
                input.classList.add('is-invalid');
            }
        }
    }

    // Location Validation (if exists)
    const geoInputs = document.querySelectorAll('input[name="geo[]"]');
    for (const input of geoInputs) {
        if (input.value) {
            const geoRegex = /^geo:-?\d+(\.\d+)?,-?\d+(\.\d+)?$/;
            if (!geoRegex.test(input.value)) {
                errors.push(`Invalid geo format: ${input.value}. Expected format: geo:latitude,longitude`);
            }
        }
    }

    return errors;
}

function validateTravel() {
    const errors = [];
    const geoInputs = document.querySelectorAll('input[name="geo[]"]');
    const locationInputs = document.querySelectorAll('input[name="location[]"]');
    const dateInputs = document.querySelectorAll('input[name="date[]"]');

    for (let i = 0; i < geoInputs.length; i++) {
        const hasGeo = geoInputs[i].value.trim();
        const hasLocation = locationInputs[i].value.trim();
        const hasDate = dateInputs[i].value.trim();

        // Skip if all fields are empty (no travel data)
        if (!hasGeo && !hasLocation && !hasDate) {
            continue;
        }

        // If any field is filled, all must be filled
        if (!hasGeo || !hasLocation || !hasDate) {
            const missing = [];
            if (!hasGeo) missing.push('coordinates');
            if (!hasLocation) missing.push('location name');
            if (!hasDate) missing.push('date');
            errors.push(`Location ${i + 1} is missing: ${missing.join(', ')}`);
        }
    }

    return errors;
}

function validateEvent() {
    const errors = [];
    const eventName = document.querySelector('input[name="event_name"]')?.value?.trim();
    const eventStart = document.querySelector('input[name="dt_start"]')?.value?.trim();
    const eventEnd = document.querySelector('input[name="dt_end"]')?.value?.trim();
    const eventUrl = document.querySelector('input[name="event_url"]')?.value?.trim();

    // Skip if all fields are empty (no event data)
    if (!eventName && !eventStart && !eventEnd && !eventUrl) {
        return errors;
    }

    // If any field is filled, required fields must be filled
    if (!eventName || !eventStart) {
        const missing = [];
        if (!eventName) missing.push('event name');
        if (!eventStart) missing.push('start time');
        errors.push(`Event is missing: ${missing.join(', ')}`);
    }

    // End time is optional, but if provided, must be after start time
    if (eventEnd && eventStart) {
        const start = new Date(eventStart);
        const end = new Date(eventEnd);
        if (end < start) {
            errors.push('Event end time must be after start time');
        }
    }

    return errors;
}

// Integrate with travel validation on page load
document.addEventListener('DOMContentLoaded', function () {
    const originalValidateTravelForm = window.validateTravelForm;

    window.validateTravelForm = async function () {
        const postErrors = validatePost();
        const travelResult = await originalValidateTravelForm.call(this);

        // Combine errors from both validations
        if (postErrors.length > 0) {
            showValidationAlert(postErrors);
            return false;
        }

        return travelResult;
    };
});

function showValidationAlert(errors) {
    // Clear any existing alerts first
    const existingAlerts = document.querySelectorAll('#form-validation-alert');
    existingAlerts.forEach(alert => alert.remove());

    // Create new alert
    const alertDiv = document.createElement('div');
    alertDiv.id = 'form-validation-alert';
    alertDiv.className = 'alert alert-danger';
    alertDiv.role = 'alert';

    if (errors.length === 1) {
        alertDiv.textContent = errors[0];
    } else {
        const ul = document.createElement('ul');
        errors.forEach(error => {
            const li = document.createElement('li');
            li.textContent = error;
            ul.appendChild(li);
        });
        alertDiv.appendChild(ul);
    }

    document.querySelector('form').insertAdjacentElement('beforebegin', alertDiv);
} 