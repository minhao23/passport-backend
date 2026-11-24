import { Info } from "lucide-react";

export default function SubmissionNote() {
  return (
    <aside className="submission-guidance wrap" aria-label="Before you submit">
      <div className="submission-note">
        <Info size={17} aria-hidden="true" />
        <p>
          <strong>Before you submit.</strong> We resize and remove the
          background, but acceptance isn&apos;t guaranteed. Check your issuing
          authority&apos;s current rules on head size, expression, head
          coverings, and photo editing.
        </p>
      </div>
    </aside>
  );
}
