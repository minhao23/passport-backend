"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import original from "@/assets/bg.png";
import removed from "@/assets/bgremoved.png";
import styles from "./background-comparison.module.css";

export default function BackgroundComparison() {
  const [position, setPosition] = useState(50);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(true);
  const direction = useRef(1);

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(preference.matches);
    update();
    preference.addEventListener("change", update);
    return () => preference.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (hovered || focused || dragging || reducedMotion) return;
    let frame: number;
    let previous: number | undefined;
    function animate(time: number) {
      const elapsed = previous === undefined ? 0 : Math.min(time - previous, 50);
      previous = time;
      const delta = direction.current * elapsed * 0.012;
      setPosition(current => {
        const next = current + delta;
        return Math.max(0, Math.min(100, next));
      });
      frame = requestAnimationFrame(animate);
    }
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [hovered, focused, dragging, reducedMotion]);

  useEffect(() => {
    if (position >= 100) direction.current = -1;
    if (position <= 0) direction.current = 1;
  }, [position]);

  function updatePosition(event: PointerEvent<HTMLInputElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    setPosition(Math.round(Math.max(0, Math.min(100,
      ((event.clientX - bounds.left) / bounds.width) * 100,
    ))));
  }

  return (
    <figure className={styles.comparison}>
      <div
        className={styles.stage}
        onPointerEnter={event => { if (event.pointerType === "mouse") setHovered(true); }}
        onPointerLeave={event => { if (event.pointerType === "mouse") setHovered(false); }}
      >
        <Image
          src={original}
          alt="Illustrated portrait with a city background"
          fill
          priority
          sizes="(max-width: 900px) 90vw, 460px"
          className={styles.original}
          draggable={false}
        />
        {/* Clip a full-size layer so dragging never changes the portrait scale. */}
        <div className={styles.removed} style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}>
          <Image
            src={removed}
            alt="The same illustrated portrait with a white background"
            fill
            priority
            sizes="(max-width: 900px) 90vw, 460px"
            draggable={false}
          />
        </div>
        <div className={styles.divider} style={{ left: `${position}%` }} aria-hidden="true" />
        <input
          className={styles.control}
          type="range"
          min={0}
          max={100}
          step="any"
          value={position}
          aria-label="Reveal background removal"
          aria-valuetext={`${Math.round(position)}% background removed`}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={event => {
            setFocused(true);
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              setPosition(current => Math.max(0, Math.min(100, current + (event.key === "ArrowRight" ? 1 : -1))));
            }
          }}
          onChange={event => setPosition(Number(event.target.value))}
          onPointerDown={event => {
            if (event.button !== 0) return;
            event.preventDefault();
            setDragging(true);
            event.currentTarget.focus();
            setFocused(false);
            event.currentTarget.setPointerCapture(event.pointerId);
            updatePosition(event);
          }}
          onPointerMove={event => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) updatePosition(event);
          }}
          onPointerUp={event => {
            setDragging(false);
            if (event.currentTarget.hasPointerCapture(event.pointerId)) {
              updatePosition(event);
              event.currentTarget.releasePointerCapture(event.pointerId);
            }
          }}
          onLostPointerCapture={() => setDragging(false)}
          onPointerCancel={() => setDragging(false)}
        />
      </div>
    </figure>
  );
}
