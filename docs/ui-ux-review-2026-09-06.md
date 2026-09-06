# UI/UX review — 6 September 2026

Reviewed every screen on desktop (1300px) and phone (375px) with the demo season loaded, as `admin1` and `foreman1`. Screens: packing plan, lot detail, plan list, plan detail, sample route, capture, sample status, imports, validation, readiness, settings, login.

Overall the app is in good shape: one consistent stylesheet, a clear green palette, sensible responsive cards on the board, a fast four-step capture flow, and honest empty states. The problems below are mostly about *density and priority on the phone*, a handful of real bugs, and inconsistency between screens that were built at different times.

## Confirmed bugs

| # | Where | What | Fix |
|---|---|---|---|
| B1 | Readiness | Check values (e.g. "18 / 28 active lots") render as small grey uppercase text because the global `h3` style is the section-label style. | Use `.tile .num` markup or a dedicated class. |
| B2 | Lot detail | The pack-by tile only turns red when `timeuntil` returns "0 minutes". A lot 83 days overdue shows a plain black "Jun 15". | Compute `overdue_days` in the view and set the tile tone from it (the board already does this). |
| B3 | Board, phone cards | Stage chip shows the raw code ("Y") where the desktop table shows "Yellow"; the overdue line is muted grey instead of the red flag the table uses. | Use `get_stage_display` and the same tone logic as the table. |
| B4 | Capture | Radio inputs are hidden with `opacity:0; width:0`, so the browser's "please select one" validation bubble anchors to an invisible point. A foreman who skips step 2 sees the page refuse to submit with no visible reason. | On submit, check each required fieldset, add an error style and scroll to the first incomplete step. |
| B5 | base.html | `th { position: sticky }` never sticks: the table sits inside `.table-wrap { overflow-x:auto }`, and `top:0` would slide under the sticky site header anyway. | Either drop it or make `.table-wrap` overflow only on narrow screens and set `top` to the header height. |
| B6 | Board tiles | "1223.0 known bins due" — bins shown with one decimal where whole numbers read better. | `floatformat:0` unless fractional bins are real. |
| B7 | Header, phone | Nav scrolls horizontally; "Log out" is cut off for GM/admin and there is no scroll hint. The username is only visible as a tooltip on the Log out button. | See P1 below. |

## Priority improvements

### P1. Reclaim the phone screen (all roles)

On a 375px phone the first lot card on the packing plan starts 1080px down: header (95px), disclaimer (74px), title block, filter card, five tiles, decisions card, chip row. A foreman opening the app between bins sees no lot without scrolling.

- Shrink the disclaimer to one line ("Estimates need manager review · why?") that expands on tap, and remember dismissal for the session. Keep the full text on the lot detail page next to the chart, where it is actually read. The demo-mode notice can be a small pill in the header.
- Replace the scrolling top nav on phones with a bottom tab bar holding the role's three primary destinations (foreman: Samples, Plan, Decisions; GM/admin: Plan, Decisions, Samples) and a "More" sheet for Imports, Validation, Readiness, Settings, Admin, Log out.
- Show who is logged in and at which plant in the header (`gm1 · SLA1`). The plant switcher should live there too, persisted in the session, instead of being re-implemented on five screens in three different styles.
- Board filters: make Plant and Room auto-submit on change (the plan list already does this) and debounce the search like the sample route does. That removes the full-width Apply and Reset buttons.
- The five summary tiles and the five filter chips say the same thing. Make the tiles the filters (tap "Observed decay flags 9" to filter) and drop the chip row, or vice versa.

### P2. Plan detail: make Monday decisions fast (GM)

Recording 17 decisions currently means 17 times: open "Record decision", pick a status, pick a reason, save, page reload. The form lives inside a 220px table cell and on a phone the eight-column table scrolls sideways.

- One-click **Accept** button per row (POST `status=accepted`, no reason needed), with "Defer / override…" opening the form.
- "Accept all remaining" with a confirm, recorded as individual decisions so the audit trail is unchanged.
- On phones render each recommendation as a card (reuse the board's card pattern) with the decision form inline under it.
- Save via fetch and update the row in place so the GM keeps their scroll position; fall back to the full POST without JavaScript.

### P3. Capture flow polish (foreman, phone)

The flow is already good. The remaining friction is above the photo button.

- Remember the last calibration station per device (localStorage) and preselect it; move its help text behind an info toggle. The "collect 10 fruit across 5 bins" paragraph belongs in step 1's dashed box, not above it.
- Hide the native file input. The dashed box is the button; after selection show the preview inside it with a "Retake" link.
- Fix B4 so a missed step is visible.
- Pre-highlight the previous check's colour and pack-within choice as a faint "last time" hint on the tap grids, without preselecting them.
- Route list: never-sampled lots show "1.4 wk →" while sampled lots show "10d due →". Use one unit: "never · 10 wk stored" vs "10d overdue".

### P4. Lot detail: action first, history on demand

- The metadata line is a nine-item "·" run-on that wraps into a three-line blob on phones. Render it as a two-column key/value grid.
- Reorder the tiles: pack-by date with days remaining/overdue (red when overdue, fixes B2), bins remaining, decay, model stage, weeks stored. CCI now and drift per day belong in "Technical model details".
- The chart's SVG is 760×300 with 12px text; on a phone it scales to 320px wide and the axis labels are about 5px. Either scale fonts up at small widths via a `<style>` inside the SVG, or let the chart scroll horizontally at a 560px minimum width.
- Put Samples and Photos directly under the chart; collapse Prediction history, Room moves, Storage exposure, Treatments and Packout into `<details>` with counts in the summary ("Prediction history · 22").
- Samples table: show only non-zero defect counts ("decay 3" instead of "D 3 · soft 0 · shrivel 0 · chill 0 · rind 0"), "none" otherwise.
- Packout has 13 columns. Split into a summary row plus an expandable carton breakdown, or one card per packout.

### P5. Consistency pass

- A shared page-header include (eyebrow, title, lede, right-hand actions). Imports, Import detail and Settings currently use a bare `h2` and look like a different app.
- Standard back-link style and position (currently four variants).
- Validation and Readiness overlap: the Validation page repeats a "Prediction data readiness" table. Rename the nav items to what they answer ("Outcomes" and "Data coverage") and keep coverage on one page.
- Settings: the "Monday report recipients" card also holds weekly capacity per plant; rename it "Plants". Add a sticky Save bar since the button is below five cards.
- Imports: make batch rows clickable rather than the small "details" link; show the row-error count as a link straight to the errors.

### P6. Later, if wanted

- Adopt htmx for the fetch-based pieces above (board filters, decision saves, sample-status polling, route search). The route search already hand-rolls an `HX-Request` header, so the server side is half there.
- Dark mode via `prefers-color-scheme`; the palette is already in CSS variables so it is mostly a second `:root` block.
- Board: group rows into urgency bands (Overdue / This week / Next 4 weeks / Monitoring) with sticky band headers instead of one flat list.
- Login: 44px inputs and a show-password toggle for phone typing.

## Suggested order

1. Bugs B1–B7 (an hour, no behaviour change).
2. P1 phone layout and P3 capture polish, since foremen use the phone daily.
3. P2 plan decisions before the next Monday plan.
4. P4 and P5 as a follow-up.
