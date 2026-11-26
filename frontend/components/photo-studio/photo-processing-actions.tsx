"use client";

import { useEffect, useRef, type ComponentProps } from "react";
import { ArrowRight, ScanFace } from "lucide-react";

type ButtonProps = ComponentProps<"button">;

export function useProcessingActions(
  loading: boolean,
  onGenerate: () => Promise<void>,
  onCancel: () => void,
) {
  const primaryAction = useRef<HTMLButtonElement>(null);
  const mobileCancel = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);

  useEffect(() => {
    if (!restoreFocus.current) return;
    const action =
      loading &&
      mobileCancel.current &&
      window.matchMedia("(max-width: 600px)").matches
        ? mobileCancel.current
        : primaryAction.current;
    action?.focus({ preventScroll: true });
    restoreFocus.current = false;
  }, [loading]);

  return {
    primaryAction,
    mobileCancel,
    generate: () => {
      restoreFocus.current = true;
      void onGenerate();
    },
    cancel: () => {
      restoreFocus.current = true;
      onCancel();
    },
  };
}

export function GeneratePhotoButton({
  mobileLabel = false,
  ...props
}: ButtonProps & { mobileLabel?: boolean }) {
  return (
    <button type="button" className="primary generate" {...props}>
      <ScanFace size={20} aria-hidden="true" />
      {mobileLabel ? (
        <>
          <span className="desktop-generate-label">
            Generate passport photo
          </span>
          <span className="mobile-generate-label">Generate photo</span>
        </>
      ) : (
        "Generate passport photo"
      )}
      <ArrowRight size={18} aria-hidden="true" />
    </button>
  );
}

export function CancelPhotoButton({
  className = "secondary",
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={className}
      aria-label="Cancel generation"
      {...props}
    >
      Cancel
    </button>
  );
}
