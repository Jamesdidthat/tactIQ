import type { Json } from './types';

export const evidenceLabel = (level: string) => level === 'descriptive_moderate' ? 'Moderate' : 'Low';
// Presentation bands for an internal ranking score; not statistical confidence.
export const priorityLabel = (score: number) => score >= .75 ? 'High' : score >= .5 ? 'Medium' : 'Low';
const footballLabels: Record<string, string> = {
  defence_tactical_median_x: 'Defensive line position',
  defence_to_midfield_gap: 'Defence–midfield gap',
  midfield_to_attack_gap: 'Midfield–attack gap',
  total_outfield_length: 'Outfield team length',
  outfield_length: 'Outfield length',
  outfield_width: 'Outfield width',
  full_team_length: 'Full-team length',
  full_team_width: 'Full-team width',
  shots_for: 'Shots for',
  shots_conceded: 'Shots conceded',
  in_possession: 'In possession',
  out_of_possession: 'Out of possession',
  directional_matchup_interaction: 'Directional matchup interaction',
  general_team_comparison: 'General team comparison',
  supporting_tendency: 'Supporting tendency',
};
export const metricLabel = (key: string) => footballLabels[key] ?? key.replaceAll('_', ' ').replace(/\b\w/g, value => value.toUpperCase());
export function formatValue(key: string, value: Json | undefined): string {
  if (value === null || value === undefined) return 'Unavailable';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 'Unavailable';
    if (key.endsWith('_metres')) return `${value.toFixed(1)} m`;
    return Number.isInteger(value) ? value.toLocaleString('en') : value.toFixed(2);
  }
  return typeof value === 'string' ? value.replaceAll('_', ' ') : JSON.stringify(value);
}
