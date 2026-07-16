import { APP_NAME } from "../lib/brand";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="page-header anim-fade-in">
      <span className="page-eyebrow">{APP_NAME}</span>
      <h2>{title}</h2>
      {subtitle && <p className="muted">{subtitle}</p>}
    </div>
  );
}
