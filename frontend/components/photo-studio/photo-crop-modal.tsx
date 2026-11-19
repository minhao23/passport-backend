"use client";

import { useEffect, useRef, useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import ReactCrop, { type PercentCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import { MAX_FILE_SIZE } from "@/lib/countries";
import {
  createCroppedFile,
  cropPixels,
  FULL_PHOTO_CROP,
} from "@/lib/photo-crop";
import styles from "./photo-crop-modal.module.css";

type PhotoCropModalProps = {
  original: File;
  savedCrop: PercentCrop | null;
  onSave: (file: File, crop: PercentCrop) => boolean;
  onClose: () => void;
};

export default function PhotoCropModal({
  original,
  savedCrop,
  onSave,
  onClose,
}: PhotoCropModalProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const image = useRef<HTMLImageElement>(null);
  const active = useRef(false);
  const exporting = useRef(false);
  const [source, setSource] = useState("");
  const [crop, setCrop] = useState<PercentCrop>(savedCrop ?? FULL_PHOTO_CROP);
  const [size, setSize] = useState<{ width: number; height: number } | null>(
    null,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    active.current = true;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const url = URL.createObjectURL(original);
    setSource(url);
    element.showModal();
    // Announce the editor without making Close look selected on arrival.
    title.current?.focus({ preventScroll: true });
    document.body.style.overflow = "hidden";
    return () => {
      active.current = false;
      element.close();
      URL.revokeObjectURL(url);
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
        previousFocus.focus({ preventScroll: true });
      }
    };
  }, [original]);

  function close() {
    active.current = false;
    onClose();
  }

  async function save() {
    if (!image.current || !size || exporting.current) return;
    exporting.current = true;
    setSaving(true);
    setError("");
    try {
      const file = await createCroppedFile(
        original,
        image.current,
        crop,
        MAX_FILE_SIZE,
      );
      if (!active.current) return;
      if (onSave(file, crop)) close();
      else
        setError(
          "Your photo changed. Close the editor and open your latest photo.",
        );
    } catch (failure) {
      if (active.current) {
        setError(
          failure instanceof Error
            ? failure.message
            : "The crop couldn't be saved. Please try again.",
        );
      }
    } finally {
      exporting.current = false;
      if (active.current) setSaving(false);
    }
  }

  let dimensions = "";
  if (size) {
    try {
      const pixels = cropPixels(crop, size.width, size.height);
      dimensions = `${pixels.width} × ${pixels.height} px`;
    } catch {
      // An in-progress drag can briefly have an empty selection.
    }
  }

  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby="crop-title"
      aria-describedby="crop-instructions"
      aria-busy={saving}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled), [tabindex="0"]',
          ),
        ).filter((control) => control.getClientRects().length);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === title.current)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <header className={styles.header}>
        <h2 id="crop-title" ref={title} tabIndex={-1}>
          Crop your photo
        </h2>
        <button
          type="button"
          className={styles.close}
          onClick={close}
          aria-label="Close crop editor"
        >
          <X size={20} aria-hidden="true" />
        </button>
      </header>
      <div className={styles.body}>
        <p id="crop-instructions" className="sr-only">
          Drag the corners to resize, or drag inside to move. Keep your whole
          head and shoulders. Tab to a crop handle, then use the arrow keys to
          adjust.
        </p>
        <div className={styles.stage} aria-busy={!size && !error}>
          {!size && !error && <p role="status">Opening your photo...</p>}
          {source && (
            <ReactCrop
              className={`ReactCrop--no-animate ${styles.cropper}`}
              crop={crop}
              onChange={(_, percent) => {
                setCrop(percent);
                setError("");
              }}
              ariaLabels={{
                cropArea: "Move crop selection with arrow keys",
                nwDragHandle: "Resize crop from top left",
                nDragHandle: "Resize crop from top",
                neDragHandle: "Resize crop from top right",
                eDragHandle: "Resize crop from right",
                seDragHandle: "Resize crop from bottom right",
                sDragHandle: "Resize crop from bottom",
                swDragHandle: "Resize crop from bottom left",
                wDragHandle: "Resize crop from left",
              }}
              disabled={saving || !size}
              keepSelection
              ruleOfThirds
              minWidth={24}
              minHeight={24}
            >
              {/* A local object URL must stay unoptimized for canvas cropping. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                ref={image}
                src={source}
                alt="Your original photo to crop"
                draggable={false}
                onLoad={(event) => {
                  setSize({
                    width: event.currentTarget.naturalWidth,
                    height: event.currentTarget.naturalHeight,
                  });
                }}
                onError={() =>
                  setError(
                    "This photo couldn't be opened. Close the editor and choose another photo.",
                  )
                }
              />
            </ReactCrop>
          )}
        </div>
        <div className={styles.details}>
          <output aria-label="Crop dimensions" aria-live="off">
            {dimensions}
          </output>
        </div>
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className="quiet-button"
          disabled={!size || saving}
          onClick={() => {
            setCrop(FULL_PHOTO_CROP);
            setError("");
          }}
        >
          <RotateCcw size={16} aria-hidden="true" /> Reset
        </button>
        <button type="button" className="secondary" onClick={close}>
          Cancel
        </button>
        <button
          type="button"
          className={`primary ${styles.save}`}
          disabled={!size || !dimensions || saving}
          onClick={() => void save()}
        >
          <Check size={20} aria-hidden="true" />
          {saving ? "Saving..." : "Save crop"}
        </button>
      </div>
    </dialog>
  );
}
