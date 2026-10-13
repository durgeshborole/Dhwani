# Problem Statement

**One line:** Mumbai's suburban trains run late constantly — especially in the
monsoon — but commuters can't tell in the moment whether *their* line is at
risk, and planners have no clear picture of where the delays concentrate.
Dhwani makes that visible, and where possible live.

## The full statement

> Mumbai's suburban railway carries over 7 million passengers a day and is the
> city's lifeline, yet it is frequently delayed — and the monsoon makes it far
> worse, with heavy rain flooding tracks and slowing entire lines. Two things
> are missing. **Commuters** have no way to judge, right now, whether their line
> is likely to be running late today. And **planners** have no quantified
> picture of how much rainfall costs each line, at which stations and hours the
> delays concentrate, or which routes are least reliable. This project builds a
> **monsoon-aware reliability system** that both **quantifies historically** how
> rain delays each line, station and hour, and uses **live weather, traffic and
> air-quality signals** to estimate current delay risk on each line — turning a
> daily frustration into an actionable signal for commuters and measurable
> evidence for planners.

## Who benefits

- **Commuter** — wants "is my line at risk right now?" (the *commuter* login).
- **Planner / researcher** — wants "where should we target the fix?"
  (the *admin* dashboard).

## What is measured

- Delay in minutes per **line**, per **station**, per **hour**, per **month**.
- The relationship between **rainfall and delay** (the monsoon impact).
- A **live delay-risk score** per line.
- **Reliability rankings** across routes.

## How we know it is solved

- A headline number: e.g. *"the Western Line loses X minutes on average in
  July versus Y in February"* (see the **Wet season vs dry season** table).
- A ranking: the stations and hours that account for most delays
  (see **Station hotspots** and the **heat-map**).
- A live view that updates as the weather and traffic change.

## Scope and honesty

- Weather data is **real** (Open-Meteo, live and historical).
- Delay history is **modelled** from the timetable plus real rainfall, because
  Mumbai publishes no open delay feed. The model is documented, not hidden —
  and the rain→delay relationship is exactly what the project studies.
- Real-time train GPS is **out of scope** (no public feed); the live layer
  estimates risk from weather, traffic and air quality instead.
