import { after } from "next/server";
import { ACCEPTED_TYPES, countries, MAX_FILE_SIZE } from "@/lib/countries";
import { normalizePhotoError, photoError } from "@/lib/photo-errors";
import { disposeRejectedUpload, PhotoUploadError, readPhotoForm } from "@/lib/photo-upload";
import { UPSTREAM_TIMEOUT_MS } from "@/lib/processing-limits";

export const runtime = "nodejs";

// Matches two backend workers plus two uploading/waiting requests by default.
const MAX_ACTIVE_REQUESTS = 4;
let activeRequests = 0;
const noStore = { "Cache-Control": "no-store" };

export async function POST(request: Request) {
  if (activeRequests >= MAX_ACTIVE_REQUESTS) {
    return Response.json(photoError("SERVICE_BUSY"), {
      status: 503, headers: { ...noStore, "Retry-After": "10", Connection: "close" },
    });
  }
  activeRequests++;
  let deferredCleanup = false;
  try {
    const form = await readPhotoForm(request);
    const country = form.get("country");
    const file = form.get("file");
    if (typeof country !== "string" || !Object.hasOwn(countries, country)) {
      return Response.json(photoError("INVALID_COUNTRY"), { status: 400, headers: noStore });
    }
    if (!(file instanceof File) || !ACCEPTED_TYPES.includes(file.type) || !file.size) {
      return Response.json(photoError("PHOTO_ISSUE", "Please upload a non-empty JPG, PNG, or WebP image."), { status: 400, headers: noStore });
    }
    if (file.size > MAX_FILE_SIZE) {
      return Response.json(photoError("PHOTO_ISSUE", "Your photo must be 10 MB or smaller."), { status: 413, headers: noStore });
    }
    const url = new URL("/images/process", process.env.BACKEND_URL || "http://127.0.0.1:8000");
    url.searchParams.set("country", country);
    const upstreamForm = new FormData();
    upstreamForm.set("file", file);
    const response = await fetch(url, {
      method: "POST",
      body: upstreamForm,
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(UPSTREAM_TIMEOUT_MS)]),
      cache: "no-store",
    });
    if (!response.ok) {
      const error = normalizePhotoError(await response.json().catch(() => null), response.status);
      const status = error.code === "SERVICE_BUSY" ? 503
        : response.status === 413 || response.status === 408 ? response.status
        : error.code === "INTERNAL_SERVER_ERROR" ? 502
        : error.code === "INVALID_COUNTRY" ? 400 : 422;
      return Response.json(error, {
        status, headers: { ...noStore, ...(status === 503 ? { "Retry-After": "10" } : {}) },
      });
    }
    if (!response.headers.get("content-type")?.startsWith("image/jpeg")) {
      return Response.json(photoError("INTERNAL_SERVER_ERROR"), { status: 502, headers: noStore });
    }
    return new Response(response.body, {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store" },
    });
  } catch (error) {
    if (request.signal.aborted) {
      return new Response(null, { status: 499 });
    }
    if (error instanceof PhotoUploadError) {
      after(async () => {
        try {
          await disposeRejectedUpload(request);
        } finally {
          activeRequests--;
        }
      });
      deferredCleanup = true;
      return Response.json(photoError("PHOTO_ISSUE", error.message), {
        status: error.status, headers: noStore,
      });
    }
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return Response.json(photoError("INTERNAL_SERVER_ERROR", timeout
      ? "Processing is taking longer than expected. Please try again in a moment."
      : "The photo service is temporarily unavailable. Please try again in a moment."),
    { status: timeout ? 504 : 502, headers: noStore });
  } finally {
    if (!deferredCleanup) activeRequests--;
  }
}
