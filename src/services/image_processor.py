import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO
from rembg import remove, new_session
import io

from utils.passport_sizes import passport_photo_sizes_mm

print("Loading models into memory...")

def load_models():
    global rembg_session, yolo_model
    print("Loading models into memory...")
    rembg_session = new_session("birefnet-portrait")
    yolo_model = YOLO('best.pt')

def create_passport_photo(image_bytes: bytes, country: str) -> bytes:
    """
    Takes raw image bytes and a country string, processes them into a passport photo 
    with a white background, preserves aspect ratio (diagonal scaling), and 
    ensures the person is grounded at the bottom, maxing out either the width or 
    the 75% face-height rule.
    """
    if country not in passport_photo_sizes_mm:
        raise ValueError(f"Country '{country}' not found in database.")
        
    target_w_mm, target_h_mm = passport_photo_sizes_mm[country]
    target_ratio = target_w_mm / target_h_mm
    
    nparr = np.frombuffer(image_bytes, np.uint8)
    original_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if original_img is None:
        raise ValueError("Could not decode the uploaded image.")

    H, W = original_img.shape[:2]

    # Process Background Removal
    full_pil = Image.fromarray(cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB))
    rembg_full = remove(full_pil, session=rembg_session)
    rembg_np   = np.array(rembg_full)           # (H, W, 4) RGBA
    rembg_alpha = rembg_np[:, :, 3].astype(np.float32) / 255.0

    # Process YOLO Face Detection
    results = yolo_model.predict(original_img, conf=0.1, verbose=False)

    if len(results[0].boxes) == 0:
        raise Exception("No person detected")

    best_conf  = results[0].boxes.conf[0].item()
    best_class = int(results[0].boxes.cls[0].item())
    
    if best_class != 0 or best_conf < 0.65:
        raise Exception("Confidence too low or wrong class")

    masks = results[0].masks
    if masks is not None:
        seg_mask = masks.data[0].cpu().numpy()
        seg_mask = cv2.resize(seg_mask, (W, H), interpolation=cv2.INTER_LINEAR)
        yolo_alpha = seg_mask.astype(np.float32)
    else:
        box = results[0].boxes[0].xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = map(int, box)
        yolo_alpha = np.zeros((H, W), dtype=np.float32)
        yolo_alpha[y1:y2, x1:x2] = 1.0

    # Merge Alphas
    print("Merging alphas...")
    kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    yolo_bin = (yolo_alpha > 0.5).astype(np.uint8)
    eroded   = cv2.erode(yolo_bin,  kernel, iterations=1)   
    dilated  = cv2.dilate(yolo_bin, kernel, iterations=2)   

    final_alpha = np.zeros((H, W), dtype=np.float32)
    final_alpha[eroded == 1] = rembg_alpha[eroded == 1]

    transition = (dilated == 1) & (eroded == 0)
    yolo_weight = np.clip(yolo_alpha * 2.0, 0.0, 1.0)  
    final_alpha[transition] = (
        rembg_alpha[transition] * yolo_weight[transition]
    )

    final_alpha[dilated == 0] = 0.0

    final_alpha_u8 = (final_alpha * 255).astype(np.uint8)
    final_alpha_u8 = cv2.GaussianBlur(final_alpha_u8, (7, 7), 0)

    result_rgba = rembg_np.copy()
    result_rgba[:, :, 3] = final_alpha_u8

# ==========================================================
    # SMART CROPPING & DIAGONAL SCALING LOGIC
    # ==========================================================
    print("Calculating Proportions...")
    
    # 1. Get the absolute pixel bounds of the person's body from our alpha mask
    # This is much more accurate than the YOLO box because it perfectly wraps the visible pixels
    y_idx, x_idx = np.where(final_alpha > 0)
    if len(y_idx) > 0:
        px1, px2 = np.min(x_idx), np.max(x_idx)
        py1, py2 = np.min(y_idx), np.max(y_idx) # py1 = top of hair, py2 = lowest visible pixel
    else:
        px1, px2, py1, py2 = 0, W, 0, H

    center_x = px1 + ((px2 - px1) / 2.0)

    # 2. The Flawless Passport Math:
    # We want the person to span exactly from the 10% top margin down to the 0% bottom edge.
    # This means the person's visible height must equal exactly 90% of the canvas height.
    person_h = py2 - py1
    canvas_h = person_h / 0.90
    canvas_w = canvas_h * target_ratio
    
    canvas_w, canvas_h = int(canvas_w), int(canvas_h)

    # Convert the isolated person to a full PIL image
    transparent_full = Image.fromarray(result_rgba, 'RGBA')

    # Create a pure white canvas that mathematically matches our target Aspect Ratio perfectly
    white_bg = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    
    # 3. Calculate exact placements
    # Horizontal: Center the person perfectly in the middle
    paste_x = int((canvas_w / 2) - center_x)
    
    # Vertical: Anchor the absolute lowest pixel of the person to the absolute bottom of the canvas
    paste_y = int(canvas_h - py2)
    
    # Paste the person onto the white canvas
    # The shoulders will naturally extend outward and get cleanly cropped by the left/right edges!
    white_bg.paste(transparent_full, (paste_x, paste_y), transparent_full)
    
    # ==========================================================
    # FINAL EXPORT
    # ==========================================================
    print("Exporting...")

    pixels_per_mm = 11.81
    final_pixel_w = int(target_w_mm * pixels_per_mm)
    final_pixel_h = int(target_h_mm * pixels_per_mm)
    
    final_img = white_bg.resize((final_pixel_w, final_pixel_h), Image.Resampling.LANCZOS)

    img_byte_arr = io.BytesIO()
    final_img.save(img_byte_arr, format='JPEG', quality=95)
    
    return img_byte_arr.getvalue()