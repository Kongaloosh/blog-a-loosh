// Initialize MathJax safely
function initMathJax() {
    // Wait for MathJax to be fully loaded
    window.MathJax = {
        tex: {
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$', '$$'], ['\\[', '\\]']],
        },
        svg: {
            fontCache: 'global'
        },
        startup: {
            ready: () => {
                console.log('MathJax is loaded and ready');
            }
        }
    };
}

// State management
const state = {
    text: "",
    img: "",
    title: "",
    summary: "",
    travel: [],
    event: {},
    geo: null
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

function updatePreview(elementId, previewId, value) {
    const previewElement = document.getElementById(previewId);
    // Only update if the value has actually changed
    if (previewElement && value !== state[elementId]) {
        state[elementId] = value;  // Update state first
        previewElement.innerHTML = value;
    }
}

// Markdown to HTML conversion with proper error handling
const getHTMLFromMD = debounce(async (val) => {
    const wysiwyg = document.getElementById("wysiwyg");
    if (!wysiwyg) return;

    // Save location preview if it exists
    const locationPreview = wysiwyg.querySelector('.location-preview');
    const locationHTML = locationPreview?.outerHTML;

    if (!val) {
        wysiwyg.innerHTML = locationHTML || '';
        return;
    }

    try {
        const token = getCSRFToken();
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

        // Combine location preview with markdown content
        wysiwyg.innerHTML = (locationHTML || '') + result.html;

        // Add responsive classes to images
        const images = wysiwyg.getElementsByTagName('img');
        Array.from(images).forEach(img => {
            img.classList.add('img-fluid', 'mx-auto', 'd-block');
        });

        // Typeset math if present
        if (window.MathJax?.typesetPromise) {
            await window.MathJax.typesetPromise([wysiwyg]);
        }
    } catch (error) {
        console.error('Preview error:', error);
        wysiwyg.innerHTML = `
            ${locationHTML || ''}
            <div class="alert alert-warning">
                Preview temporarily unavailable: ${error.message}
            </div>`;
    }
}, 300);

// Initialize all previews and listeners
function initializePreviews() {
    console.log("Initializing previews...");

    // Remove any existing listeners before adding new ones
    const titleInput = document.getElementById('title_form');
    const summaryInput = document.getElementById('summary_form');
    const textInput = document.getElementById('text_input');

    if (titleInput) {
        const newTitleInput = titleInput.cloneNode(true);
        titleInput.parentNode.replaceChild(newTitleInput, titleInput);
        newTitleInput.addEventListener('input', function (e) {
            updatePreview('title', 'title_format', e.target.value);
        });
        if (newTitleInput.value) {
            updatePreview('title', 'title_format', newTitleInput.value);
        }
    }

    if (summaryInput) {
        const newSummaryInput = summaryInput.cloneNode(true);
        summaryInput.parentNode.replaceChild(newSummaryInput, summaryInput);
        newSummaryInput.addEventListener('input', function (e) {
            updatePreview('summary', 'summary_format', e.target.value);
        });
        if (newSummaryInput.value) {
            updatePreview('summary', 'summary_format', newSummaryInput.value);
        }
    }

    if (textInput) {
        const newTextInput = textInput.cloneNode(true);
        textInput.parentNode.replaceChild(newTextInput, textInput);
        newTextInput.addEventListener('input', function (e) {
            getHTMLFromMD(e.target.value);
        });
        if (newTextInput.value) {
            getHTMLFromMD(newTextInput.value);
        }
    }

    // Initialize MathJax
    initMathJax();

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
        // Add existing videos if any
        if (window.entryData && Array.isArray(window.entryData.video)) {
            console.log("Loading videos:", window.entryData.video);

            window.entryData.video.forEach(function (videoPath) {
                if (!videoPath) return; // Skip null/undefined entries

                console.log("Adding video:", videoPath);
                const previewContainer = document.createElement('div');
                previewContainer.className = 'media-preview video-preview';

                const video = document.createElement('video');
                video.src = '/' + videoPath;
                video.controls = true;
                video.classList.add('img-fluid');

                // Create delete button instead of overlay
                const deleteButton = document.createElement('button');
                deleteButton.className = 'video-delete-btn';
                deleteButton.style.width = '100%';
                deleteButton.innerHTML = '<i class="fa fa-times-circle"></i>';
                deleteButton.onclick = function (e) {
                    e.stopPropagation(); // Prevent click from reaching video
                    if (confirm('Are you sure you want to delete this video?')) {
                        const previewContainer = deleteButton.closest('.video-preview');
                        if (previewContainer) {
                            previewContainer.remove();
                            updateMediaPaths();
                        }
                    }
                };

                previewContainer.appendChild(video);
                previewContainer.appendChild(deleteButton);
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

    // Initialize location preview
    initializeLocationPreview();
}

// Remove duplicate initialization calls
document.addEventListener('DOMContentLoaded', function () {
    // Remove any existing event listeners
    const oldElement = document.querySelector('script[data-initialization="true"]');
    if (oldElement) {
        oldElement.remove();
    }

    // Add initialization script with marker
    const script = document.createElement('script');
    script.setAttribute('data-initialization', 'true');
    script.textContent = `
        initializeTagSystem();
        initializePreviews();
    `;
    document.body.appendChild(script);
});

function handlePhotoUpload(input) {
    Array.from(input.files).forEach(file => {
        const isVideo = file.type.startsWith('video/');
        let mediaElement;
        let previewContainer = document.createElement('div');
        previewContainer.className = 'media-preview';

        if (isVideo) {
            mediaElement = document.createElement('video');
            // Create an object URL instead of using FileReader
            mediaElement.src = URL.createObjectURL(file);
            mediaElement.controls = true;
            mediaElement.preload = 'auto';
            mediaElement.classList.add('img-fluid');

            // Add loading indicator
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'loading-spinner';
            loadingSpinner.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
            previewContainer.appendChild(loadingSpinner);

            // Wait for video data to fully load
            mediaElement.addEventListener('loadeddata', function () {
                loadingSpinner.remove();
                // Ensure video is visible in preview
                mediaElement.currentTime = 0;

                // Create a poster frame after data is loaded
                const canvas = document.createElement('canvas');
                canvas.width = mediaElement.videoWidth;
                canvas.height = mediaElement.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(mediaElement, 0, 0, canvas.width, canvas.height);
                mediaElement.poster = canvas.toDataURL();
            });

            // Add error handling
            mediaElement.addEventListener('error', function (e) {
                console.error('Video loading error:', e);
                loadingSpinner.innerHTML = '<i class="fa fa-exclamation-circle"></i> Error loading video';
            });

            // Clean up object URL when video is loaded
            mediaElement.addEventListener('loadeddata', function () {
                URL.revokeObjectURL(mediaElement.src);
            });
        } else {
            // For images, continue using FileReader
            const reader = new FileReader();
            reader.onload = function (e) {
                mediaElement = document.createElement('img');
                mediaElement.src = e.target.result;
                mediaElement.classList.add('img-fluid');
                finishPreviewSetup();
            };
            reader.readAsDataURL(file);
            return; // Exit early for images, rest will be handled in onload
        }

        // Setup function for both videos and images
        function finishPreviewSetup() {
            mediaElement.dataset.fileName = file.name;

            const deleteOverlay = document.createElement('div');
            deleteOverlay.className = 'delete-overlay';
            deleteOverlay.innerHTML = '<i class="fa fa-times-circle delete-icon"></i>';

            deleteOverlay.onclick = function () {
                if (confirm('Are you sure you want to delete this media?')) {
                    previewContainer.remove();
                    updateMediaPaths();
                }
            };

            previewContainer.appendChild(mediaElement);
            previewContainer.appendChild(deleteOverlay);

            const mediaPreviewGrid = document.getElementById('media_preview_grid');
            if (mediaPreviewGrid) {
                mediaPreviewGrid.appendChild(previewContainer);
            }

            updateMediaPaths();
        }

        // For videos, call finishPreviewSetup immediately
        if (isVideo) {
            finishPreviewSetup();
        }
    });
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
        <span class="badge rounded-pill bg-light text-dark border me-2 mb-2">
            <span class="d-inline-flex align-items-center py-2 px-3">
                ${tag}
                <i class="fa fa-times ms-2 tag-remove-button" onclick="removeTag('${tag}')" aria-label="Remove" style="cursor: pointer; font-size: 0.7em;"></i>
            </span>
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
    const existingPhotosInput = document.getElementById('existing_photos');
    const newPhotosInput = document.getElementById('new_photos');
    const existingVideosInput = document.getElementById('existing_videos');
    const newVideosInput = document.getElementById('new_videos');

    if (existingPhotosInput && newPhotosInput && existingVideosInput && newVideosInput) {
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

        // Separate photos and videos
        const existingPhotos = existingPaths.filter(path => path.match(/\.(jpg|jpeg|png|gif)$/i));
        const existingVideos = existingPaths.filter(path => path.match(/\.(mp4|mov|avi|wmv|flv|mkv)$/i));

        existingPhotosInput.value = existingPhotos.join(',');
        newPhotosInput.value = newPaths.filter(path => path.match(/\.(jpg|jpeg|png|gif)$/i)).join(',');
        existingVideosInput.value = existingVideos.join(',');
        newVideosInput.value = newPaths.filter(path => path.match(/\.(mp4|mov|avi|wmv|flv|mkv)$/i)).join(',');

        console.log('Existing photos paths:', existingPhotos);
        console.log('New photos paths:', newPhotosInput.value);
        console.log('Existing videos paths:', existingVideos);
        console.log('New videos paths:', newVideosInput.value);
    } else {
        console.warn('Media input elements not found');
    }
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const button = document.querySelector(`button[onclick="toggleSection('${sectionId}')"] i`);

    if (section.style.display === 'none') {
        section.style.display = 'block';
        button.style.transform = 'rotate(90deg)';
    } else {
        section.style.display = 'none';
        button.style.transform = 'rotate(0deg)';
    }
}

function initializeLocationPreview() {
    const geoName = document.getElementById('geo_name')?.value;
    if (geoName) {
        updateLocationPreview(geoName);
    }
}

function createPreviewFooter() {
    const geoName = document.getElementById('geo_name')?.value;
    const publishDate = document.getElementById('publish_date')?.value;

    return `
    <hr>
    <div class="row post-meta">
        <div class="col-md-8 pull-left">
            <p>
                Posted by on
                <time class="dt-published">${publishDate || 'now'}</time>
                by
                <a rel="author" class="p-author h-card" href="http://kongaloosh.com">Alex Kearney</a>
                ${geoName ? `
                in
                <a class="p-location" style="overflow:scroll;">${geoName}</a>
                ` : ''}
            </p>
        </div>
    </div>`;
}

function updateContent() {
    const content = document.getElementById('content').value;
    const contentDiv = document.getElementById('wysiwyg-content');
    const footerDiv = document.getElementById('wysiwyg-footer');

    if (contentDiv && footerDiv) {
        // Update content with markdown
        contentDiv.innerHTML = marked.parse(content);
        // Update footer
        footerDiv.innerHTML = createPreviewFooter();
    }

    // Update state
    state.text = content;
}

// Make sure any content input triggers this
document.getElementById('content')?.addEventListener('input', updateContent);

// Add some CSS to the page
const style = document.createElement('style');
style.textContent = `
    #wysiwyg-content {
        min-height: 200px;
        margin-bottom: 20px;
    }
    #wysiwyg-footer {
        border-top: 1px solid #eee;
        padding-top: 15px;
        margin-top: 20px;
    }
`;
document.head.appendChild(style);

