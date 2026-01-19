from PIL import Image, ImageDraw
import os

# Create icons directory if it doesn't exist
os.makedirs('static/icons', exist_ok=True)

# Define icon sizes
sizes = [72, 96, 128, 144, 192, 384, 512]

for size in sizes:
    # Create a new image with white background
    img = Image.new('RGB', (size, size), color='#0066cc')
    draw = ImageDraw.Draw(img)
    
    # Add "FM" text in the center
    # Note: This is a simple placeholder. For production, use proper logos
    
    # Save the image
    img.save(f'static/icons/icon-{size}x{size}.png')
    print(f'Created icon-{size}x{size}.png')

print("Icons created successfully!")
