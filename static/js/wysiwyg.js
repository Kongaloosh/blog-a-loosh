// Initialize MathJax safely
function initMathJax() {
    if (window.MathJax && window.MathJax.Hub) {
        MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
    }
}

// State management
const state = {
    text: "",
    img: "",
    title: "",
    summary: "",
    travel: [],
    event: {}
};

// Get CSRF token from meta tag or cookie
function getCSRFToken() {
    // Try meta tag first
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) return token;

    // Try cookie as fallback
    const tokenCookie = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrf_token='));
    return tokenCookie ? tokenCookie.split('=')[1] : null;
}

// Debounce function to prevent too many updates
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Preview update functions
function updatePreview(elementId, previewId, value) {
    const previewElement = document.getElementById(previewId);
    if (previewElement && value !== state[elementId] && value !== 'None') {
        previewElement.innerHTML = value;
        state[elementId] = value;
    }
}

// Markdown to HTML conversion with proper error handling
const getHTMLFromMD = debounce(async (val) => {
    if (!val) {
        const wysiwyg = document.getElementById("wysiwyg");
        if (wysiwyg) {
            wysiwyg.innerHTML = '';
        }
        return;
    }

    try {
        const token = getCSRFToken();
        console.log('Request payload:', { text: val });
        console.log('CSRF token:', token);

        if (!token) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch('/md_to_html', {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            credentials: 'include',
            body: JSON.stringify({ text: val })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        const wysiwyg = document.getElementById("wysiwyg");
        if (wysiwyg) {
            wysiwyg.innerHTML = result.html;

            // Add responsive classes to images
            const images = wysiwyg.getElementsByTagName('img');
            Array.from(images).forEach(img => {
                img.classList.add('img-fluid', 'mx-auto', 'd-block');
            });

            // Typeset math if present
            if (window.MathJax?.typesetPromise) {
                await window.MathJax.typesetPromise([wysiwyg]);
            }
        }
    } catch (error) {
        console.error('Preview error:', error);
        const wysiwyg = document.getElementById("wysiwyg");
        if (wysiwyg) {
            wysiwyg.innerHTML = `<div class="alert alert-warning">
                Preview temporarily unavailable: ${error.message}
            </div>`;
        }
    }
});

// Initialize all previews and listeners
function initializePreviews() {
    console.log("Initializing previews...");

    // Initialize MathJax
    initMathJax();

    // Text content preview
    const textInput = document.getElementById('text_input');
    if (textInput) {
        textInput.addEventListener('input', e => getHTMLFromMD(e.target.value));
        if (textInput.value) {
            getHTMLFromMD(textInput.value);
        }
    }

    // Media preview
    const mediaInput = document.querySelector('input[name="media_file[]"]');
    if (mediaInput) {
        mediaInput.addEventListener('change', function () {
            handlePhotoUpload(this);
        });
    }

    // Initialize existing photos if editing
    if (window.entryData && window.entryData.photo) {
        const photoHolder = document.getElementById('featured_image_preview');
        console.log("Photo holder found:", photoHolder);
        console.log("Photo array:", window.entryData.photo);
        if (photoHolder && Array.isArray(window.entryData.photo)) {
            console.log("Photo holder found and photo array is valid");
            window.entryData.photo.forEach(photoPath => {
                console.log("Photo path:", photoPath);
                const img = document.createElement('img');
                img.src = '/' + photoPath;
                img.classList.add('img-fluid', 'mb-3');
                photoHolder.appendChild(img);
            });
        }
    }

    // Title preview
    const titleInput = document.getElementById('title_form');
    if (titleInput) {
        titleInput.addEventListener('input', e =>
            updatePreview('title', 'title_format', e.target.value));
        if (titleInput.value) {
            updatePreview('title', 'title_format', titleInput.value);
        }
    }

    // Summary preview
    const summaryInput = document.getElementById('summary_form');
    if (summaryInput) {
        summaryInput.addEventListener('input', e =>
            updatePreview('summary', 'summary_format', e.target.value));
        if (summaryInput.value) {
            updatePreview('summary', 'summary_format', summaryInput.value);
        }
    }

    // Initialize featured image preview
    // initializeFeaturedImage();
}

function handlePhotoUpload(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const reader = new FileReader();

        reader.onload = function (e) {
            const isVideo = file.type.startsWith('video/');
            let mediaElement;
            let previewContainer = document.createElement('div');
            previewContainer.className = 'media-preview';

            if (isVideo) {
                mediaElement = document.createElement('video');
                mediaElement.src = e.target.result;
                mediaElement.controls = true;
                mediaElement.preload = 'metadata';
                mediaElement.classList.add('img-fluid');
            } else {
                mediaElement = document.createElement('img');
                mediaElement.src = e.target.result;
                mediaElement.classList.add('img-fluid');
            }

            // Add delete overlay
            const deleteOverlay = document.createElement('div');
            deleteOverlay.className = 'delete-overlay';
            deleteOverlay.innerHTML = '<i class="fa fa-times-circle delete-icon"></i>';

            // Add to preview container
            previewContainer.appendChild(mediaElement);
            previewContainer.appendChild(deleteOverlay);

            // Add to preview grid
            const previewGrid = document.getElementById('media_preview_grid');
            if (previewGrid) {
                previewGrid.appendChild(previewContainer);
            }
        }

        reader.readAsDataURL(file);
    }
}

// Tag management
function initializeTagSystem() {
    window.tags = new Set(
        document.getElementById('tags')?.value
            ? document.getElementById('tags').value.split(',').map(t => t.trim())
            : []
    );

    // Add enter key support
    document.getElementById('tag_input')?.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTag();
        }
    });
}

function updateTags() {
    // Update hidden input
    document.getElementById('tags').value = Array.from(window.tags).join(',');

    // Update display
    const display = document.getElementById('tag_display');
    display.innerHTML = Array.from(window.tags).map(tag => `
        <span class="badge bg-primary me-1 mb-1">
            ${tag}
            <button type="button" class="btn-close btn-close-white ms-1" 
                onclick="removeTag('${tag}')" aria-label="Remove"></button>
        </span>
    `).join('');
}

function addTag() {
    const input = document.getElementById('tag_input');
    const tag = input.value.trim();

    if (tag && !window.tags.has(tag)) {
        window.tags.add(tag);
        updateTags();
    }

    input.value = '';
    input.focus();
}

function removeTag(tag) {
    window.tags.delete(tag);
    updateTags();
}

function addExistingTag(tag) {
    if (!window.tags.has(tag)) {
        window.tags.add(tag);
        updateTags();
    }
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    initializeTagSystem();
    initializePreviews();
});

// Backup initialization in case DOMContentLoaded already fired
if (document.readyState === 'complete') {
    initializeTagSystem();
    initializePreviews();
}

