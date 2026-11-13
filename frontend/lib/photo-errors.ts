export type PhotoErrorCode =
  | "PHOTO_ISSUE"
  | "PERSON_NOT_DETECTED"
  | "SERVICE_BUSY"
  | "INTERNAL_SERVER_ERROR"
  | "INVALID_COUNTRY";

export type PhotoError = { code: PhotoErrorCode; title: string; detail: string };

export function photoError(code: PhotoErrorCode, detail?: string): PhotoError {
  const defaults: Record<PhotoErrorCode, { title: string; detail: string }> = {
    PHOTO_ISSUE: {
      title: "This photo needs a little attention",
      detail: "Try a clear, well-lit photo with your whole head and shoulders visible.",
    },
    PERSON_NOT_DETECTED: {
      title: "No person detected",
      detail: "Try another photo with your whole head and shoulders clearly visible.",
    },
    INTERNAL_SERVER_ERROR: {
      title: "We're having trouble creating your photo",
      detail: "Please try again in a moment. You don't need to change your photo.",
    },
    SERVICE_BUSY: {
      title: "The photo service is busy",
      detail: "Please wait a moment and try again. Your photo is still selected.",
    },
    INVALID_COUNTRY: {
      title: "Please check your country",
      detail: "Select a supported country and try again.",
    },
  };
  return { code, ...defaults[code], ...(detail ? { detail } : {}) };
}

export function normalizePhotoError(payload: unknown, status: number): PhotoError {
  const data = payload && typeof payload === "object"
    ? payload as { code?: unknown; detail?: unknown }
    : {};
  const detail = typeof data.detail === "string" ? data.detail : undefined;
  if (data.code === "INTERNAL_SERVER_ERROR") return photoError("INTERNAL_SERVER_ERROR");
  if (data.code === "SERVICE_BUSY" || status === 429 || status === 503) {
    return photoError("SERVICE_BUSY");
  }
  if (data.code === "PERSON_NOT_DETECTED") return photoError("PERSON_NOT_DETECTED");
  if (data.code === "PHOTO_ISSUE" || data.code === "INVALID_COUNTRY") {
    return photoError(data.code, detail);
  }
  // Support the original Python API while deployments are upgraded.
  if (detail === "No person detected") return photoError("PERSON_NOT_DETECTED");
  if (detail === "Confidence too low or wrong class" || detail === "Could not decode the uploaded image.") {
    return photoError("PHOTO_ISSUE");
  }
  // Unknown backend errors must not blame the photo or reveal exception text.
  if (status >= 500 || status === 404) return photoError("INTERNAL_SERVER_ERROR");
  return photoError("PHOTO_ISSUE");
}
