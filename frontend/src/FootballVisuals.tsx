import { useState } from "react";
import type { TeamHeader } from "./types";

export type FootballIconName = "overview" | "flow" | "teams" | "goal" | "evidence";

export function FootballIcon({ name }: { name: FootballIconName }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (name === "flow") return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M3 17l5-5 4 3 8-9"/><path {...common} d="M16 6h4v4"/></svg>;
  if (name === "teams") return <svg viewBox="0 0 24 24" aria-hidden="true"><circle {...common} cx="8" cy="8" r="3"/><circle {...common} cx="17" cy="9" r="2.5"/><path {...common} d="M3 19c.5-4 2.2-6 5-6s4.5 2 5 6M14 19c.2-2.8 1.4-4.5 3.5-4.5 2 0 3.2 1.5 3.5 4.5"/></svg>;
  if (name === "goal") return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M4 20V6h16v14M4 9h16M8 9v11M16 9v11"/><circle {...common} cx="12" cy="15" r="2.4"/></svg>;
  if (name === "evidence") return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M6 3h9l3 3v15H6zM15 3v4h3M9 11h6M9 15h6"/></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect {...common} x="3" y="4" width="18" height="16" rx="2"/><path {...common} d="M12 4v16M3 12h18"/><circle {...common} cx="12" cy="12" r="2.5"/></svg>;
}

function initials(team: TeamHeader) {
  if (team.code) return team.code.slice(0, 3).toUpperCase();
  return (team.name ?? "Team").split(/\s+/).map(word => word[0]).join("").slice(0, 3).toUpperCase();
}

export function TeamBadge({ team, side = "home", size = "large" }: { team: TeamHeader; side?: "home" | "away"; size?: "small" | "large" }) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(team.crest_url) && !failed;
  return <span className={`team-badge ${side} ${size}`} aria-label={`${team.name ?? initials(team)} badge`}>
    {showImage ? <img src={team.crest_url ?? ""} alt={`${team.name ?? "Team"} crest`} onError={() => setFailed(true)} /> : <strong>{initials(team)}</strong>}
  </span>;
}
