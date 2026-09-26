import { useMemo, useState } from "react";
import { RealTrackingClip } from "./FootballShapeProfileView";
import type { GoalAnalysis, MatchTacticalProfile, MatchTimeSegment, ShapeFrameReference, TeamMatchTacticalProfile } from "./types";

type StoryMetric = {
  key: string;
  label: string;
  highlight: ShapeFrameReference["highlight"];
  threshold: number;
  higher: string;
  lower: string;
};

const STORY_METRICS: StoryMetric[] = [
  { key: "defensive_line_position_metres", label: "Defensive-line position", highlight: "defensive_line", threshold: 5, higher: "moved higher", lower: "dropped deeper" },
  { key: "outfield_width_metres", label: "Team width", highlight: "width", threshold: 5, higher: "became wider", lower: "became narrower" },
  { key: "outfield_length_metres", label: "Back-to-front spacing", highlight: "length", threshold: 5, higher: "became more stretched", lower: "became more compact" },
];

type TeamShift = {
  team: TeamMatchTacticalProfile;
  segment: MatchTimeSegment;
  previous: MatchTimeSegment;
  metric: StoryMetric;
  previousValue: number;
  currentValue: number;
  difference: number;
  strength: number;
};

type WindowStory = { minute: number; endMinute: number; primary: TeamShift; shifts: TeamShift[] };

const numberValue = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;

function reference(segment: MatchTimeSegment, matchId: string | number, metric: StoryMetric, label: string): ShapeFrameReference | null {
  const frame = numberValue(segment.evidence.representative_frame);
  const period = numberValue(segment.evidence.representative_period);
  if (frame == null || period == null) return null;
  return {
    match_id: matchId,
    frame,
    period,
    label,
    highlight: metric.highlight,
    clip_before_seconds: 6,
    clip_after_seconds: 6,
    clip_reason: "This window shows a representative real shape from the selected spell. Compare both clips; it does not compress the entire 15-minute period into one animation.",
  };
}

function windowStories(profile: MatchTacticalProfile): WindowStory[] {
  const shifts: TeamShift[] = [];
  for (const team of profile.team_profiles) {
    team.segments.forEach((segment, index) => {
      if (!index || !segment.change_from_previous.length) return;
      const previous = team.segments[index - 1];
      const candidates = STORY_METRICS.flatMap(metric => {
        const before = numberValue(previous.evidence[metric.key]);
        const after = numberValue(segment.evidence[metric.key]);
        if (before == null || after == null || Math.abs(after - before) < metric.threshold) return [];
        return [{ team, segment, previous, metric, previousValue: before, currentValue: after, difference: after - before, strength: Math.abs(after - before) / metric.threshold }];
      }).sort((a, b) => b.strength - a.strength || a.metric.key.localeCompare(b.metric.key));
      if (candidates[0]) shifts.push(candidates[0]);
    });
  }
  const byWindow = new Map<number, TeamShift[]>();
  shifts.forEach(item => byWindow.set(item.segment.start_minute, [...(byWindow.get(item.segment.start_minute) ?? []), item]));
  const windows = [...byWindow.entries()].map(([minute, items]) => ({
    minute,
    endMinute: items[0].segment.end_minute,
    primary: [...items].sort((a, b) => b.strength - a.strength || String(a.team.team_id).localeCompare(String(b.team.team_id)))[0],
    shifts: [...items].sort((a, b) => String(a.team.team_id).localeCompare(String(b.team.team_id))),
  }));
  return windows.sort((a, b) => b.primary.strength - a.primary.strength || a.minute - b.minute).slice(0, 3).sort((a, b) => a.minute - b.minute);
}

function shiftSentence(shift: TeamShift) {
  const action = shift.difference > 0 ? shift.metric.higher : shift.metric.lower;
  return `${shift.team.team_name} ${action}: ${shift.previousValue.toFixed(1)}m to ${shift.currentValue.toFixed(1)}m.`;
}

function storyHeadline(story: WindowStory) {
  const lineShifts = story.shifts.filter(item => item.metric.key === "defensive_line_position_metres");
  if (lineShifts.length === 2 && Math.sign(lineShifts[0].difference) !== Math.sign(lineShifts[1].difference)) {
    const higher = lineShifts.find(item => item.difference > 0)!;
    const deeper = lineShifts.find(item => item.difference < 0)!;
    return `${higher.team.team_name} pushed higher as ${deeper.team.team_name} dropped`;
  }
  const action = story.primary.difference > 0 ? story.primary.metric.higher : story.primary.metric.lower;
  return `${story.primary.team.team_name} ${action}`;
}

function ShapeStoryCard({ story, matchId, order }: { story: WindowStory; matchId: string | number; order: number }) {
  const [moment, setMoment] = useState<"before" | "after">("after");
  const before = reference(story.primary.previous, matchId, story.primary.metric, `Before · ${story.primary.previous.start_minute}'–${story.primary.previous.end_minute}'`);
  const after = reference(story.primary.segment, matchId, story.primary.metric, `Changed spell · ${story.minute}'–${story.endMinute}'`);
  const selected = moment === "before" ? before : after;
  return <article className="visual-story-card shape-story-card">
    <header><span>{order}</span><div><small>{story.minute}'–{story.endMinute}' · Team structure</small><h3>{storyHeadline(story)}</h3></div></header>
    <p>{story.shifts.map(shiftSentence).join(" ")}</p>
    <div className="story-moment-tabs"><button className={moment === "before" ? "active" : ""} onClick={() => setMoment("before")}>Before</button><button className={moment === "after" ? "active" : ""} onClick={() => setMoment("after")}>Changed spell</button></div>
    {selected ? <RealTrackingClip reference={selected} teamId={story.primary.team.team_id}/> : <p className="football-empty">A representative tracking frame is unavailable.</p>}
    <details><summary>Why this moment was selected</summary><p>The period-to-period change exceeded TactIQ's existing five-metre descriptive threshold. The clips show representative shapes from each window; they do not prove what caused the change.</p><dl>{story.shifts.map(shift => <div key={`${shift.team.team_id}-${shift.metric.key}`}><dt>{shift.team.team_name} · {shift.metric.label}</dt><dd>{shift.difference > 0 ? "+" : ""}{shift.difference.toFixed(1)}m</dd></div>)}</dl></details>
  </article>;
}

function GoalStoryCard({ goal, matchId, order }: { goal: GoalAnalysis; matchId: string | number; order: number }) {
  const context = goal.tracking_context;
  const frame = numberValue(context?.frame);
  const period = numberValue(context?.period);
  const ref: ShapeFrameReference | null = frame == null || period == null ? null : {
    match_id: matchId,
    frame,
    period,
    label: "Goal-leading sequence",
    highlight: context?.line_structure_complete ? "defence_midfield_gap" : "none",
    clip_before_seconds: 12,
    clip_after_seconds: 3,
    clip_reason: "The evidence window begins before the final tracked shot action so the team structure and ball movement can be reviewed together.",
  };
  return <article className="visual-story-card goal-story-card">
    <header><span>{order}</span><div><small>{goal.minute}:{String(goal.second).padStart(2, "0")} · Goal investigation</small><h3>{goal.scoring_team_name}'s goal-leading move</h3></div></header>
    <p>{goal.what_happened} {goal.what_created_the_opportunity}</p>
    {ref ? <RealTrackingClip reference={ref} teamId={goal.conceding_team_id}/> : <p className="football-empty">Full tracking could not be aligned to this goal-leading action.</p>}
    <div className="goal-story-answers"><div><strong>Had this been happening earlier?</strong><p>{goal.had_this_been_happening_earlier}</p></div><div><strong>Recurring or match-specific?</strong><p>{goal.recurring_season_pattern}</p></div><div><strong>Structure or execution?</strong><p>{goal.structural_versus_execution}</p></div></div>
    <details><summary>Evidence limits</summary>{goal.limitations.map(item => <p key={item}>{item}</p>)}</details>
  </article>;
}

export function VisualMatchStory({ profile }: { profile: MatchTacticalProfile }) {
  const shapeStories = useMemo(() => windowStories(profile), [profile]);
  const entries = [
    ...shapeStories.map(story => ({ type: "shape" as const, minute: story.minute, story })),
    ...profile.goals.filter(goal => goal.tracking_context).map(goal => ({ type: "goal" as const, minute: goal.minute + goal.second / 60, goal })),
  ].sort((a, b) => a.minute - b.minute);
  return <section className="visual-match-story">
    <header className="match-section-intro"><div><small>Visual match story</small><h2>Watch how the game changed</h2></div><p>Each chapter uses the real positions of both teams and the ball. Period comparisons are descriptive; they do not assign a cause or tactical intention.</p></header>
    <nav className="visual-story-index" aria-label="Visual story chapters">{entries.map((entry, index) => <a href={`#visual-story-${index + 1}`} key={`${entry.type}-${entry.minute}`}><span>{index + 1}</span><strong>{entry.type === "goal" ? `${entry.goal.scoring_team_name} goal` : storyHeadline(entry.story)}</strong><small>{Math.floor(entry.minute)}'</small></a>)}</nav>
    <div className="visual-story-list">{entries.map((entry, index) => <div id={`visual-story-${index + 1}`} key={`${entry.type}-${entry.minute}`}>{entry.type === "goal" ? <GoalStoryCard goal={entry.goal} matchId={profile.match_id} order={index + 1}/> : <ShapeStoryCard story={entry.story} matchId={profile.match_id} order={index + 1}/>}</div>)}</div>
    {!entries.length && <p className="football-empty">No full-tracking match changes or goal sequences passed the current deterministic evidence rules.</p>}
  </section>;
}
