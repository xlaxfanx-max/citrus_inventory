# Hold budget model

Added 14 September 2026 (model version v1.4). Closes item A3 / finding F2 from
the 10 September review: a lot that has already turned yellow used to show a
pack-by date months in the past and an "overdue" count that grew by one every
day. The house was still selling that fruit, so the number told the GM
nothing.

## The idea

Every color stage has a **hold budget**: the number of days a lot can sit at
that stage and still be marketable. The budget starts on the day the lot
entered the stage and is spent one day per day, faster in warm rooms and
faster when the samples show decay. What is left is the operative number
for lots at or past a stage.

| Stage at entry | Default budget | Trade guidance (NSW DPI) |
|---|---|---|
| Dark green | 165 days | 5 to 6 months |
| Light green | 60 days | about 2 months |
| Silver | 42 days | about 6 weeks |
| Yellow | 14 days | weeks, not months |

All six parameters are on the settings page under "Hold budget" and can be
tuned per house without a deploy: the four budgets, the warm multiplier and
the decay penalty.

## How it is computed

For each nightly prediction, in `forecast/model.py`:

1. **Stage entry day.** The same CCI path that gives `cci_now` (the fitted
   line, or the prior walked over the room history) is solved for the lower
   boundary of the current stage. A silver lot entered silver when its path
   crossed the light-green ceiling; a yellow lot when it crossed the yellow
   threshold. A lot received at or above that boundary entered on day 0.
2. **Days in stage** = today minus the entry day.
3. **Warm days in stage.** Days spent in rooms whose setpoint is at or above
   the warm threshold (the same threshold as the rot-risk clock). Each warm
   day spends `hold_warm_multiplier` days of budget, so with the default of
   2.0 a warm day costs one extra day.
4. **Decay penalty** = observed decay percent from the last two samples times
   `hold_decay_days_per_pct` (default 3 days per percent). Two decayed fruit
   in a 25-fruit sample is 8 percent and removes 24 days.
5. **Days remaining** = budget minus days in stage minus warm extra minus
   decay penalty, floored to a whole day. It can be negative: the budget is
   exhausted.
6. **Hold-until date** = today plus days remaining.

The prediction row stores `stage_entry_date`, `hold_days_remaining` and
`hold_until_date`; the components are in `inputs['hold']` for audit.

## Which date the board acts on

`Prediction.deadline_kind` decides:

- **Yellow lot:** the color pack-by date is in the past by construction, so
  the hold-until date is the deadline. The board shows "Hold budget ends
  Sep 24 · 10d of hold left · yellow since Sep 12", and once exhausted "hold
  exhausted 3d ago". Ranking, the 7-day bins-due tile, the capacity
  projection and the Monday report all use the same date.
- **Green lot:** whichever comes first of the color pack-by date and the
  hold-until date. The hold budget rarely binds before yellow unless the lot
  has sat warm for weeks or is decaying.
- **No hold data** (predictions from before v1.4): the color pack-by date,
  unchanged.

Published plans snapshot both dates and `deadline_kind`, and the outcome
scorecard measures packout lateness against the date the recommendation
actually acted on. The color pack-by date is still stored and shown as
context, and the accuracy screen still measures the color forecast against
the packout date.

## What is not modelled yet

- The budgets are trade rules of thumb, not fitted. Once the pilot has
  packout and holdout outcomes, the yellow budget in particular should be
  calibrated against fresh-pack percent by days since crossing.
- Decay type is not recorded, so sour rot and mold spend the budget at the
  same rate.
- Firmness and weight loss are captured on samples but do not yet feed the
  budget.
