#!/bin/bash
# Pre-deploy script for Render
set -e

echo "=== Starting deployment preparation ==="
echo "Python version: $(python --version)"
echo "Django version: $(python -c "import django; print(django.get_version())")"

echo "1. Ensuring proper static file structure..."
# Create required directories
mkdir -p static/{css,js,images,icons}
mkdir -p website/static/website/{css,js,images}

# Copy any website app static files to proper location
if [ -d "website/static/images" ]; then
    cp -r website/static/images/* website/static/website/images/ 2>/dev/null || true
fi
if [ -d "website/static/js" ]; then
    cp -r website/static/js/* website/static/website/js/ 2>/dev/null || true
fi

# Also copy to project static for backup
if [ -d "website/static/images" ]; then
    cp -r website/static/images/* static/images/ 2>/dev/null || true
fi

echo "2. Running database migrations..."
python manage.py migrate --noinput

echo "3. Collecting static files..."
python manage.py collectstatic --noinput -v 2

echo "4. Checking collected static files..."
if [ -d "staticfiles" ]; then
    count=$(find staticfiles -type f | wc -l)
    echo "✅ Collected $count files in staticfiles/"
    if [ $count -eq 0 ]; then
        echo "⚠️  WARNING: No static files were collected!"
        echo "Listing static directories:"
        find . -type d -name "static" | grep -v venv
    fi
else
    echo "❌ ERROR: staticfiles directory not created!"
fi

echo "=== Deployment preparation complete! ==="
