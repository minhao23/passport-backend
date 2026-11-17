import { ArrowRight } from "lucide-react";

export default function SiteFooter() {
  return (
    <footer className="wrap">
      <a href="#" className="brand" aria-label="Passport Studio home">
        Passport Studio
      </a>
      <a
        className="footer-credit"
        href="https://minhao.vercel.app"
        target="_blank"
        rel="noopener noreferrer"
      >
        Contact me<span className="sr-only"> (opens in a new tab)</span>
      </a>
      <a href="#studio">
        Back to your photo <ArrowRight size={15} />
      </a>
    </footer>
  );
}
