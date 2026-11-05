import { ACCEPTED_TYPES, countries, MAX_FILE_SIZE } from "@/lib/countries";
import { normalizePhotoError, photoError } from "@/lib/photo-errors";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const country = form.get("country");
    const file = form.get("file");
    if (typeof country !== "string" || !Object.hasOwn(countries, country)) {
      return Response.json(photoError("INVALID_COUNTRY"), { status: 400 });
    }
    if (!(file instanceof File) || !ACCEPTED_TYPES.includes(file.type) || !file.size) {
      return Response.json(photoError("PHOTO_ISSUE", "Please upload a non-empty JPG, PNG, or WebP image."), { status: 400 });
    }
    if (file.size > MAX_FILE_SIZE) {
      return Response.json(photoError("PHOTO_ISSUE", "Your photo must be 10 MB or smaller."), { status: 413 });
    }
    const url = new URL("/images/process", process.env.BACKEND_URL || "http://127.0.0.1:8000");
    url.searchParams.set("country", country);
    const upstreamForm = new FormData();
    upstreamForm.set("file", file);
    const response = await fetch(url, {
      method: "POST",
      body: upstreamForm,
      signal: AbortSignal.timeout(180_000),
      cache: "no-store",
    });
    if (!response.ok) {
      const error = normalizePhotoError(await response.json().catch(() => null), response.status);
      const status = error.code === "INTERNAL_SERVER_ERROR" ? 502
        : error.code === "INVALID_COUNTRY" ? 400 : 422;
      return Response.json(error, { status });
    }
    if (!response.headers.get("content-type")?.startsWith("image/jpeg")) {
      return Response.json(photoError("INTERNAL_SERVER_ERROR"), { status: 502 });
    }
    return new Response(response.body, {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store" },
    });
  } catch (error) {
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return Response.json(photoError("INTERNAL_SERVER_ERROR", timeout
      ? "Processing is taking longer than expected. Please try again in a moment."
      : "The photo service is temporarily unavailable. Please try again in a moment."),
    { status: timeout ? 504 : 502 });
  }
}
