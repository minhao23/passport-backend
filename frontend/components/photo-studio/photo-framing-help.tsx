"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, Info, UserRound } from "lucide-react";
import styles from "./photo-framing-help.module.css";

export default function PhotoFramingHelp() {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  const guideRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const guide = guideRef.current;
    if (
      !open ||
      !guide ||
      typeof IntersectionObserver === "undefined" ||
      typeof guide.getAnimations !== "function"
    ) {
      return;
    }

    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    const updatePlayback = () => {
      const playing = visible && !document.hidden && !preference.matches;
      for (const animation of guide.getAnimations({ subtree: true })) {
        if (playing) animation.play();
        else animation.pause();
      }
    };

    guide.dataset.motionEnabled = "true";
    updatePlayback();
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        updatePlayback();
      },
      { threshold: 0.5 },
    );
    observer.observe(guide);
    document.addEventListener("visibilitychange", updatePlayback);
    preference.addEventListener("change", updatePlayback);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", updatePlayback);
      preference.removeEventListener("change", updatePlayback);
    };
  }, [open]);

  return (
    <div className={styles.help}>
      <section
        id={contentId}
        className={styles.content}
        aria-label="Framing tips"
        hidden={!open}
      >
        <div className={styles.composition}>
          <figure
            ref={guideRef}
            className={styles.guide}
            data-open={open}
            aria-label="Center your face in the crop with similar space on both sides. Leave a little headroom and keep your whole head and shoulders visible."
          >
            <span className={styles.label}>Leave a little headroom</span>
            <div className={styles.window} aria-hidden="true">
              <span className={`${styles.corner} ${styles.topLeft}`} />
              <span className={`${styles.corner} ${styles.topRight}`} />
              <span className={`${styles.corner} ${styles.bottomLeft}`} />
              <span className={`${styles.corner} ${styles.bottomRight}`} />
              <span className={styles.headroom} />
              <span className={styles.centerline} />
              <UserRound
                className={styles.person}
                strokeWidth={0.8}
                aria-hidden="true"
              />
            </div>
            <figcaption className={styles.caption}>
              <Check size={13} aria-hidden="true" />
              <span>
                Center your face
                <br />
                in the crop
              </span>
            </figcaption>
          </figure>
          <div className={styles.advice}>
            <p>
              <strong>Crop too tight?</strong>
              Widen or reset it to include your whole head and shoulders.
            </p>
            <p>
              <strong>Too much empty space?</strong>
              Crop a little closer, without clipping your hair or shoulders.
            </p>
          </div>
        </div>
        <section className={styles.issues} aria-label="Common issues">
          <h4>Common issues</h4>
          <article>
            <h5>Shoulders cropped too tightly</h5>
            <p>
              Widen or reset the crop to show more of both shoulders. If
              they&apos;re cut off in the original, retake your selfie from
              farther away with your whole head and shoulders in view.
            </p>
          </article>
          <article>
            <h5>Photo looks off-center</h5>
            <p>
              Use the crop tool on your original photo to center your face, with
              similar space on both sides. Keep your whole head and shoulders
              visible.
            </p>
          </article>
          <article>
            <h5>Not facing straight ahead</h5>
            <p>
              Look directly at the camera with your head upright. If your head
              is turned or tilted, retake the photo; cropping cannot correct the
              angle.
            </p>
          </article>
        </section>
      </section>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((current) => !current)}
      >
        <Info size={14} aria-hidden="true" />
        <span>Not happy with the framing?</span>
        <ChevronDown size={16} className={styles.chevron} aria-hidden="true" />
      </button>
    </div>
  );
}
