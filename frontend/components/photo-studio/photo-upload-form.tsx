"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import {
  ArrowRight,
  ChevronDown,
  ImagePlus,
  LoaderCircle,
  ScanFace,
} from "lucide-react";
import { ACCEPTED_TYPES, countries } from "@/lib/countries";

type PhotoUploadFormProps = {
  country: string;
  size: readonly [number, number];
  file: File | null;
  loading: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onCountryChange: (country: string) => void;
  onFileSelect: (file?: File) => Promise<void>;
  onChoosePhoto: () => void;
  onRemovePhoto: () => void;
  onGenerate: () => Promise<void>;
  onCancel: () => void;
};

export default function PhotoUploadForm({
  country,
  size: [width, height],
  file,
  loading,
  inputRef,
  onCountryChange,
  onFileSelect,
  onChoosePhoto,
  onRemovePhoto,
  onGenerate,
  onCancel,
}: PhotoUploadFormProps) {
  const [dragging, setDragging] = useState(false);
  const primaryAction = useRef<HTMLButtonElement>(null);
  const focusAction = useRef(false);

  useEffect(() => {
    if (focusAction.current) {
      primaryAction.current?.focus({ preventScroll: true });
      focusAction.current = false;
    }
  }, [loading]);

  return (
    <div
      id="studio"
      className={`studio-form${file ? " has-photo" : ""}`}
      tabIndex={-1}
      aria-label="Create your passport photo"
    >
      <div className="field-title">
        <label htmlFor="country">Issuing country</label>
        <span className="size-spec" id="country-size">
          {width} × {height} mm
        </span>
      </div>
      <div className="country-row">
        <div className="select-wrap">
          <select
            id="country"
            value={country}
            onChange={(event) => onCountryChange(event.target.value)}
            disabled={loading}
            aria-describedby="country-help country-size"
          >
            {Object.keys(countries).map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <ChevronDown
            className="select-chevron"
            size={16}
            aria-hidden="true"
          />
        </div>
      </div>
      <p id="country-help" className="sr-only">
        Choose the country issuing your passport, not your destination.
      </p>
      <p id="photo-help" className="sr-only">
        Choose a JPG, PNG, or WebP up to 10 MB.
      </p>
      <input
        ref={inputRef}
        id="photo"
        aria-label="Add your photo"
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        disabled={loading}
        className="sr-only"
        tabIndex={-1}
        aria-describedby="photo-help"
        onChange={(event) => {
          void onFileSelect(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <div
        className={`upload-area ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!loading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void onFileSelect(event.dataTransfer.files[0]);
        }}
      >
        {file && (
          <a className="primary mobile-review" href="#workspace-title">
            Review your photo <ArrowRight size={18} aria-hidden="true" />
          </a>
        )}
        {loading ? (
          <div className="processing-state">
            <div className="processing-status" role="status">
              <LoaderCircle className="spin" size={20} aria-hidden="true" />
              <div className="processing-copy">
                <strong>Creating your photo</strong>
                <p className="file-note" title={file?.name}>
                  {file?.name}
                </p>
              </div>
            </div>
            <button
              ref={primaryAction}
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
        ) : file ? (
          <button
            ref={primaryAction}
            className="primary generate"
            type="button"
            onClick={() => {
              focusAction.current = true;
              void onGenerate();
            }}
          >
            <ScanFace size={20} /> Generate passport photo{" "}
            <ArrowRight size={18} />
          </button>
        ) : (
          <button
            ref={primaryAction}
            type="button"
            className="primary upload-button"
            onClick={onChoosePhoto}
          >
            {dragging ? "Drop your photo here" : "Upload your photo"}
          </button>
        )}
        {!loading &&
          (file ? (
            <>
              <p className="file-note" title={file.name}>
                {file.name}
              </p>
              <div className="photo-actions">
                <button
                  className="secondary"
                  type="button"
                  onClick={onChoosePhoto}
                >
                  <ImagePlus size={18} aria-hidden="true" /> Change photo
                </button>
                <button
                  className="quiet-button"
                  type="button"
                  onClick={onRemovePhoto}
                >
                  Remove photo
                </button>
              </div>
            </>
          ) : (
            <p className="upload-help">
              JPG, PNG, WebP up to 10 MB. <span>Or drop it here.</span>
            </p>
          ))}
      </div>
    </div>
  );
}
