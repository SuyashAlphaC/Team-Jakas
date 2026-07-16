import { APP_TAGLINE, TEAM_NAME, TEAM_TRACK } from "../lib/brand";

export function BrandTagline({ variant = "header" }: { variant?: "header" | "footer" }) {
  return (
    <p className={`brand-tagline-row brand-tagline-row--${variant}`}>
      <span className="brand-tagline-phrase" aria-label={APP_TAGLINE}>
        {APP_TAGLINE.split(" ").map((word, i) => (
          <span
            key={word}
            className="brand-tagline-word"
            style={{ animationDelay: `${i * 0.12}s` }}
          >
            {word}
          </span>
        ))}
      </span>
      <span className="brand-tagline-sep" aria-hidden>·</span>
      <span className="brand-team-name">{TEAM_NAME}</span>
      <span className="brand-tagline-sep" aria-hidden>·</span>
      <span className="brand-track-badge">{TEAM_TRACK}</span>
    </p>
  );
}
