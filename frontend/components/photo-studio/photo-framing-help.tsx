"use client";

import { useId, useState } from "react";
import { Check, ChevronDown, Info, UserRound } from "lucide-react";
import styles from "./photo-framing-help.module.css";

export default function PhotoFramingHelp() {
  const [open, setOpen] = useState(false);
  const contentId = useId();

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
            className={styles.guide}
            role="img"
            aria-label="Leave a little headroom and keep your whole head and shoulders visible."
          >
            <span className={styles.label}>Leave a little headroom</span>
            <div className={styles.window} aria-hidden="true">
              <span className={`${styles.corner} ${styles.topLeft}`} />
              <span className={`${styles.corner} ${styles.topRight}`} />
              <span className={`${styles.corner} ${styles.bottomLeft}`} />
              <span className={`${styles.corner} ${styles.bottomRight}`} />
              <span className={styles.headroom} />
              <UserRound
                className={styles.person}
                strokeWidth={0.8}
                aria-hidden="true"
              />
            </div>
            <figcaption className={styles.caption}>
              <Check size={13} aria-hidden="true" />
              <span>
                Head &amp; shoulders
                <br />
                in frame
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
              We need enough of both shoulders visible to frame your photo
              cleanly. Widen or reset the crop. If the original photo cuts them
              off, use a wider photo.
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
