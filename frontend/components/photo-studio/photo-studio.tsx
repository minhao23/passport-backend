"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { ImagePlus, Info } from "lucide-react";
import BackgroundComparison from "@/components/background-comparison";
import PhotoUploadForm from "./photo-upload-form";
import PhotoWorkspace from "./photo-workspace";
import { usePhotoStudio } from "./use-photo-studio";

const PhotoCropModal = dynamic(() => import("./photo-crop-modal"), {
  ssr: false,
});

export default function PhotoStudio() {
  const studio = usePhotoStudio();
  const input = useRef<HTMLInputElement>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const [editingPhoto, setEditingPhoto] = useState<File | null>(null);
  const choosePhoto = () => input.current?.click();

  useEffect(() => {
    if (studio.error) feedback.current?.focus();
  }, [studio.error]);

  return (
    <>
      <section className="hero wrap">
        <div className="hero-copy">
          <h1>
            Your passport photo
            <br />
            starts here.
          </h1>
          <PhotoUploadForm
            country={studio.country}
            size={studio.size}
            file={studio.file}
            loading={studio.loading}
            inputRef={input}
            onCountryChange={studio.changeCountry}
            onFileSelect={studio.selectFile}
            onChoosePhoto={choosePhoto}
            onRemovePhoto={studio.removePhoto}
            onGenerate={studio.generate}
            onCancel={studio.cancelProcessing}
          />
        </div>
        <BackgroundComparison />
      </section>
      {studio.error && (
        <div className="feedback wrap">
          <div
            ref={feedback}
            className="error"
            role="alert"
            tabIndex={-1}
            data-error-code={studio.error.code}
          >
            <Info size={20} aria-hidden="true" />
            <div>
              <strong>{studio.error.title}</strong>
              <p>{studio.error.detail}</p>
              {studio.error.code === "PERSON_NOT_DETECTED" && (
                <button
                  className="quiet-button"
                  type="button"
                  disabled={studio.loading}
                  onClick={choosePhoto}
                >
                  <ImagePlus size={16} aria-hidden="true" /> Try another photo
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      {studio.file && (
        <PhotoWorkspace
          country={studio.country}
          size={studio.size}
          preview={studio.preview}
          result={studio.result}
          loading={studio.loading}
          cropped={studio.savedCrop !== null}
          onChoosePhoto={choosePhoto}
          onRemovePhoto={studio.removePhoto}
          onGenerate={studio.generate}
          onCancel={studio.cancelProcessing}
          onCrop={() => setEditingPhoto(studio.originalFile)}
        />
      )}
      {editingPhoto &&
        editingPhoto === studio.originalFile &&
        !studio.loading && (
          <PhotoCropModal
            original={editingPhoto}
            savedCrop={studio.savedCrop}
            onSave={(file, crop) => studio.applyCrop(editingPhoto, file, crop)}
            onClose={() => setEditingPhoto(null)}
          />
        )}
    </>
  );
}
