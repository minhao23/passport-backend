"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  Download,
  ImagePlus,
  LoaderCircle,
  ScanFace,
} from "lucide-react";
import { passportPhotoFilename } from "@/lib/photo-download";
import PhotoFramingHelp from "./photo-framing-help";
import {
  CancelPhotoButton,
  GeneratePhotoButton,
  useProcessingActions,
} from "./photo-processing-actions";
import "./photo-workspace.css";

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
  const actions = useProcessingActions(loading, onGenerate, onCancel);
  const [viewedOriginal, setViewedOriginal] = useState("");
  const showingOriginal = !result || viewedOriginal === result;
  const status = result
    ? "Ready to download"
    : loading
      ? "Creating your photo"
      : "Photo selected";

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
              className="result-frame"
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
              <CancelPhotoButton
                ref={actions.primaryAction}
                className="secondary workspace-cancel"
                onClick={actions.cancel}
              />
            )}
          </figure>
        </div>
        <div className={`output-details${result ? " has-result" : ""}`}>
          <div className="output-summary">
            <h3>{country}</h3>
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
                <GeneratePhotoButton
                  ref={actions.primaryAction}
                  onClick={actions.generate}
                  mobileLabel
                />
              )
            )}
            {loading && (
              <div className="mobile-processing-action">
                <span role="status">
                  <LoaderCircle size={18} className="spin" aria-hidden="true" />
                  Creating your photo
                </span>
                <CancelPhotoButton
                  ref={actions.mobileCancel}
                  onClick={actions.cancel}
                />
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
          {!result && <PhotoPreparationTips country={country} />}
        </div>
      </div>
    </section>
  );
}

function PhotoPreparationTips({ country }: { country: string }) {
  const framingTip =
    country === "United Kingdom"
      ? "For UK online applications, use an uncropped original showing your head, shoulders and upper body."
      : "Crop just above the armpits. Keep your full head, shoulders and a little headroom.";
  const tips = (
    <ul>
      <li>{framingTip}</li>
      <li>
        Face forward at eye level, with eyes open and mouth closed. Avoid
        close-up selfies.
      </li>
      <li>
        Use even lighting and a sharp photo. Skip shadows and beauty filters.
      </li>
      <li>
        No headwear or sunglasses. Religious or medical coverings may be
        allowed; check your country&apos;s rules.
      </li>
    </ul>
  );

  return (
    <>
      <section
        className="workspace-tips"
        aria-labelledby="workspace-tips-title"
      >
        <h4 id="workspace-tips-title">Photo tips</h4>
        {tips}
      </section>
      <details className="mobile-photo-tips">
        <summary>
          Photo tips <ChevronDown size={16} aria-hidden="true" />
        </summary>
        {tips}
      </details>
    </>
  );
}
