import os
from PIL import Image

mock_dir = "tests/e2e/mock_recording"
os.makedirs(mock_dir, exist_ok=True)

# Generate 3 frames representing 3 seconds of a mock simulation
for i in range(3):
    img = Image.new('RGB', (800, 600), color = (73, 109, 137))
    filename = f"frame_26_04_30_12_00_0{i}_0000_00000{i}.jpg"
    img.save(os.path.join(mock_dir, filename))

print(f"Created 3 mock frames in {mock_dir}")
