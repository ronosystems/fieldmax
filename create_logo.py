from PIL import Image, ImageDraw, ImageFont
import os

# Create a simple logo
img = Image.new('RGB', (200, 200), color='#0066cc')
draw = ImageDraw.Draw(img)

# Add text (requires a font file, using default for simplicity)
try:
    # Try to use a system font
    import matplotlib.font_manager as fm
    font_path = fm.findfont(fm.FontProperties(family='sans-serif'))
    font = ImageFont.truetype(font_path, 40)
except:
    # Fallback to default font
    font = ImageFont.load_default()

# Draw text
draw.text((50, 80), "FM", fill='white', font=font)
draw.text((30, 130), "FieldMax", fill='white', font=font)

# Save
os.makedirs('static/images', exist_ok=True)
img.save('static/images/LOGO.jpg')
print("Created LOGO.jpg")
