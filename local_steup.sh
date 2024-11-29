# Create main data directories
mkdir -p data
mkdir -p drafts
mkdir -p uploads
mkdir -p static

# Create temp directories for photo processing
mkdir -p images/temp
mkdir -p images/photos

# Ensure permissions are set correctly
chmod -R 755 data uploads images