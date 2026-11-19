import { ChevronDown } from "lucide-react";

type PhotoPreparationTipsProps = {
  country: string;
  compact?: boolean;
};

export default function PhotoPreparationTips({
  country,
  compact = false,
}: PhotoPreparationTipsProps) {
  const framingTip =
    country === "United Kingdom"
      ? "For UK online applications, use an uncropped original showing your head, shoulders and upper body."
      : "Crop just above the armpits. Keep your full head, shoulders and a little headroom.";

  const tips = (
    <ul>
      <li>{framingTip}</li>
      <li>
        Face forward at eye level, with eyes open and mouth closed. Avoid
        close-up selfies.
      </li>
      <li>
        Use even lighting and a sharp photo. Skip shadows and beauty filters.
      </li>
      <li>
        No headwear or sunglasses. Religious or medical coverings may be
        allowed; check your country&apos;s rules.
      </li>
    </ul>
  );

  if (compact) {
    return (
      <details className="mobile-photo-tips">
        <summary>
          Photo tips <ChevronDown size={16} aria-hidden="true" />
        </summary>
        {tips}
      </details>
    );
  }

  return (
    <section className="workspace-tips" aria-labelledby="workspace-tips-title">
      <h4 id="workspace-tips-title">Photo tips</h4>
      {tips}
    </section>
  );
}
