import io
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Assuming you have already fetched your Tibber data and it is in the `data` variable

class Camera:
    def __init__(self, data):
        self.data = data

    def generate_image(self):
        # Define image dimensions
        width, height = 600, 400

        # Create a blank image with white background
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        # Define some sample data to plot, replace this with your actual data
        times = [point['time'] for point in self.data]
        values = [point['value'] for point in self.data]

        # Normalizing data for the image
        max_value = max(values)
        min_value = min(values)
        range_value = max_value - min_value
        values_normalized = [(value - min_value) / range_value * (height - 40) for value in values]

        # Draw a simple line graph
        for i in range(1, len(values_normalized)):
            draw.line([(i-1) * (width // len(values_normalized)), height - values_normalized[i-1],
                       i * (width // len(values_normalized)), height - values_normalized[i]], fill='blue')

        # Draw axis
        draw.line([(0, height), (width, height)], fill='black')
        draw.line([(0, 0), (0, height)], fill='black')

        # Add labels
        font = ImageFont.load_default()
        draw.text((width // 2, height - 20), "Time", font=font, fill='black')
        draw.text((10, 10), f"Value: {min_value} - {max_value}", font=font, fill='black')

        # Save to a bytes buffer
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

# Example usage
data = [
    {"time": "2024-06-20T00:00:00Z", "value": 10},
    {"time": "2024-06-20T01:00:00Z", "value": 15},
    {"time": "2024-06-20T02:00:00Z", "value": 7},
    # Add more data points as needed
]

camera = Camera(data)
image_bytes = camera.generate_image()

# Save the image to a file for testing
with open("output.png", "wb") as f:
    f.write(image_bytes)
