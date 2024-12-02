console.log("Travel validation script loaded");

async function validateTravelForm() {
    console.log("Starting form validation");

    // Clear any existing alerts
    const existingAlert = document.querySelector('#form-validation-alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    let errors = [];

    // Get form elements
    const title = document.querySelector('input[name="title"]')?.value?.trim();
    const content = document.querySelector('textarea[name="content"]')?.value?.trim();
    const photos = document.querySelector('input[type="file"]')?.files;

    console.log("Form data:", { title, content, hasPhotos: photos?.length > 0 });

    // Content validation
    if (!content && !title) {
        errors.push("Either content or title with additional content is required");
    }
    if (title && !content && !photos?.length && !hasTravel()) {
        errors.push("Title alone is not enough - add content, photos, or travel");
    }

    // Reply-to validation - only if the field exists and has a value
    const replyToInput = document.querySelector('input[name="in_reply_to"]');
    if (replyToInput?.value?.trim()) {
        console.log("Validating reply-to:", replyToInput.value);
        const replyToUrl = replyToInput.value.trim();
        try {
            const url = new URL(replyToUrl);
            if (!['http:', 'https:'].includes(url.protocol)) {
                errors.push(`Invalid URL protocol: ${replyToUrl} (must be http or https)`);
                replyToInput.classList.add('is-invalid');
            }
        } catch (e) {
            errors.push(`Invalid URL format: ${replyToUrl}`);
            replyToInput.classList.add('is-invalid');
        }
    }

    // Travel validation
    if (hasTravel()) {
        console.log("Validating travel");
        const travelErrors = validateTravel();
        errors = errors.concat(travelErrors);
    }

    // Event validation
    if (hasEvent()) {
        console.log("Validating event");
        const eventErrors = validateEvent();
        errors = errors.concat(eventErrors);
    }

    console.log("Validation errors:", errors);

    // Show errors if any
    if (errors.length > 0) {
        showValidationAlert(errors);
        return false;
    }

    console.log("Form validation successful");
    return true;
}

function hasTravel() {
    const geoInputs = document.querySelectorAll('input[name="geo[]"]');
    return Array.from(geoInputs).some(input => input.value.trim());
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

        if (hasGeo && !hasLocation) {
            errors.push(`Missing location name for entry ${i + 1}`);
        }
        if ((hasGeo || hasLocation) && !hasDate) {
            errors.push(`Missing date for location ${i + 1}`);
        }
    }

    return errors;
}

function showValidationAlert(errors) {
    const alert = document.createElement('div');
    alert.id = 'form-validation-alert';
    alert.className = 'alert alert-danger';

    let errorHtml = '<ul class="mb-0">';
    errors.forEach(error => {
        errorHtml += `<li>${error}</li>`;
    });
    errorHtml += '</ul>';

    alert.innerHTML = errorHtml;

    const form = document.querySelector('form');
    form.insertBefore(alert, form.firstChild);
}

// Update the form submission handler
document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    if (form) {
        console.log("Form action:", form.action);

        form.onsubmit = async function (e) {
            e.preventDefault();
            console.log("Form submission attempted");
            console.log("Form data:", new FormData(this));  // Debug log
            console.log("Submit type:", e.submitter?.name);  // Log which button was clicked

            const isValid = await validateTravelForm();
            console.log("Validation result:", isValid);

            if (isValid) {
                console.log("Submitting form to:", this.action);
                if (!this.action) {
                    console.error("No form action specified!");
                    return false;
                }
                // Ensure we preserve which button was clicked
                if (e.submitter) {
                    const submitType = document.createElement('input');
                    submitType.type = 'hidden';
                    submitType.name = e.submitter.name;
                    submitType.value = e.submitter.value || e.submitter.name;
                    this.appendChild(submitType);
                }
                this.submit();
            }
        };
    } else {
        console.error("Form not found!");
    }
});

// Utility function to debounce input validation
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function hasEvent() {
    const eventName = document.querySelector('input[name="event_name"]')?.value?.trim();
    const eventStart = document.querySelector('input[name="dt_start"]')?.value?.trim();
    const eventEnd = document.querySelector('input[name="dt_end"]')?.value?.trim();
    return eventName || eventStart || eventEnd;
}

function validateEvent() {
    const errors = [];
    const eventName = document.querySelector('input[name="event_name"]')?.value?.trim();
    const eventStart = document.querySelector('input[name="dt_start"]')?.value?.trim();
    const eventEnd = document.querySelector('input[name="dt_end"]')?.value?.trim();

    if (eventName || eventStart || eventEnd) {
        if (!eventName) {
            errors.push("Event name is required if adding event details");
            document.querySelector('input[name="event_name"]')?.classList.add('is-invalid');
        }
        if (!eventStart) {
            errors.push("Event start date is required if adding event details");
            document.querySelector('input[name="dt_start"]')?.classList.add('is-invalid');
        }
        if (!eventEnd) {
            errors.push("Event end date is required if adding event details");
            document.querySelector('input[name="dt_end"]')?.classList.add('is-invalid');
        }
    }

    return errors;
} 