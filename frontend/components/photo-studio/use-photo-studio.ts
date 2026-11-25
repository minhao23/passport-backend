"use client";

import { useEffect, useRef, useState } from "react";
import type { PercentCrop } from "react-image-crop";
import { ACCEPTED_TYPES, countries, MAX_FILE_SIZE } from "@/lib/countries";
import { downloadPassportPhoto } from "@/lib/photo-download";
import {
  normalizePhotoError,
  photoError,
  type PhotoError,
} from "@/lib/photo-errors";
import { PHOTO_REQUEST_TIMEOUT_MS } from "@/lib/processing-limits";

export function usePhotoStudio() {
  const [country, setCountry] = useState("United States");
  const [file, setFile] = useState<File | null>(null);
  const [originalFile, setOriginalFile] = useState<File | null>(null);
  const [savedCrop, setSavedCrop] = useState<PercentCrop | null>(null);
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState<PhotoError | null>(null);
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  const selection = useRef(0);
  const originalSelection = useRef<File | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    return () => {
      if (result) URL.revokeObjectURL(result);
    };
  }, [result]);

  useEffect(() => {
    return () => {
      const controller = request.current;
      request.current = null;
      controller?.abort();
    };
  }, []);

  async function selectFile(next?: File) {
    if (!next || request.current) return;
    const version = ++selection.current;
    setError(null);
    if (!ACCEPTED_TYPES.includes(next.type)) {
      setError(
        photoError("PHOTO_ISSUE", "Please choose a JPG, PNG, or WebP photo."),
      );
      return;
    }
    if (!next.size || next.size > MAX_FILE_SIZE) {
      setError(
        photoError(
          "PHOTO_ISSUE",
          "Please choose a non-empty photo that is 10 MB or smaller.",
        ),
      );
      return;
    }
    try {
      const bitmap = await createImageBitmap(next);
      bitmap.close();
      if (version !== selection.current) return;
      originalSelection.current = next;
      setOriginalFile(next);
      setSavedCrop(null);
      setFile(next);
      setResult("");
    } catch {
      if (version === selection.current) {
        setError(
          photoError(
            "PHOTO_ISSUE",
            "This image couldn't be opened. Please choose another photo.",
          ),
        );
      }
    }
  }

  function applyCrop(original: File, cropped: File, crop: PercentCrop) {
    if (request.current || originalSelection.current !== original) return false;
    ++selection.current;
    setFile(cropped);
    setSavedCrop(cropped === original ? null : crop);
    setResult("");
    setError(null);
    return true;
  }

  function changeCountry(next: string) {
    setCountry(next);
    setResult("");
    setError(null);
  }

  function removePhoto() {
    if (request.current) return;
    ++selection.current;
    originalSelection.current = null;
    setOriginalFile(null);
    setSavedCrop(null);
    setFile(null);
    setResult("");
    setError(null);
  }

  function cancelProcessing() {
    const controller = request.current;
    if (!controller) return;
    // Invalidate first so late responses cannot overwrite a replacement or retry.
    request.current = null;
    controller.abort();
    setLoading(false);
    setError(null);
  }

  async function generate() {
    if (!file || request.current) return;
    ++selection.current;
    setLoading(true);
    setError(null);
    setResult("");
    const controller = new AbortController();
    request.current = controller;
    const timer = setTimeout(
      () => controller.abort(),
      PHOTO_REQUEST_TIMEOUT_MS,
    );
    try {
      const form = new FormData();
      form.set("country", country);
      form.set("file", file);
      const response = await fetch("/api/process", {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
      if (request.current !== controller) return;
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        if (request.current !== controller) return;
        setError(normalizePhotoError(data, response.status));
        return;
      }
      const blob = await response.blob();
      if (request.current !== controller) return;
      if (!blob.size || !blob.type.startsWith("image/jpeg")) {
        setError(photoError("INTERNAL_SERVER_ERROR"));
        return;
      }
      const resultUrl = URL.createObjectURL(blob);
      setResult(resultUrl);
      downloadPassportPhoto(resultUrl, country);
    } catch (err) {
      if (request.current !== controller) return;
      setError(
        photoError(
          "INTERNAL_SERVER_ERROR",
          err instanceof Error && err.name === "AbortError"
            ? "Processing is taking longer than expected. Please try again in a moment."
            : "We couldn't connect to the photo service. Check your connection and try again.",
        ),
      );
    } finally {
      clearTimeout(timer);
      if (request.current === controller) {
        request.current = null;
        setLoading(false);
      }
    }
  }

  return {
    country,
    size: countries[country],
    file,
    originalFile,
    savedCrop,
    preview,
    result,
    error,
    loading,
    selectFile,
    applyCrop,
    changeCountry,
    removePhoto,
    cancelProcessing,
    generate,
  };
}
