export default function SiteHeader() {
  return (
    <>
      <a className="skip-link" href="#studio">
        Skip to photo studio
      </a>
      <header className="nav wrap">
        <a className="brand" href="#" aria-label="Passport Studio home">
          Passport Studio
        </a>
        <nav aria-label="Main navigation">
          <a href="#photo-tips">Photo guide</a>
          <span className="free-note">Free. No account needed.</span>
        </nav>
      </header>
    </>
  );
}
