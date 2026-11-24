import Image from "next/image";
import { ChevronDown, Info } from "lucide-react";
import sampleRules from "@/assets/sample_rules.jpg";
import styles from "./photo-guide.module.css";

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
      <details className={styles.examples}>
        <summary>
          <span>View photo examples</span>
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <div className={styles.content}>
          <p>taken from: Singapore ICA.</p>
          <Image
            src={sampleRules}
            alt="Singapore ICA photo guidelines comparing unsuitable and suitable portraits."
            className={styles.image}
            unoptimized
          />
        </div>
      </details>
    </aside>
  );
}
