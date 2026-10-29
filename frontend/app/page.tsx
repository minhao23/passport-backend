"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { ArrowDown, ArrowRight, Camera, Check, CheckCheck, Download, Globe2, ImagePlus, LoaderCircle, LockKeyhole, ScanFace, Sparkles, Upload, X } from "lucide-react";
import { ACCEPTED_TYPES, countries, MAX_FILE_SIZE } from "@/lib/countries";
import { normalizePhotoError, photoError, type PhotoError } from "@/lib/photo-errors";

const portrait = "https://copilot-sg-og.byteintl.net/api/ide/v1/text_to_image?prompt=Professional%20passport%20portrait%20photograph%20of%20a%20young%20adult%20woman%20with%20short%20dark%20brown%20hair%20wearing%20a%20simple%20dark%20olive%20crewneck%20shirt%2C%20looking%20straight%20at%20camera%2C%20neutral%20expression%2C%20head%20and%20shoulders%2C%20symmetrical%20frontal%20composition%2C%20soft%20even%20studio%20lighting%2C%20pure%20white%20background%2C%20realistic%20photography%2C%20no%20text&image_size=portrait_4_3";

export default function Home() {
  const [country, setCountry] = useState("United States");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState<PhotoError | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
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
  useEffect(() => () => { request.current?.abort(); }, []);

  async function selectFile(next?: File) {
    if (!next || loading) return;
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
    } catch {
      if (version === selection.current) setError(photoError("PHOTO_ISSUE", "This image couldn't be opened. Please choose another photo."));
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false);
    void selectFile(event.dataTransfer.files[0]);
  }
  function changeCountry(event: ChangeEvent<HTMLSelectElement>) {
    setCountry(event.target.value); setResult(""); setError(null);
  }
  async function generate() {
    if (!file || loading) return;
    setLoading(true); setError(null); setResult("");
    const controller = new AbortController();
    request.current = controller;
    const timer = setTimeout(() => controller.abort(), 190_000);
    try {
      const form = new FormData();
      form.set("country", country); form.set("file", file);
      const response = await fetch("/api/process", { method: "POST", body: form, signal: controller.signal });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setError(normalizePhotoError(data, response.status));
        return;
      }
      const blob = await response.blob();
      if (!blob.size || !blob.type.startsWith("image/jpeg")) {
        setError(photoError("INTERNAL_SERVER_ERROR")); return;
      }
      setResult(URL.createObjectURL(blob));
    } catch (err) {
      setError(photoError("INTERNAL_SERVER_ERROR", err instanceof Error && err.name === "AbortError"
        ? "Processing is taking longer than expected. Please try again in a moment."
        : "We couldn't connect to the photo service. Check your connection and try again."));
    } finally {
      clearTimeout(timer); request.current = null; setLoading(false);
    }
  }

  return (
    <main>
      <header className="nav wrap">
        <a className="brand" href="#" aria-label="Passport Studio home"><span className="brand-mark"><ScanFace size={22} /></span>passport<span className="brand-light">studio</span><span className="brand-dot">.</span></a>
        <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#photo-tips">Photo tips</a><a className="nav-cta" href="#studio">Create my photo <ArrowRight size={15} /></a></nav>
      </header>

      <section className="hero wrap">
        <div className="hero-copy">
          <div className="eyebrow"><span className="live-dot" /> A LITTLE PHOTO. A WORLD OF POSSIBILITIES.</div>
          <h1>Your next adventure<br />starts with a<br /><span>better photo.</span><svg viewBox="0 0 360 18" aria-hidden="true"><path d="M4 12 Q170 -2 354 9" /></svg></h1>
          <p className="hero-description">Skip the photo booth. Turn a photo you already have into a passport-sized photo, right from home.</p>
          <a href="#studio" className="primary hero-button">Let&apos;s make your photo <ArrowRight size={18} /></a>
          <div className="hero-perks"><span><Check size={15} /> No sign-up</span><span><Check size={15} /> Free to download</span><span><Check size={15} /> Made for your country</span></div>
        </div>
        <div className="hero-art" aria-label="Illustrative passport photo preview">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <span className="art-spark spark-one">✦</span><span className="art-spark spark-two">✧</span>
          <div className="passport-book"><Globe2 size={46} strokeWidth={1} /><span>PASSPORT</span><div className="book-lines" /><span className="book-label">THE WORLD IS WAITING</span></div>
          <div className="example-photo">
            {/* Generated illustration, not an actual processed result. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={portrait} alt="Illustrative front-facing passport portrait on white" />
            <div className="photo-corner top-left" /><div className="photo-corner bottom-right" />
            <div className="photo-caption"><span><span className="live-dot" /> A fresh start</span><ScanFace size={18} /></div>
          </div>
          <div className="floating-note"><span className="note-icon"><CheckCheck size={21} /></span><div>One photo. Ready to go.<small>White background. Your dimensions.</small></div></div>
          <span className="art-footnote">A little less admin. A little more adventure.</span>
        </div>
      </section>

      <div className="benefit-strip"><div className="wrap"><span><ScanFace /> AI-powered background removal</span><span><Globe2 /> {Object.keys(countries).length} country sizes</span><span><Download /> High-quality JPEG</span><span><LockKeyhole /> No account needed</span></div></div>

      <section id="studio" className="studio-section wrap">
        <div className="section-heading"><div><span className="eyebrow muted">YOUR AT-HOME PHOTO STUDIO</span><h2>A few clicks. A fresh photo.</h2></div><p>You bring the photo.<br />We&apos;ll take care of the background and size.</p></div>
        <div className="studio-grid">
          <div className="studio-form">
            <div className="field-title"><span className="step-number">1</span><label htmlFor="country">Where are you headed?</label></div>
            <p className="field-help">Choose the country your passport photo is for.</p>
            <div className="select-wrap"><Globe2 size={19} /><select id="country" value={country} onChange={changeCountry} disabled={loading}>{Object.keys(countries).map(name => <option key={name}>{name}</option>)}</select></div>
            <div className="size-hint"><Check size={13} /> Photo dimensions: {width} × {height} mm</div>
            <div className="field-title upload-title"><span className="step-number">2</span><label htmlFor="photo">Add your photo</label></div>
            <input ref={input} id="photo" type="file" accept={ACCEPTED_TYPES.join(",")} disabled={loading} className="sr-only" onChange={event => { void selectFile(event.target.files?.[0]); event.target.value = ""; }} />
            <div className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-photo" : ""}`} onDragOver={event => { event.preventDefault(); if (!loading) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              {preview ? <div className="uploaded">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="Your uploaded photo" />
                <div><strong>{file?.name}</strong><small>{((file?.size || 0) / 1024 / 1024).toFixed(1)} MB · Ready to process</small><button type="button" disabled={loading} onClick={() => input.current?.click()}>Choose a different photo</button></div>
                <button className="remove-photo" type="button" aria-label="Remove photo" disabled={loading} onClick={() => { ++selection.current; setFile(null); setResult(""); setError(null); }}><X size={17} /></button>
              </div> : <button type="button" className="upload-button" onClick={() => input.current?.click()} disabled={loading}><span className="upload-icon"><Upload size={24} /></span><strong>Drop your photo here</strong><span>or <u>browse files</u></span><small>JPG, PNG or WebP · Up to 10 MB</small></button>}
            </div>
            <p className="upload-tip"><Camera size={14} /> A clear, front-facing photo works best.</p>
            {error && <div className="error" role="alert" data-error-code={error.code}><strong>{error.title}</strong><p>{error.detail}</p></div>}
            <button className="primary generate" type="button" onClick={() => void generate()} disabled={!file || loading}>{loading ? <><LoaderCircle className="spin" size={18} /> Creating your photo...</> : <><Sparkles size={18} /> Generate passport photo <ArrowRight size={17} /></>}</button>
            <p className="form-footnote"><LockKeyhole size={12} /> Your photo is sent to the processor only when you generate.</p>
          </div>
          <div className={`result-panel ${result ? "complete" : ""}`} aria-busy={loading}>
            <div className="preview-header"><span><span className={`live-dot ${result ? "" : "gray"}`} /> {result ? "YOUR PHOTO IS READY" : "YOUR PHOTO PREVIEW"}</span><span>JPEG</span></div>
            <div className="preview-stage">
              {result ? <div className="result-frame" style={{ aspectRatio: `${width}/${height}` }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={result} alt={`Generated passport photo for ${country}`} />
              </div> : <div className="empty-photo" style={{ aspectRatio: `${width}/${height}` }}><div className="frame-corner tl" /><div className="frame-corner tr" /><div className="frame-corner bl" /><div className="frame-corner br" />{loading ? <LoaderCircle size={42} className="spin" strokeWidth={1.2} /> : <ScanFace size={55} strokeWidth={1} />}<span>{loading ? "A little photo magic..." : "Your next chapter"}</span><small>{loading ? "Removing the background and sizing your photo." : "starts here."}</small></div>}
            </div>
            <div className="preview-info"><span>{width} × {height} mm</span><span>White background</span></div>
            <div aria-live="polite" className="result-message">{result ? "Looking good. Your JPEG is ready to download." : loading ? "This may take a few minutes. Keep this page open." : "Upload a photo to bring your preview to life."}</div>
            {result && <a href={result} download={`passport-${country.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.jpg`} className="primary download"><Download size={17} /> Download JPEG</a>}
          </div>
        </div>
        <p className="compliance-note">Made to the listed photo dimensions. Please check your issuing authority&apos;s current rules for head size, expression, and photo editing before submitting.</p>
      </section>

      <section id="how-it-works" className="how-section wrap">
        <span className="eyebrow muted">LESS ERRANDS. MORE EXPLORING.</span><h2>From your camera to your carry-on.</h2>
        <div className="steps"><article><span className="feature-icon"><Globe2 /></span><span className="step-label">01 / CHOOSE</span><h3>Pick your country</h3><p>We&apos;ll use the photo dimensions listed for your destination.</p></article><article><span className="feature-icon"><ImagePlus /></span><span className="step-label">02 / UPLOAD</span><h3>Bring your best shot</h3><p>A simple photo, good lighting, and you looking straight ahead.</p></article><article><span className="feature-icon"><ArrowDown /></span><span className="step-label">03 / DOWNLOAD</span><h3>Meet your new photo</h3><p>Get a clean white background and a JPEG you can download.</p></article></div>
      </section>
      <section id="photo-tips" className="tips wrap"><div className="tips-title"><span className="feature-icon"><Camera /></span><div><span className="eyebrow muted">A BETTER STARTING POINT</span><h3>A good photo makes all the difference.</h3></div></div><div className="tips-list"><span><Check /> Face the camera directly</span><span><Check /> Use soft, even lighting</span><span><Check /> Keep your whole head in frame</span><span><Check /> Take off hats and sunglasses</span></div></section>
      <footer className="wrap"><a href="#" className="brand"><span className="brand-mark"><ScanFace size={18} /></span>passport<span className="brand-light">studio</span>.</a><span>Small photo. Big plans.</span><a href="#studio">Start your photo <ArrowRight size={14} /></a></footer>
    </main>
  );
}
