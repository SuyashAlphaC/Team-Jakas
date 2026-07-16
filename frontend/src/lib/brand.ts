export const APP_NAME = "Aperture";
export const APP_TAGLINE = "Signal through the surge";
export const TEAM_NAME = "Team Jakas";
export const TEAM_TRACK = "Track 2 Platinum";
export const APP_FULL_TITLE = `${APP_NAME} — ${APP_TAGLINE}`;

export const TAB_TITLES: Record<string, string> = {
  home: APP_FULL_TITLE,
  monitor: `${APP_NAME} · Live Monitor`,
  analysis: `${APP_NAME} · Analysis`,
  incidents: `${APP_NAME} · Incidents & RCA`,
  remediation: `${APP_NAME} · Remediation`,
  timeline: `${APP_NAME} · Timeline`,
  grafana: `${APP_NAME} · Grafana`,
};
