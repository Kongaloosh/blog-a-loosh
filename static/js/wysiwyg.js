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
        textInput.addEventListener('input', function (e) {
            getHTMLFromMD(e.target.value);
        });
        if (textInput.value) {
            getHTMLFromMD(textInput.value);
        }
    }

    // Initialize existing photos if editing
    const mediaPreviewGrid = document.getElementById('media_preview_grid');
    if (mediaPreviewGrid) {
        // Clear existing content first
        mediaPreviewGrid.innerHTML = '';

        // Add existing photos if any
        if (window.entryData && Array.isArray(window.entryData.photo)) {
            console.log("Loading photos:", window.entryData.photo);

            window.entryData.photo.forEach(function (photoPath) {
                if (!photoPath) return; // Skip null/undefined entries

                console.log("Adding photo:", photoPath);
                const previewContainer = document.createElement('div');
                previewContainer.className = 'media-preview';

                const img = document.createElement('img');
                img.src = '/' + photoPath;
                img.classList.add('img-fluid');

                // Add delete overlay
                const deleteOverlay = document.createElement('div');
                deleteOverlay.className = 'delete-overlay';
                deleteOverlay.innerHTML = '<i class="fa fa-times-circle delete-icon"></i>';

                // Add click handler for delete
                deleteOverlay.onclick = function () {
                    if (confirm('Are you sure you want to delete this media?')) {
                        previewContainer.remove();
                        updateMediaPaths();
                    }
                };

                previewContainer.appendChild(img);
                previewContainer.appendChild(deleteOverlay);
                mediaPreviewGrid.appendChild(previewContainer);
            });
        }
    }

    // Media upload listener - remove any existing listeners first
    const mediaInput = document.querySelector('input[name="media_file[]"]');
    if (mediaInput) {
        // Remove existing listeners
        mediaInput.replaceWith(mediaInput.cloneNode(true));

        // Add new listener to the fresh element
        document.querySelector('input[name="media_file[]"]').addEventListener('change', function () {
            handlePhotoUpload(this);
        });
    }

    // Title preview
    const titleInput = document.getElementById('title_form');
    if (titleInput) {
        titleInput.addEventListener('input', function (e) {
            updatePreview('title', 'title_format', e.target.value);
        });
        if (titleInput.value) {
            updatePreview('title', 'title_format', titleInput.value);
        }
    }

    // Summary preview
    const summaryInput = document.getElementById('summary_form');
    if (summaryInput) {
        summaryInput.addEventListener('input', function (e) {
            updatePreview('summary', 'summary_format', e.target.value);
        });
        if (summaryInput.value) {
            updatePreview('summary', 'summary_format', summaryInput.value);
        }
    }
}

// Remove the duplicate initialization calls
document.addEventListener('DOMContentLoaded', function () {
    // Only call once
    initializePreviews();
});

function handlePhotoUpload(input) {
    if (input.files && input.files.length > 0) {
        Array.from(input.files).forEach(file => {
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

                // Store the file name as a data attribute
                mediaElement.dataset.fileName = file.name;

                // Add delete overlay
                const deleteOverlay = document.createElement('div');
                deleteOverlay.className = 'delete-overlay';
                deleteOverlay.innerHTML = '<i class="fa fa-times-circle delete-icon"></i>';

                // Add click handler for delete
                deleteOverlay.onclick = function () {
                    if (confirm('Are you sure you want to delete this media?')) {
                        previewContainer.remove();
                        updateMediaPaths();
                    }
                };

                // Add to preview container
                previewContainer.appendChild(mediaElement);
                previewContainer.appendChild(deleteOverlay);

                // Add to preview grid
                const mediaPreviewGrid = document.getElementById('media_preview_grid');
                if (mediaPreviewGrid) {
                    mediaPreviewGrid.appendChild(previewContainer);
                }

                // Update the hidden input
                updateMediaPaths();
            };

            reader.readAsDataURL(file);
        });
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

// Initialize featured image preview
function initializeFeaturedImage() {
    if (window.entryData && window.entryData.photo) {
        const featuredPreview = document.getElementById('featured_image_preview');
        if (featuredPreview) {
            const photoPath = Array.isArray(window.entryData.photo)
                ? window.entryData.photo[0]
                : window.entryData.photo;
            featuredPreview.src = '/' + photoPath;
            featuredPreview.style.display = 'block';
        }
    }
}

function updateMediaPaths() {
    // Get all media elements from preview grid
    const mediaElements = document.querySelectorAll('#media_preview_grid img, #media_preview_grid video');
    const mediaPaths = Array.from(mediaElements).map(media => {
        // For new uploads (data URLs), use the fileName attribute
        if (media.src.includes('data:')) {
            return media.dataset.fileName || '';
        }
        // For existing media, get the full path
        return media.src.replace(window.location.origin + '/', '');
    }).filter(path => path); // Remove empty paths

    console.log('Updated media paths:', mediaPaths);

    // Update hidden inputs for both new and existing media
    const existingMediaInput = document.getElementById('existing_media');
    const newMediaInput = document.getElementById('new_media');

    if (existingMediaInput && newMediaInput) {
        // Split paths between existing and new
        const newPaths = mediaPaths.filter(path =>
            // Check if it's a new file (either starts with BULK_UPLOAD_DIR or is just a filename)
            path.startsWith(window.BULK_UPLOAD_DIR || '') ||
            !path.includes('/')
        );
        const existingPaths = mediaPaths.filter(path =>
            // Existing files have paths but don't start with BULK_UPLOAD_DIR
            path.includes('/') &&
            !path.startsWith(window.BULK_UPLOAD_DIR || '')
        );

        existingMediaInput.value = existingPaths.join(',');
        newMediaInput.value = newPaths.join(',');

        console.log('Existing media paths:', existingPaths);
        console.log('New media paths:', newPaths);
    } else {
        console.warn('Media input elements not found');
    }
}

