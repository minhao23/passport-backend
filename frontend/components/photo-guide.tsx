import {
  ArrowRight,
  Check,
  Info,
  ScanFace,
  Sun,
  UserRound,
} from "lucide-react";

const photoTips = [
  {
    icon: Sun,
    title: "Find the light.",
    detail: "Face a window. Skip harsh shadows and camera filters.",
  },
  {
    icon: ScanFace,
    title: "Keep it natural.",
    detail: "Head straight, eyes open, neutral expression. No sunglasses.",
  },
  {
    icon: UserRound,
    title: "Give yourself room.",
    detail:
      "Include your whole head and shoulders. We'll handle the background.",
  },
];

function FramingGuide() {
  return (
    <div
      className="framing-guide"
      role="img"
      aria-label="Framing guide: face the camera with your whole head and shoulders visible and space above your head."
    >
      <span className="framing-label">Leave a little headroom</span>
      <div className="framing-window">
        <i className="corner tl" />
        <i className="corner tr" />
        <i className="corner bl" />
        <i className="corner br" />
        <div className="headroom-line" />
        <UserRound className="framing-person" strokeWidth={0.8} />
        <div className="eye-line" />
        <span className="eye-label">Eyes level</span>
      </div>
      <span className="framing-caption">
        <Check size={14} /> Head &amp; shoulders in frame
      </span>
    </div>
  );
}

export default function PhotoGuide() {
  return (
    <section
      id="photo-tips"
      className="guide wrap"
      aria-labelledby="guide-title"
    >
      <div className="guide-panel">
        <div className="guide-intro">
          <h2 id="guide-title">
            A little prep.
            <br />A better shot.
          </h2>
          <p>
            No special setup. Just you,
            <br />
            your camera, and a window.
          </p>
          <a className="text-link" href="#studio">
            I have a photo <ArrowRight size={17} />
          </a>
        </div>
        <FramingGuide />
        <div className="guide-notes">
          {photoTips.map(({ icon: Icon, title, detail }) => (
            <article key={title}>
              <Icon size={21} />
              <div>
                <h3>{title}</h3>
                <p>{detail}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
      <div className="submission-note">
        <Info size={17} />
        <p>
          <strong>Before you submit.</strong> We resize and remove the
          background, but acceptance isn&apos;t guaranteed. Check your issuing
          authority&apos;s current rules on head size, expression, head
          coverings, and photo editing.
        </p>
      </div>
    </section>
  );
}
