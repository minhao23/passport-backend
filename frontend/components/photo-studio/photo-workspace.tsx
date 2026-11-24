"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Download,
  ImagePlus,
  LoaderCircle,
  ScanFace,
} from "lucide-react";
import { passportPhotoFilename } from "@/lib/photo-download";
import PhotoFramingHelp from "./photo-framing-help";
import PhotoPreparationTips from "./photo-preparation-tips";

type PhotoWorkspaceProps = {
  country: string;
  size: readonly [number, number];
  preview: string;
  result: string;
  loading: boolean;
  cropped: boolean;
  onChoosePhoto: () => void;
  onRemovePhoto: () => void;
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
  onRemovePhoto,
  onGenerate,
  onCancel,
  onCrop,
}: PhotoWorkspaceProps) {
  const workspace = useRef<HTMLElement>(null);
  const outputHeading = useRef<HTMLHeadingElement>(null);
  const primaryAction = useRef<HTMLButtonElement>(null);
  const mobileCancel = useRef<HTMLButtonElement>(null);
  const focusAction = useRef(false);
  const [viewedOriginal, setViewedOriginal] = useState("");
  const showingOriginal = !result || viewedOriginal === result;
  const status = result
    ? "Ready to download"
    : loading
      ? "Creating your photo"
      : "Photo selected";

  useEffect(() => {
    // Follow the action swap only when it was initiated in this workspace.
    if (focusAction.current) {
      const action =
        loading && window.matchMedia("(max-width: 600px)").matches
          ? mobileCancel.current
          : primaryAction.current;
      action?.focus({ preventScroll: true });
      focusAction.current = false;
    }
  }, [loading]);

  useEffect(() => {
    if (result) outputHeading.current?.focus();
  }, [result]);

  useEffect(() => {
    if (preview && window.matchMedia("(max-width: 600px)").matches) {
      // Bring the phone workflow into view without moving the comparison.
      outputHeading.current?.focus({ preventScroll: true });
      workspace.current?.scrollIntoView({ block: "start" });
    }
  }, [preview]);

  return (
    <section
      ref={workspace}
      className="workspace wrap"
      data-state={result ? "complete" : loading ? "processing" : "selected"}
      aria-labelledby="workspace-title"
    >
      <div className="workspace-heading">
        <div>
          <h2 ref={outputHeading} tabIndex={-1} id="workspace-title">
            {result ? "Your photo is ready." : "Your photo workspace"}
          </h2>
          <p className="workspace-status">{status}</p>
        </div>
      </div>
      <div className="workspace-body">
        <div
          className="photo-pair"
          data-preview={showingOriginal ? "original" : "result"}
        >
          {result && (
            <div
              className="mobile-preview-switch"
              role="group"
              aria-label="Photo preview"
            >
              <button
                type="button"
                aria-pressed={showingOriginal}
                onClick={() => setViewedOriginal(result)}
              >
                Original
              </button>
              <button
                type="button"
                aria-pressed={!showingOriginal}
                onClick={() => setViewedOriginal("")}
              >
                Result
              </button>
            </div>
          )}
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
                  if (
                    event.detail === 0 ||
                    window.matchMedia("(max-width: 600px)").matches
                  )
                    onCrop();
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="Your uploaded photo" />
              </button>
            )}
            <figcaption>{cropped ? "Your crop" : "Your original"}</figcaption>
            <div className="source-photo-actions" aria-hidden={loading}>
              <p id="photo-crop-hint" className="crop-hint">
                <span className="desktop-crop-hint">Double-click to crop</span>
                <span className="mobile-crop-hint">Tap photo to crop</span>
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
              <button
                className="quiet-button mobile-remove"
                type="button"
                disabled={loading}
                onClick={onRemovePhoto}
              >
                Remove photo
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
                  <span className="desktop-generate-label">
                    Generate passport photo
                  </span>
                  <span className="mobile-generate-label">Generate photo</span>
                  <ArrowRight size={18} aria-hidden="true" />
                </button>
              )
            )}
            {loading && (
              <div className="mobile-processing-action">
                <span role="status">
                  <LoaderCircle size={18} className="spin" aria-hidden="true" />
                  Creating your photo
                </span>
                <button
                  ref={mobileCancel}
                  className="secondary"
                  type="button"
                  aria-label="Cancel generation"
                  onClick={() => {
                    focusAction.current = true;
                    onCancel();
                  }}
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
          {result && (
            <>
              <p className="result-check">
                Check your photo against your issuing authority's rules.
              </p>
              <PhotoFramingHelp key={result} />
            </>
          )}
          {!result && (
            <>
              <PhotoPreparationTips country={country} />
              <PhotoPreparationTips country={country} compact />
            </>
          )}
        </div>
      </div>
    </section>
  );
}
