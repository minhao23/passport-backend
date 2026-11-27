import { ACCEPTED_TYPES, HEIC_TYPES, MAX_FILE_SIZE } from "./countries";

export class PhotoInputError extends Error {}

export function isHeicPhoto(file: File): boolean {
  return (
    HEIC_TYPES.includes(file.type) ||
    (!file.type && /\.(heic|heif)$/i.test(file.name))
  );
}

const dimensionError =
  "This photo's dimensions are too large. Use a photo of 20 megapixels or fewer, with neither side exceeding 10,000 pixels.";
const decodeError =
  "This image couldn't be opened. Please choose another photo.";

function checkDimensions(width: number, height: number) {
  if (!width || !height) throw new PhotoInputError(decodeError);
  if (width * height > 20_000_000 || Math.max(width, height) > 10_000)
    throw new PhotoInputError(dimensionError);
}

// Read HEIF spatial-extent properties before a decoder allocates the pixels.
export async function checkHeicDimensions(file: Blob): Promise<void> {
  const data = new DataView(await file.arrayBuffer());
  const kind = (offset: number) =>
    String.fromCharCode(...[0, 1, 2, 3].map((i) => data.getUint8(offset + i)));
  let found = false;
  if (data.byteLength < 12 || kind(4) !== "ftyp")
    throw new PhotoInputError(decodeError);
  function walk(start: number, end: number, depth = 0) {
    if (depth > 3) throw new PhotoInputError(decodeError);
    for (let offset = start; offset < end; ) {
      if (offset + 8 > end) throw new PhotoInputError(decodeError);
      let size = data.getUint32(offset);
      let header = 8;
      if (size === 1) {
        if (offset + 16 > end || data.getUint32(offset + 8) !== 0)
          throw new PhotoInputError(decodeError);
        size = data.getUint32(offset + 12);
        header = 16;
      } else if (size === 0) size = end - offset;
      if (size < header || size > end - offset)
        throw new PhotoInputError(decodeError);
      const type = kind(offset + 4);
      const body = offset + header;
      const next = offset + size;
      if (type === "ispe") {
        if (next - body < 12) throw new PhotoInputError(decodeError);
        checkDimensions(data.getUint32(body + 4), data.getUint32(body + 8));
        found = true;
      } else if (type === "meta" || type === "iprp" || type === "ipco") {
        const children = body + (type === "meta" ? 4 : 0);
        if (children > next) throw new PhotoInputError(decodeError);
        walk(children, next, depth + 1);
      }
      offset = next;
    }
  }
  walk(0, data.byteLength);
  if (!found) throw new PhotoInputError(decodeError);
}

async function loadImage(file: Blob): Promise<HTMLImageElement> {
  const image = new Image();
  const url = URL.createObjectURL(file);
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new PhotoInputError(decodeError));
      image.src = url;
    });
    return image;
  } finally {
    image.onload = image.onerror = null;
    URL.revokeObjectURL(url);
  }
}

let conversionQueue: Promise<unknown> = Promise.resolve();

async function convertHeic(file: File): Promise<File> {
  let blob: Blob;
  let image: HTMLImageElement | undefined;
  try {
    image = await loadImage(file);
  } catch {
    // Older browsers cannot display HEIC. Keep the decoder off the initial bundle.
  }
  if (image) {
    const canvas = document.createElement("canvas");
    try {
      checkDimensions(image.naturalWidth, image.naturalHeight);
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) throw new PhotoInputError(decodeError);
      context.drawImage(image, 0, 0);
      blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (value) =>
            value?.size
              ? resolve(value)
              : reject(new PhotoInputError(decodeError)),
          "image/jpeg",
          1,
        );
      });
    } finally {
      image.src = "";
      canvas.width = canvas.height = 0;
    }
  } else {
    const { heicTo } = await import("heic-to/csp");
    blob = await heicTo({ blob: file, type: "image/jpeg", quality: 1 });
  }
  if (!blob.size || blob.type !== "image/jpeg")
    throw new PhotoInputError(decodeError);
  if (blob.size > MAX_FILE_SIZE)
    throw new PhotoInputError(
      "This photo exceeds 15 MB after conversion. Export a smaller JPEG and try again.",
    );
  const name = file.name.replace(/\.[^.]+$/, "") || "photo";
  return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
}

export async function preparePhoto(file: File): Promise<File> {
  const heic = isHeicPhoto(file);
  if (!heic && !ACCEPTED_TYPES.includes(file.type))
    throw new PhotoInputError(
      "Please choose a JPG, PNG, WebP, HEIC, or HEIF photo.",
    );
  if (!file.size || file.size > MAX_FILE_SIZE)
    throw new PhotoInputError(
      "Please choose a non-empty photo that is 15 MB or smaller.",
    );
  if (heic) {
    await checkHeicDimensions(file);
    const converted = conversionQueue.then(() => convertHeic(file));
    conversionQueue = converted.catch(() => {});
    return converted;
  }
  try {
    const bitmap = await createImageBitmap(file);
    bitmap.close();
  } catch {
    // Image elements also work in Safari versions without createImageBitmap.
    const image = await loadImage(file);
    image.src = "";
  }
  return file;
}
