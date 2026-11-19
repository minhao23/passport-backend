"use client";

import { useRef, useState } from "react";
import BackgroundComparison from "@/components/background-comparison";
import { usePhotoStudio } from "@/hooks/use-photo-studio";
import PhotoCropModal from "./photo-crop-modal";
import PhotoFeedback from "./photo-feedback";
import PhotoUploadForm from "./photo-upload-form";
import PhotoWorkspace from "./photo-workspace";

export default function PhotoStudio() {
  const studio = usePhotoStudio();
  const input = useRef<HTMLInputElement>(null);
  const [editingPhoto, setEditingPhoto] = useState<File | null>(null);
  const choosePhoto = () => input.current?.click();

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
      <PhotoFeedback
        error={studio.error}
        loading={studio.loading}
        onChoosePhoto={choosePhoto}
      />
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
