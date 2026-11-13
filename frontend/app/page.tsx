"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { ArrowRight, Check, ChevronDown, Download, ImagePlus, Info, LoaderCircle, ScanFace, Sun, UserRound } from "lucide-react";
import { ACCEPTED_TYPES, countries, MAX_FILE_SIZE } from "@/lib/countries";
import { normalizePhotoError, photoError, type PhotoError } from "@/lib/photo-errors";
import BackgroundComparison from "@/components/background-comparison";

export default function Home() {
  const [country, setCountry] = useState("United States");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState<PhotoError | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const primaryAction = useRef<HTMLButtonElement>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const outputHeading = useRef<HTMLHeadingElement>(null);
  const request = useRef<AbortController | null>(null);
  const selection = useRef(0);
  const [width, height] = countries[country];

  useEffect(() => {
    if (!file) { setPreview(""); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => () => { if (result) URL.revokeObjectURL(result); }, [result]);
  useEffect(() => () => {
    const controller = request.current;
    request.current = null;
    controller?.abort();
  }, []);
  useEffect(() => { if (error) feedback.current?.focus(); }, [error]);
  useEffect(() => { if (result) outputHeading.current?.focus(); }, [result]);
  useEffect(() => { if (cancelled) primaryAction.current?.focus(); }, [cancelled]);

  async function selectFile(next?: File) {
    if (!next || request.current) return;
    const version = ++selection.current;
    setError(null);
    if (!ACCEPTED_TYPES.includes(next.type)) {
      setError(photoError("PHOTO_ISSUE", "Please choose a JPG, PNG, or WebP photo.")); return;
    }
    if (!next.size || next.size > MAX_FILE_SIZE) {
      setError(photoError("PHOTO_ISSUE", "Please choose a non-empty photo that is 10 MB or smaller.")); return;
    }
    try {
      const bitmap = await createImageBitmap(next);
      bitmap.close();
      if (version !== selection.current) return;
      setFile(next);
      setResult("");
      setCancelled(false);
    } catch {
      if (version === selection.current) setError(photoError("PHOTO_ISSUE", "This image couldn't be opened. Please choose another photo."));
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false);
    void selectFile(event.dataTransfer.files[0]);
  }
  function changeCountry(event: ChangeEvent<HTMLSelectElement>) {
    setCountry(event.target.value); setResult(""); setError(null); setCancelled(false);
  }
  function removePhoto() {
    if (request.current) return;
    ++selection.current;
    setFile(null); setResult(""); setError(null); setCancelled(false);
  }
  function cancelProcessing() {
    const controller = request.current;
    if (!controller) return;
    // Invalidate first so late responses cannot overwrite a replacement or retry.
    request.current = null;
    controller.abort();
    setLoading(false); setError(null); setCancelled(true);
  }
  async function generate() {
    if (!file || request.current) return;
    ++selection.current;
    setLoading(true); setError(null); setResult(""); setCancelled(false);
    const controller = new AbortController();
    request.current = controller;
    const timer = setTimeout(() => controller.abort(), 190_000);
    try {
      const form = new FormData();
      form.set("country", country); form.set("file", file);
      const response = await fetch("/api/process", { method: "POST", body: form, signal: controller.signal });
      if (request.current !== controller) return;
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        if (request.current !== controller) return;
        setError(normalizePhotoError(data, response.status));
        return;
      }
      const blob = await response.blob();
      if (request.current !== controller) return;
      if (!blob.size || !blob.type.startsWith("image/jpeg")) {
        setError(photoError("INTERNAL_SERVER_ERROR")); return;
      }
      setResult(URL.createObjectURL(blob));
    } catch (err) {
      if (request.current !== controller) return;
      setError(photoError("INTERNAL_SERVER_ERROR", err instanceof Error && err.name === "AbortError"
        ? "Processing is taking longer than expected. Please try again in a moment."
        : "We couldn't connect to the photo service. Check your connection and try again."));
    } finally {
      clearTimeout(timer);
      if (request.current === controller) {
        request.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <main>
      <a className="skip-link" href="#studio">Skip to photo studio</a>
      <header className="nav wrap">
        <a className="brand" href="#" aria-label="Passport Studio home">Passport Studio</a>
        <nav aria-label="Main navigation"><a href="#photo-tips">Photo guide</a><span className="free-note">Free. No account needed.</span></nav>
      </header>

      <section className="hero wrap">
        <div className="hero-copy">
          <h1>Your passport photo<br />starts here.</h1>
          <div id="studio" className="studio-form" tabIndex={-1} aria-label="Create your passport photo">
            <div className="field-title"><label htmlFor="country">Issuing country</label><span className="size-spec" id="country-size">{width} × {height} mm</span></div>
            <div className="country-row">
              <div className="select-wrap"><select id="country" value={country} onChange={changeCountry} disabled={loading} aria-describedby="country-help country-size">{Object.keys(countries).map(name => <option key={name}>{name}</option>)}</select><ChevronDown className="select-chevron" size={16} aria-hidden="true" /></div>
            </div>
            <p id="country-help" className="sr-only">Choose the country issuing your passport, not your destination.</p>
            <p id="photo-help" className="sr-only">Choose a JPG, PNG, or WebP up to 10 MB. Your photo is sent to the processor only when you generate.</p>
            <input ref={input} id="photo" aria-label="Add your photo" type="file" accept={ACCEPTED_TYPES.join(",")} disabled={loading} className="sr-only" tabIndex={-1} aria-describedby="photo-help" onChange={event => { void selectFile(event.target.files?.[0]); event.target.value = ""; }} />
            <div className={`upload-area ${dragging ? "dragging" : ""}`} onDragOver={event => { event.preventDefault(); if (!loading) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              {loading
                ? <div className="processing-state">
                  <div className="processing-status" role="status">
                    <LoaderCircle className="spin" size={20} aria-hidden="true" />
                    <div className="processing-copy">
                      <strong>Creating your photo</strong>
                      <p className="file-note" title={file?.name}>{file?.name}</p>
                    </div>
                  </div>
                  <button className="quiet-button" type="button" aria-label="Cancel processing" onClick={cancelProcessing}>Cancel</button>
                </div>
                : file
                  ? <button ref={primaryAction} className="primary generate" type="button" onClick={() => void generate()}><ScanFace size={20} /> Generate passport photo <ArrowRight size={18} /></button>
                  : <button ref={primaryAction} type="button" className="primary upload-button" onClick={() => input.current?.click()}>{dragging ? "Drop your photo here" : "Upload your photo"}</button>}
              {!loading && (file
                ? <>
                  <p className="file-note" title={file.name}>{file.name}</p>
                  <div className="photo-actions">
                    <button className="secondary" type="button" onClick={() => input.current?.click()}><ImagePlus size={18} aria-hidden="true" /> Change photo</button>
                    <button className="quiet-button" type="button" onClick={removePhoto}>Remove photo</button>
                  </div>
                </>
                : <p className="upload-help">JPG, PNG, WebP up to 10 MB. <span>Or drop it here.</span></p>)}
              <p className="process-note" role="status">{cancelled ? "Cancelled. Change your photo or generate again." : ""}</p>
            </div>
            <p className="mobile-free-note">Free. No account needed.</p>
          </div>
        </div>
        <BackgroundComparison />
      </section>

      {error && <div className="feedback wrap"><div ref={feedback} className="error" role="alert" tabIndex={-1} data-error-code={error.code}><Info size={20} /><div><strong>{error.title}</strong><p>{error.detail}</p></div></div></div>}

      {file && <section className="workspace wrap" aria-labelledby="workspace-title">
        <div className="workspace-heading"><div><h2 ref={outputHeading} tabIndex={-1} id="workspace-title">{result ? "Your photo is ready." : "Your photo workspace"}</h2><p className="workspace-status">{result ? "Ready to download" : loading ? "Processing your photo" : cancelled ? "Processing cancelled" : "Photo selected"}</p></div>{result && <a href={result} download={`passport-${country.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.jpg`} className="primary download"><Download size={18} /> Download JPEG</a>}</div>
        <div className="workspace-body">
          <div className="photo-pair">
            <figure className="source-photo">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {preview && <img src={preview} alt="Your uploaded photo" />}
              <figcaption>Your original</figcaption>
              <button className="quiet-button preview-change" type="button" disabled={loading} onClick={() => input.current?.click()}><ImagePlus size={16} aria-hidden="true" /> Change photo</button>
            </figure>
            <ArrowRight className="photo-direction" size={24} aria-hidden="true" />
            <figure className="output-photo">
              <div className={`result-frame ${result ? "complete" : ""}`} style={{ aspectRatio: `${width}/${height}` }} aria-busy={loading}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {result ? <img src={result} alt={`Generated passport photo for ${country}`} /> : loading ? <LoaderCircle size={36} className="spin" /> : <ScanFace size={46} strokeWidth={1} />}
              </div>
              <figcaption>{result ? "Your passport photo" : loading ? "Preparing your JPEG" : "Your result goes here"}</figcaption>
            </figure>
          </div>
          <div className="output-details"><h3 className="preview-country">{country}</h3><dl><div><dt>Photo size</dt><dd>{width} × {height} mm</dd></div><div><dt>Background</dt><dd>White</dd></div><div><dt>File format</dt><dd>JPEG</dd></div></dl><p className="result-message" role="status">{result ? "Download your photo, then check it against your issuing authority's rules." : loading ? "This may take a few minutes. You can cancel and keep your original photo." : cancelled ? "Your original photo is still here. Change it or generate again when you're ready." : "Select Generate passport photo above when you're ready."}</p>{loading && <button className="quiet-button workspace-cancel" type="button" onClick={cancelProcessing}>Cancel processing</button>}<p className="privacy-note">Your photo is sent to the processor only when you generate.</p></div>
        </div>
      </section>}

      <section id="photo-tips" className="guide wrap" aria-labelledby="guide-title">
        <div className="guide-panel">
          <div className="guide-intro"><h2 id="guide-title">A little prep.<br />A better shot.</h2><p>No special setup. Just you,<br />your camera, and a window.</p><a className="text-link" href="#studio">I have a photo <ArrowRight size={17} /></a></div>
          <div className="framing-guide" role="img" aria-label="Framing guide: face the camera with your whole head and shoulders visible and space above your head.">
            <span className="framing-label">Leave a little headroom</span>
            <div className="framing-window"><i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" /><div className="headroom-line" /><UserRound className="framing-person" strokeWidth={.8} /><div className="eye-line" /><span className="eye-label">Eyes level</span></div>
            <span className="framing-caption"><Check size={14} /> Head &amp; shoulders in frame</span>
          </div>
          <div className="guide-notes">
            <article><Sun size={21} /><div><h3>Find the light.</h3><p>Face a window. Skip harsh shadows and camera filters.</p></div></article>
            <article><ScanFace size={21} /><div><h3>Keep it natural.</h3><p>Head straight, eyes open, neutral expression. No sunglasses.</p></div></article>
            <article><UserRound size={21} /><div><h3>Give yourself room.</h3><p>Include your whole head and shoulders. We&apos;ll handle the background.</p></div></article>
          </div>
        </div>
        <div className="submission-note"><Info size={17} /><p><strong>Before you submit.</strong> We resize and remove the background, but acceptance isn&apos;t guaranteed. Check your issuing authority&apos;s current rules on head size, expression, head coverings, and photo editing.</p></div>
      </section>
      <footer className="wrap">
        <a href="#" className="brand" aria-label="Passport Studio home">Passport Studio</a>
        <a className="footer-credit" href="https://minhao.vercel.app" target="_blank" rel="noopener noreferrer">
          Contact me<span className="sr-only"> (opens in a new tab)</span>
        </a>
        <a href="#studio">Back to your photo <ArrowRight size={15} /></a>
      </footer>
    </main>
  );
}
