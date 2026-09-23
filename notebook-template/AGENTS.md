# Personal health notebook

This directory contains private health information. Read PROFILE.md for timezone,
units, and preferences. Record facts and organize questions; do not infer a
diagnosis, prescribe medication changes, or invent clinical targets.

## Files

- meal-log.org: weighed meals, nutrition calculations, and meal-related notes.
- foods.org: reusable product/ingredient nutrition, with source and serving basis.
- body-weight.org: dated weight measurements and units.
- glucose-log.org: user-supplied readings, units, device/source, and context.
- daily-log.org: other observations, exercise, and symptoms.
- lab-results.org: results with units, reference ranges, date, and source.
- appointment-questions.org: questions and follow-up actions for clinicians.

## Recording

Check `git status` before edits; preserve unrelated and unsaved user changes.
Keep entries chronological and use Org timestamps, e.g. `<2026-01-15 Thu 12:30>`.
Use the person's timezone. Ask if a date, time, or glucose unit is ambiguous;
do not silently treat server UTC as local time. Keep reported facts, estimates,
and interpretation distinguishable. Never invent missing results.

Use compact meal tables with `Food`, `Wt.`, `Carb`, `Cal`, `Fat`, `Prot.`, `Sat.`.
Weights and macros are grams, energy kcal; state the basis above the table.
Use numeric cells where known, `?` for unknowns, and put sources/uncertainty in
notes. Distinguish raw and cooked weights and per-100-g versus per-serving labels.
Calculate from the stated basis. Add meal subtotals and day totals when meaningful;
label incomplete totals. Reuse confirmed foods.org entries before estimating.

There is no automatic CGM connection in this version. Never claim to have checked
a live feed. Record supplied readings with their actual measurement time and
source; do not treat an old reading as current. The sensor's own app remains the
reference for its readings and alerts. Any future connector must explicitly
check freshness and report missing/stale data.

After useful updates, make a local Git commit of only the intended notebook files
unless asked otherwise. If Git identity is missing, ask for the preferred identity.
Push only when the owner has enabled backup and verified a private destination;
never publish records or transcripts. Do not add credentials, images, or exports
to Git. Do not read authentication files while diagnosing routine notebook issues.

Do not run simultaneous editing sessions on the same notebook. Do not modify
service configuration or install integrations during ordinary logging without
an explicit setup request.
