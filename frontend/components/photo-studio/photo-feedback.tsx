"use client";

import { useEffect, useRef } from "react";
import { ImagePlus, Info } from "lucide-react";
import type { PhotoError } from "@/lib/photo-errors";

type PhotoFeedbackProps = {
  error: PhotoError | null;
  loading: boolean;
  onChoosePhoto: () => void;
};

export default function PhotoFeedback({
  error,
  loading,
  onChoosePhoto,
}: PhotoFeedbackProps) {
  const feedback = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) feedback.current?.focus();
  }, [error]);

  if (!error) return null;

  return (
    <div className="feedback wrap">
      <div
        ref={feedback}
        className="error"
        role="alert"
        tabIndex={-1}
        data-error-code={error.code}
      >
        <Info size={20} aria-hidden="true" />
        <div>
          <strong>{error.title}</strong>
          <p>{error.detail}</p>
          {error.code === "PERSON_NOT_DETECTED" && (
            <button
              className="quiet-button"
              type="button"
              disabled={loading}
              onClick={onChoosePhoto}
            >
              <ImagePlus size={16} aria-hidden="true" /> Try another photo
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
