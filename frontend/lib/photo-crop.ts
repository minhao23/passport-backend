import type { PercentCrop } from "react-image-crop";

export const FULL_PHOTO_CROP: PercentCrop = {
  unit: "%",
  x: 0,
  y: 0,
  width: 100,
  height: 100,
};

export function cropPixels(
  crop: PercentCrop,
  imageWidth: number,
  imageHeight: number,
) {
  if (
    ![crop.x, crop.y, crop.width, crop.height, imageWidth, imageHeight].every(
      Number.isFinite,
    ) ||
    imageWidth < 1 ||
    imageHeight < 1 ||
    crop.width <= 0 ||
    crop.height <= 0
  ) {
    throw new Error("Select a rectangle inside your photo.");
  }

  const x = Math.max(0, Math.round((crop.x / 100) * imageWidth));
  const y = Math.max(0, Math.round((crop.y / 100) * imageHeight));
  const right = Math.min(
    imageWidth,
    Math.round(((crop.x + crop.width) / 100) * imageWidth),
  );
  const bottom = Math.min(
    imageHeight,
    Math.round(((crop.y + crop.height) / 100) * imageHeight),
  );
  if (right <= x || bottom <= y) {
    throw new Error("Select a larger rectangle inside your photo.");
  }
  return { x, y, width: right - x, height: bottom - y };
}

export async function createCroppedFile(
  original: File,
  image: HTMLImageElement,
  crop: PercentCrop,
  maxFileSize: number,
): Promise<File> {
  const { x, y, width, height } = cropPixels(
    crop,
    image.naturalWidth,
    image.naturalHeight,
  );
  if (
    x === 0 &&
    y === 0 &&
    width === image.naturalWidth &&
    height === image.naturalHeight
  ) {
    return original;
  }
  // Bound the canvas before allocation, matching the processor's image limits.
  if (width * height > 20_000_000 || Math.max(width, height) > 10_000) {
    throw new Error(
      "Choose a smaller crop: at most 20 megapixels and 10,000 pixels per side.",
    );
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  try {
    const context = canvas.getContext("2d");
    if (!context)
      throw new Error(
        "Your browser couldn't crop this photo. Please try again.",
      );
    context.drawImage(image, x, y, width, height, 0, 0, width, height);
    // PNG avoids an extra lossy JPEG encode before passport processing.
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (value) =>
          value?.size
            ? resolve(value)
            : reject(
                new Error(
                  "Your browser couldn't save this crop. Please try again.",
                ),
              ),
        "image/png",
      );
    });
    if (blob.size > maxFileSize) {
      throw new Error(
        "This crop is over 15 MB. Select a smaller area or use a smaller photo.",
      );
    }
    const name = original.name.replace(/\.[^.]+$/, "") || "photo";
    return new File([blob], `${name}-cropped.png`, { type: "image/png" });
  } finally {
    canvas.width = 0;
    canvas.height = 0;
  }
}
