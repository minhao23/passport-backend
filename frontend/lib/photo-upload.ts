import { MAX_FILE_SIZE } from "./countries";
import { UPLOAD_TIMEOUT_MS } from "./processing-limits";

export const MAX_REQUEST_BYTES = MAX_FILE_SIZE + 64 * 1024;

export class PhotoUploadError extends Error {
  constructor(message: string, public readonly status = 400) {
    super(message);
  }
}

export async function readPhotoForm(request: Request): Promise<FormData> {
  const length = request.headers.get("content-length");
  if (length && Number(length) > MAX_REQUEST_BYTES) {
    throw new PhotoUploadError("Please upload one photo of 10 MB or smaller.", 413);
  }
  const contentType = request.headers.get("content-type") || "";
  if (!/^multipart\/form-data(?:;|$)/i.test(contentType) || !request.body) {
    throw new PhotoUploadError("Please upload a photo using the upload form.");
  }

  const reader = request.body.getReader();
  let received = 0;
  let timer: ReturnType<typeof setTimeout>;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new PhotoUploadError(
      "The upload took too long. Check your connection and try again.", 408,
    )), UPLOAD_TIMEOUT_MS);
  });

  try {
    const chunks: Uint8Array<ArrayBuffer>[] = [];
    while (true) {
      const chunk = await Promise.race([reader.read(), deadline]);
      if (chunk.done) break;
      received += chunk.value.byteLength;
      if (received > MAX_REQUEST_BYTES) {
        throw new PhotoUploadError("Please upload one photo of 10 MB or smaller.", 413);
      }
      chunks.push(new Uint8Array(chunk.value));
    }
    const form = await new Response(new Blob(chunks), {
      headers: { "Content-Type": contentType },
    }).formData();
    const fields = [...form.keys()];
    if (fields.length !== 2 || !form.has("file") || !form.has("country")) {
      throw new PhotoUploadError("Please upload one photo and select a country.");
    }
    return form;
  } catch (error) {
    if (error instanceof PhotoUploadError || request.signal.aborted) throw error;
    throw new PhotoUploadError("We couldn't read this upload. Please try again.");
  } finally {
    clearTimeout(timer!);
    // Cancelling IncomingMessage destroys its socket before JSON can be sent.
    // The route disposes unread bytes after writing the error response.
    reader.releaseLock();
  }
}

export async function disposeRejectedUpload(request: Request): Promise<void> {
  if (!request.body || request.body.locked) return;
  const reader = request.body.getReader();
  let done = false;
  let discarded = 0;
  let timer: ReturnType<typeof setTimeout>;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error("Upload drain deadline")), 1000);
  });
  try {
    // Let an ordinary sender finish without retaining its rejected payload.
    // Both time and bytes are bounded for clients that continue uploading.
    while (discarded <= 2 * MAX_REQUEST_BYTES) {
      const chunk = await Promise.race([reader.read(), deadline]);
      if (chunk.done) {
        done = true;
        break;
      }
      discarded += chunk.value.byteLength;
    }
  } catch {
    // Disconnected and stalled senders only need transport cleanup.
  } finally {
    clearTimeout(timer!);
    // Iterator cancellation can wait on a pending native read. Do not let that
    // extend the cleanup deadline or retain an application admission slot.
    if (!done) void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
