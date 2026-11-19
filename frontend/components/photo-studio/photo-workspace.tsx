"use client";

import { useEffect, useRef } from "react";
import {
  ArrowRight,
  Download,
  ImagePlus,
  Info,
  LoaderCircle,
  ScanFace,
} from "lucide-react";
import { passportPhotoFilename } from "@/lib/photo-download";
import PhotoPreparationTips from "./photo-preparation-tips";

type PhotoWorkspaceProps = {
  country: string;
  size: readonly [number, number];
  preview: string;
  result: string;
  loading: boolean;
  cropped: boolean;
  onChoosePhoto: () => void;
  onGenerate: () => Promise<void>;
  onCancel: () => void;
  onCrop: () => void;
};

export default function PhotoWorkspace({
  country,
  size: [width, height],
  preview,
  result,
  loading,
  cropped,
  onChoosePhoto,
  onGenerate,
  onCancel,
  onCrop,
}: PhotoWorkspaceProps) {
  const outputHeading = useRef<HTMLHeadingElement>(null);
  const primaryAction = useRef<HTMLButtonElement>(null);
  const focusAction = useRef(false);
  const status = result
    ? "Ready to download"
    : loading
      ? "Creating your photo"
      : "Photo selected";

  useEffect(() => {
    // Follow the action swap only when it was initiated in this workspace.
    if (focusAction.current) {
      primaryAction.current?.focus({ preventScroll: true });
      focusAction.current = false;
    }
  }, [loading]);

  useEffect(() => {
    if (result) outputHeading.current?.focus();
  }, [result]);

  return (
    <section className="workspace wrap" aria-labelledby="workspace-title">
      <div className="workspace-heading">
        <div>
          <h2 ref={outputHeading} tabIndex={-1} id="workspace-title">
            {result ? "Your photo is ready." : "Your photo workspace"}
          </h2>
          <p className="workspace-status">{status}</p>
        </div>
      </div>
      <div className="workspace-body">
        <div className="photo-pair">
          <figure className="source-photo">
            {preview && (
              <button
                type="button"
                className="photo-crop-preview"
                disabled={loading}
                aria-label="Crop your uploaded photo"
                aria-describedby={loading ? undefined : "photo-crop-hint"}
                onDoubleClick={onCrop}
                onClick={(event) => {
                  // Keyboard and assistive clicks do not emit a double-click.
                  if (event.detail === 0) onCrop();
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="Your uploaded photo" />
              </button>
            )}
            <figcaption>{cropped ? "Your crop" : "Your original"}</figcaption>
            <div className="source-photo-actions" aria-hidden={loading}>
              <p id="photo-crop-hint" className="crop-hint">
                Double-click to crop
              </p>
              <button
                className="secondary preview-change"
                type="button"
                disabled={loading}
                onClick={onChoosePhoto}
              >
                <ImagePlus size={16} aria-hidden="true" />
                <span>Change photo</span>
              </button>
            </div>
          </figure>
          <ArrowRight
            className="photo-direction"
            size={24}
            aria-hidden="true"
          />
          <figure className="output-photo">
            <div
              className={`result-frame ${result ? "complete" : ""}`}
              style={{
                aspectRatio: `${width}/${height}`,
                maxWidth: `calc(var(--photo-preview-height) * ${width / height})`,
              }}
              aria-busy={loading}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {result ? (
                <img
                  src={result}
                  alt={`Generated passport photo for ${country}`}
                />
              ) : loading ? (
                <LoaderCircle size={36} className="spin" aria-hidden="true" />
              ) : (
                <ScanFace size={46} strokeWidth={1} />
              )}
            </div>
            <figcaption>
              {result
                ? "Your passport photo"
                : loading
                  ? "Creating your photo..."
                  : "Your result goes here"}
            </figcaption>
            {loading && (
              <button
                ref={primaryAction}
                className="secondary workspace-cancel"
                type="button"
                aria-label="Cancel generation"
                onClick={() => {
                  focusAction.current = true;
                  onCancel();
                }}
              >
                Cancel
              </button>
            )}
          </figure>
        </div>
        <div className={`output-details${result ? " has-result" : ""}`}>
          <div className="output-summary">
            <h3 className="preview-country">{country}</h3>
            <dl>
              <div>
                <dt className="sr-only">Photo size</dt>
                <dd>
                  {width} × {height} mm
                </dd>
              </div>
            </dl>
          </div>
          <div className="workspace-action">
            {result ? (
              <a
                href={result}
                download={passportPhotoFilename(country)}
                className="primary download"
              >
                <Download size={18} aria-hidden="true" /> Download JPEG
              </a>
            ) : (
              !loading && (
                <button
                  ref={primaryAction}
                  className="primary generate"
                  type="button"
                  onClick={() => {
                    focusAction.current = true;
                    void onGenerate();
                  }}
                >
                  <ScanFace size={20} aria-hidden="true" />
                  Generate passport photo
                  <ArrowRight size={18} aria-hidden="true" />
                </button>
              )
            )}
          </div>
          {result && (
            <>
              <p className="result-check">
                Check your photo against your issuing authority's rules.
              </p>
              <div className="result-tip">
                <Info size={14} aria-hidden="true" />
                <p>
                  Not happy with the framing? Re-crop your original photo and
                  generate again. Try a few crops to find the fit you prefer.
                </p>
              </div>
            </>
          )}
          {!result && <PhotoPreparationTips country={country} />}
        </div>
      </div>
    </section>
  );
}
