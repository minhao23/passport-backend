import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO
from rembg import remove, new_session
import io

print("Loading models into memory...")
# Load models globally so they don't re-initialize on every API call
rembg_session = new_session("birefnet-portrait")
yolo_model = YOLO('best.pt')

def create_passport_photo(image_bytes: bytes) -> bytes:
    """
    Takes raw image bytes, processes them into a passport photo with a white background,
    and returns the processed image as JPEG bytes.
    """
    
    # Convert incoming bytes to a numpy array, then decode into an OpenCV image
    nparr = np.frombuffer(image_bytes, np.uint8)
    original_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if original_img is None:
        raise ValueError("Could not decode the uploaded image.")

    H, W = original_img.shape[:2]

    # ── BRANCH 1: rembg on the FULL image ──────────────────────────────────
    print("rembg on full image (birefnet-portrait)...")
    full_pil = Image.fromarray(cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB))
    rembg_full = remove(full_pil, session=rembg_session)
    rembg_np   = np.array(rembg_full)           # (H, W, 4) RGBA
    rembg_alpha = rembg_np[:, :, 3].astype(np.float32) / 255.0

    # ── BRANCH 2: YOLO segmentation pass ───────────────────────────────────
    print("YOLO segmentation pass...")
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

    # ── UNION / INTERSECTION blend ─────────────────────────────────────────
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

    # ── Composite ──────────────────────────────────────────────────────────
    result_rgba = rembg_np.copy()
    result_rgba[:, :, 3] = final_alpha_u8

    # ── Crop to bounding box ───────────────────────────────────────────────
    print("Cropping...")
    box = results[0].boxes[0].xyxy[0].cpu().numpy()
    x1, y1, x2, y2 = map(int, box)
    padding = 20
    x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
    x2, y2 = min(W, x2 + padding), min(H, y2 + padding)
    cropped = result_rgba[y1:y2, x1:x2]

    transparent_result = Image.fromarray(cropped, 'RGBA')

    # ── White background ───────────────────────────────────────────────────
    print("White background composite...")
    white_bg = Image.new("RGB", transparent_result.size, (255, 255, 255))
    white_bg.paste(transparent_result, (0, 0), transparent_result)
    
    # Save the result to a byte buffer instead of a file path
    img_byte_arr = io.BytesIO()
    white_bg.save(img_byte_arr, format='JPEG')
    
    return img_byte_arr.getvalue()