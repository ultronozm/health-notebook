# Personal health notebook

This directory contains private health information. Read PROFILE.md for timezone,
units, and preferences. Record facts and organize questions; do not infer a
diagnosis, prescribe medication changes, or invent clinical targets.

## Files

- meal-log.org: weighed meals, nutrition calculations, and meal-related notes.
- foods.org: reusable product/ingredient nutrition, with source and serving basis.
- batches.org: recipe ingredients, finished batch weights, and nutrition per 100 g.
- nutrition-targets.org: optional daily nutrition goals and their source.
- body-weight.org: dated weight measurements and units.
- glucose-log.org: user-supplied readings, units, device/source, and context.
- daily-log.org: other observations, exercise, and symptoms.
- lab-results.org: results with units, reference ranges, date, and source.
- appointment-questions.org: questions and follow-up actions for clinicians.

## Recording

Check `git status` before edits; preserve unrelated and unsaved user changes.
Keep entries chronological and date them with Org timestamps, e.g. `<2026-01-15 Thu>`.
Use the person's timezone. Ask if a date, time, or glucose unit is ambiguous;
do not silently treat server UTC as local time. Keep reported facts, estimates,
and interpretation distinguishable. Never invent missing results.

Use one nutrition table per day, under a dated heading such as
`* <2026-01-15 Thu>`, with columns
`Time`, `Item`, `Wt.`, `Carb`, `Cal`, `Fat`, `Prot.`, `Sat.`, `Notes`.
Write `Time` as plain `HH:MM`; the heading carries the date. Name items exactly
as their foods.org `Food`, or `Food, Product` when the food has several products
(a batch portion as `<name> batch YYYY-MM-DD`), so records stay linked.
Label aggregate rows `Subtotal`, `Day so far`, or `Day total` (qualifiers can
follow those words). Add meals to that day's table so totals cover the whole day.
Weights and macros are grams, energy kcal; state the basis above the table.
Use numeric cells where known, `?` for unknowns, and put sources/uncertainty in
notes. Distinguish raw and cooked weights and per-100-g versus per-serving labels.
Calculate from the stated basis. Add meal subtotals and day totals when meaningful;
label incomplete totals. Reuse confirmed foods.org entries before estimating.

When sent a food-label photo, save the product name/variant, nutrition values,
serving basis, and label source in foods.org. Ask about unreadable figures rather
than guessing. Preserve the label's carbohydrate/fiber convention. Use this
entry for later weighed portions; clarify which product only if ambiguous.

For plate photos, estimate components and portions, noting assumptions such as
oil or sauce. Mark these as photo estimates, not measured weights. Incorporate
corrections, leftovers, and second helpings into the same meal entry.

For home-cooked batches, record ingredient weights and total nutrition in
batches.org. Use the finished edible batch weight to calculate per-100-g values
and later portions. Keep each batch identifiable by name and date. For dashboard
compatibility, follow ~/health-notebook-kit/examples/notebook/batches.org.

Record weight in body-weight.org with date, units, and any measurement context.
For test results, preserve the reported value, units, reference range, and date
in lab-results.org; keep interpretation separate in Note. Use the template's
column names so the dashboard can read these records.

Save the owner's chosen nutrition targets in nutrition-targets.org. Compare
logged totals with these targets when asked and report remaining amounts or
ranges, making clear when the day's record is incomplete. Goals are optional;
do not fill in targets on the owner's behalf.

If automatic glucose import is configured in PROFILE.md, check the archive with
`python3 ~/health-notebook-kit/extras/librelinkup/latest_raw_status.py` before
using its readings. Check measurement time as well as pull time; a successful
pull can contain old readings. Otherwise use only readings supplied by the owner.
Record supplied readings with their actual measurement time and
source; do not treat an old reading as current. For screenshots, distinguish
measurement time from the time the image was sent.
The sensor's own app remains the reference for its readings and alerts.

After useful updates, make a local Git commit of only the intended notebook files
unless asked otherwise. If Git identity is missing, ask for the preferred identity.
Push to the owner's configured backup if enabled in PROFILE.md. Keep credentials
out of Git; screenshots and exports use the separate backup described in the
operations guide. Coordinate edits if more than one session uses the notebook.
