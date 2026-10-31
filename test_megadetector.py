
import json
from pathlib import Path

from megadetector.detection.run_detector import load_detector
from megadetector.detection.run_detector import try_download_known_detector
from megadetector.detection.run_detector import DEFAULT_OUTPUT_CONFIDENCE_THRESHOLD
from megadetector.detection import run_detector
from megadetector.detection import run_detector as md

from megadetector.detection.run_detector import load_detector
from megadetector.detection import run_detector

from megadetector.detection.run_detector import model_string_to_model_version
from megadetector.detection import run_detector

from megadetector.detection.run_detector import vis_utils

from megadetector.detection.run_detector import load_detector

from megadetector.detection import run_detector

from megadetector.detection.run_detector import try_download_known_detector

from megadetector.detection.run_detector import DEFAULT_OUTPUT_CONFIDENCE_THRESHOLD

from megadetector.detection.run_detector import load_detector

image_path = Path("test.png").resolve()
output_path = Path("megadetector_predictions.json")

# Load the MegaDetector model
model_file = try_download_known_detector("MDV5A")
detector = load_detector(model_file)

# Load the image
image = vis_utils.load_image(str(image_path))

# Run animal detection
result = detector.generate_detections_one_image(
    image,
    str(image_path),
    detection_threshold=DEFAULT_OUTPUT_CONFIDENCE_THRESHOLD
)

# Save the results
with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

print("MegaDetector predictions saved successfully!")
print(json.dumps(result, indent=2))
