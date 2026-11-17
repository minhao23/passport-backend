"use client";

import { useEffect, useRef } from "react";
import {
  ArrowRight,
  Download,
  ImagePlus,
  LoaderCircle,
  ScanFace,
} from "lucide-react";

type PhotoWorkspaceProps = {
  country: string;
  size: readonly [number, number];
  preview: string;
  result: string;
  loading: boolean;
  cancelled: boolean;
  onChoosePhoto: () => void;
  onCancel: () => void;
};

export default function PhotoWorkspace({
  country,
  size: [width, height],
  preview,
  result,
  loading,
  cancelled,
  onChoosePhoto,
  onCancel,
}: PhotoWorkspaceProps) {
  const outputHeading = useRef<HTMLHeadingElement>(null);
  const status = result
    ? "Ready to download"
    : loading
      ? "Processing your photo"
      : cancelled
        ? "Processing cancelled"
        : "Photo selected";
  const message = result
    ? "Download your photo, then check it against your issuing authority's rules."
    : loading
      ? "This may take a few minutes. You can cancel and keep your original photo."
      : cancelled
        ? "Your original photo is still here. Change it or generate again when you're ready."
        : "Select Generate passport photo above when you're ready.";

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
        {result && (
          <a
            href={result}
            download={`passport-${country.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.jpg`}
            className="primary download"
          >
            <Download size={18} /> Download JPEG
          </a>
        )}
      </div>
      <div className="workspace-body">
        <div className="photo-pair">
          <figure className="source-photo">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {preview && <img src={preview} alt="Your uploaded photo" />}
            <figcaption>Your original</figcaption>
            <button
              className="quiet-button preview-change"
              type="button"
              disabled={loading}
              onClick={onChoosePhoto}
            >
              <ImagePlus size={16} aria-hidden="true" /> Change photo
            </button>
          </figure>
          <ArrowRight
            className="photo-direction"
            size={24}
            aria-hidden="true"
          />
          <figure className="output-photo">
            <div
              className={`result-frame ${result ? "complete" : ""}`}
              style={{ aspectRatio: `${width}/${height}` }}
              aria-busy={loading}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {result ? (
                <img
                  src={result}
                  alt={`Generated passport photo for ${country}`}
                />
              ) : loading ? (
                <LoaderCircle size={36} className="spin" />
              ) : (
                <ScanFace size={46} strokeWidth={1} />
              )}
            </div>
            <figcaption>
              {result
                ? "Your passport photo"
                : loading
                  ? "Preparing your JPEG"
                  : "Your result goes here"}
            </figcaption>
          </figure>
        </div>
        <div className="output-details">
          <h3 className="preview-country">{country}</h3>
          <dl>
            <div>
              <dt>Photo size</dt>
              <dd>
                {width} × {height} mm
              </dd>
            </div>
            <div>
              <dt>Background</dt>
              <dd>White</dd>
            </div>
            <div>
              <dt>File format</dt>
              <dd>JPEG</dd>
            </div>
          </dl>
          <p className="result-message" role="status">
            {message}
          </p>
          {loading && (
            <button
              className="quiet-button workspace-cancel"
              type="button"
              onClick={onCancel}
            >
              Cancel processing
            </button>
          )}
          <p className="privacy-note">
            Your photo is sent to the processor only when you generate.
          </p>
        </div>
      </div>
    </section>
  );
}
