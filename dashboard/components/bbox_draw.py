"""bbox_draw.py - draw normalised (x, y, w, h) boxes on an image."""
from PIL import Image, ImageDraw


def draw_boxes(image_path, bboxes, color="lime", width=4):
    img = Image.open(image_path).convert("RGB")
    d = ImageDraw.Draw(img)
    iw, ih = img.size
    for x, y, w, h in bboxes:
        d.rectangle([int(x * iw), int(y * ih), int((x + w) * iw), int((y + h) * ih)], outline=color, width=width)
    return img
