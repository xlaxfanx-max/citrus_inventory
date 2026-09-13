# Product review and outside research — 7 September 2026

**Scope.** Review of the two design commits landed since 6 September (`a19b800` "Improve platform design and daily operations UX" and `5972384` "Simplify platform design around daily operations"), a browser walk-through of every screen as GM and foreman on desktop and phone, and three parallel outside-research passes on (1) Saticoy and the 2025–26 lemon market, (2) competing and adjacent products, and (3) pilot structure, funding, workforce and postharvest science. Research was done 7 September 2026 by web search; every claim carries its source, and inferences are marked.

**Verdict.** The product is in good shape for a demonstration: 111 tests pass, checks are clean, the new shell is consistent and phone-usable. Six items from the 6 September UX review are still open and three of them sit on the daily foreman and Monday GM paths. The outside research changes the roadmap more than the UI: the forecast should move to a temperature-band model with a separate decay clock, the sample should grow from 10 to 25 fruit, the capture flow should be Spanish-first with a lot scan, and there is a funding deadline in two weeks (CDFA Specialty Crop Block Grant 2027 concept proposals close 21 September 2026).

---

## 1. State of the product

### Verified today

| Check | Result |
|---|---|
| Working tree | Clean; all changes are in the two commits above |
| Tests | 111 passed in 43.5 s (SQLite, after `collectstatic`) |
| Django checks / migrations | No issues; no missing migrations |
| Browser walk-through | GM on 1300 px and 375 px; foreman on 375 px; board, plan list, plan detail, lot detail, readiness, validation, imports, sample route, capture, login, menu |
| Console | No application errors |

### What the two commits got right

- One stylesheet (`static/app.css`) and one script replace the inlined CSS in `base.html`; print, reduced-motion, 44 px targets and 16 px phone inputs are covered. The README now says to run `collectstatic` before tests because templates use the static manifest.
- New header: brand, date, role-aware navigation, account and role label, collapsible phone menu with Escape and outside-click close, skip link, `aria-current`. This closes B7 from the 6 September review.
- The disclaimer is a one-line `<details>`; the summary tiles are now links that filter the board; room selection is validated against the plant (with a test); changing plant clears the room and auto-submits; "Clear filters" appears only when a filter is set; the empty state is role-aware.
- Phone lot cards use `get_stage_display` (B3 fixed); table rows have `aria-label`s; evidence notes collapse; the inventory table has a fixed layout with wrapping.
- Sample route search moved to `sample-route.js` with abort and sequence guards, `inert` while loading, a live status line, `history.replaceState`, redirect handling, and it no longer disturbs the day's route progress (tested).
- Capture accepts "Today"; imports and login pages received proper headings, help text and download buttons.

### Still open from the 6 September review (confirmed in the browser)

| # | Where | What I saw today | Fix |
|---|---|---|---|
| B2 | Lot detail | Lot 26-1013 shows "Jun 17" in plain black; the board says 82 days overdue. The tile still tests `timeuntil == '0 minutes'` (`lots/templates/lots/lot_detail.html:23`). | Pass `overdue_days` from the view; tone the tile like the board row. |
| B4 | Capture | Submitting with nothing chosen focuses an invisible radio and renders zero error elements. | On submit, mark incomplete fieldsets and scroll to the first. |
| B6 | Board tiles, table, cards, plan detail, lot detail | "661.0 known bins", "154.0 bins". | `floatformat:0` unless fractional bins are real. |
| P1 | Board, phone | First lot card starts ~890 px down (was 1080). Filter bar keeps a full-width Apply although plant and room auto-submit. Chip row duplicates the tiles. | Drop Apply when JS is present; keep tiles or chips, not both. |
| P2 | Plan detail | Each of 16 undecided rows still needs open, pick status, pick reason, save, reload. On phone the eight-column table scrolls sideways and the decision column is off-screen. | One-tap Accept per row; "Accept all remaining"; phone cards; fetch save. |
| P3 | Capture | Native file input visible inside the dashed box; calibration select and two help paragraphs sit above the photo button; route list mixes "1.6 wk" and "11d since check". | Hide the input, move help behind a toggle, one unit. |
| P4 | Lot detail | Nine-item "·" metadata run-on wraps to three lines on phone; tiles unchanged (weeks first, pack-by sixth); samples table prints "D 2 · soft 0 · shrivel 0 · chill 0 · rind 0"; room interval prints `2026-05-31T00:00:00-07:00` and "exclusive". | Key/value grid; reorder tiles; non-zero counts only; format dates. |
| B5 | CSS | `th { position: sticky; top: 0 }` inside the `overflow-x` wrapper never sticks. | Remove. |

### New observations

- `base.html` hardcodes "Saticoy" in the brand and footer. Fine for the pilot; move to a setting before a second customer.
- The desktop "Known bins due · 7 days" tile lost its red tone in the redesign; it is the capacity number the GM plans against.
- Readiness reports "0 active setups; 0 photos with references" but does not link admins to register a station.
- Validation reports "0 of 14 packed lots have a direct color or decay label"; the only way to add labels is the packout CSV. QC has no in-app screen to record final packout quality.
- Plan detail on phone spends a full screen on KPI tiles before the first recommendation.
- The capture photo input already has `capture="environment"`, so phones open the camera directly. Good.

---

## 2. What the outside research says

### 2.1 Saticoy and the market (agent 1)

- **Saticoy is signalling modernisation.** CFO Laura Troost was profiled on 7 April 2026 as leading "modernizing legacy processes" and integrating accounting, operations and IT ([NSAC](https://nsacoop.org/articles/year-international-woman-farmer-spotlight-laura-troost-saticoy-lemon-association)). CEO Marty Coert (since 1 January 2023) came up through operations ([Produce News](https://theproducenews.com/saticoy-lemon-ceo-retires-successor-named?page=2)). Saticoy's own Plant Manager posting defines the job as managing "fruit processing and storage to meet company standards for quality, size, and color" (BeBee listing, now removed; seen via search snippet).
- **No public source names Saticoy's ERP, sorter or QC vision system.** The Famous and Clarifruit facts come from the pilot relationship only.
- **The market flipped from deficit to oversupply in August 2026** when Argentina and Chile shipped roughly double the planned volume ([Blue Book, 26 Aug 2026](https://www.bluebookservices.com/produce-industry-headlines-august-26-2026/)). June 2026 pricing had exceeded $20 per carton, "not seen since 2018" ([Limoneira Q2 call](https://finance.yahoo.com/markets/stocks/articles/limoneira-q2-earnings-call-highlights-220614431.html)). Argentine imports were ~94,000 t in 2024 versus ~8,000 t in 2018; the 10 % tariff was retained and California Citrus Mutual is seeking a tariff-rate quota ([AgNet West](https://agnetwest.com/california-citrus-argentine-lemon-imports/), [CCM Feb 2026](https://www.cacitrusmutual.com/2026/02/12/argentina-reciprocal-trade-agreement-bottom-line-for-california-citrus/)).
- **Ventura grower economics.** June 2025: 70 % fresh utilisation at $18.50 FOB did not cover ~$6,500 per acre; losses of $1,500–2,000 per acre and orchard removals ([CA Farm Bureau via Sierra Sun Times](https://goldrushcam.com/sierrasuntimes/index.php/news/local-news/67941-california-farm-bureau-lemon-growers-struggle-with-supply-market-slump-california-accounts-for-95-of-u-s-lemon-production)). Fresh on-tree price Aug 2025–Jan 2026 averaged $29.77 per box ([USDA ERS FTS-384](https://www.ers.usda.gov/media/20866/fts-384.pdf?v=55721)). Ventura County lemon value rose 54 % to $181.7 M in 2025.
- **Limoneira as the public proxy.** FY2025: 4.7 M cartons; packing direct cost per carton swings from about $9 in high-volume quarters to $13–14.50 in low-volume quarters (inference from 8-K segment data). Limoneira rejoined Sunkist on 1 November 2025 and now describes an "oversupplied lemon offering" ([8-K Q4 FY25](https://www.sec.gov/Archives/edgar/data/1342423/000134242325000038/lmnr103125erex991.htm)). Q3 FY2026 results are due **9 September 2026**. No public source gives a products (juice) lemon price; it must come from Famous.
- **Decay risk is documented for California long-storage lemons**: sour rot on propiconazole-treated fruit stored for extended periods, with fungicide resistance ([PubMed](https://pubmed.ncbi.nlm.nih.gov/39441531/)).
- **Sunkist** has the "i3" technology umbrella and a March 2025 minority stake in Sienz with a stated goal to "collect the right data, leverage automation, and apply AI" ([Sunkist](https://sunkist.com/press-room/sunkist-closes-strategic-investment-in-sienz-to-accelerate-innovation-pipeline-and-new-technology-development/)).

### 2.2 Competitors and adjacent products (agent 2)

- **Nobody forecasts citrus colour over time.** FreshCloud Storage is an ethylene/CO₂ sensor product for apples and pears ([AgroFresh](https://www.agrofresh.com/solutions/freshcloud/storage/)); Strella is ethylene-based and apple-centric but owns the "sequence" language and rewrites pallet expiry dates in the WMS ([DC Velocity](https://www.dcvelocity.com/articles/59259-a-fresh-approach-to-improving-our-food-chain)); OneThird is NIR and does not cover citrus; Clarifresh has no shelf-life or ripeness prediction anywhere on its integration page ([Clarifresh](https://clarifresh.com/erp-integrations/)).
- **Clarifresh is the incumbent capture tool to learn from**: barcode scan that auto-fills lot metadata from the ERP, multiple photos per defect, mandatory-attribute validation, six languages including Spanish, and results pushed back to the ERP. Its SunFresh case study reports the adoption lesson: reports "closely mirrored previous manual workflows" ([case study](https://clarifresh.com/case-studies/sunfresh-international-revolutionized-quality-control/)).
- **Famous integration reality.** Famous sells Integration Services (EDI), Apps (a QC tablet app that can "control product availability"), and Famous BI with scheduled delivery and conditional alerts ([Famous BI](https://famoussoftware.com/products/business-intelligence)). No public API docs; a vendor blog claims the public API is narrow. CSV plus scheduled BI exports is the realistic path.
- **Field-capture patterns**: encrypted on-device queue, capture-time timestamps (not sync time), automatic background sync, no silent drops ([GoAudits](https://goaudits.com/blog/offline-inspections/)).
- **Phone colour science**: Bernardi et al. 2026 (Sensors) used an 8×8 palette with four ArUco corners, homography and CDF histogram matching; class accuracy rose from 55.6 % to 100 %, but a glossy card fell to 19–25 % and intermediate classes showed a +1 bias ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13364227/)). Cubero et al. 2018 found white-balance mode × device × environment interactions significant, best R² 0.88 indoors ([IVIA](https://redivia.gva.es/handle/20.500.11939/6203)).
- **Shelf-life products report accuracy in days** (RMSE ≤ 1.3 days in dynamic-shelf-life systems, [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12269072/)); GMs read "days left ± 2" faster than a CCI curve.

### 2.3 Pilot structure, funding, workforce, science (agent 3)

- **Charge for the pilot.** Structured paid pilots convert 40–60 % versus under 10 % for free trials ([Monetizely](https://www.getmonetizely.com/articles/how-to-structure-enterprise-pilot-program-pricing-effective-proof-of-concept-strategies)). A 2026 specialty-crop example: Innov8.ag's $10k, 12-month pilot refunded if the grower cannot identify ≥ $20k savings ([Innov8.ag](https://www.innov8.ag/companynews/harvestreplay-paid-pilot/)). Public packhouse-software price points are lower than the $15–25k per plant assumption (Farmsoft ~$6,200 per year for 10 users), so the premium has to be justified in cartons saved.
- **Who pays in a co-op.** Software is a house operating cost recovered inside the per-carton packing charge; the GM and board approve it, not the grower pool. At ~$10 per carton packing cost, $20k per plant on ~1 M cartons is about 2 cents per carton (inference from Sunkist bylaws and Limoneira filings).
- **Funding calendar.** CDFA Specialty Crop Block Grant 2027 concept proposals close **21 September 2026, 9 a.m. PT**, $100–600k, ~$28 M pool, needs a UC or nonprofit-style applicant ([grants.ca.gov](https://www.grants.ca.gov/grants/2027-specialty-crop-block-grant-program/)). Citrus Research Board pre-proposals run about March 2027; category 5400 "Production and Post-Harvest Technology" prioritises "a clear path to commercialization" ([CRB RFP](https://citrus-research-board-static.sfo2.digitaloceanspaces.com/downloads/RFP_Guidelines_26-27_020626.pdf)). USDA NIFA SBIR FY2026 is delayed; watch Grants.gov. Western SARE Professional + Producer likely reopens ~November 2026, $85k, needs an extension or university PI.
- **Validation partners.** UC Lindcove REC has a donated commercial packline with a Compac grader and a Fruit Quality Evaluation Laboratory, bookable by form ([UC ANR](https://ucanr.edu/rec/lindcove-research-and-extension-center/request-forms-packline-laboratory-and-seeds)). UC Davis Postharvest Center offers consultations. Budget $5–15k for a phone-versus-colorimeter benchmark on ~300 fruit (inference).
- **Science that changes the model.** Degreening is bell-shaped in temperature: fastest at ~15 °C, slower at 5 °C, halted at 25 °C, ethylene-independent ([J Exp Bot 2020](https://academic.oup.com/jxb/article/71/16/4778/5831195)). Storage life is 4–6 months at 10 °C but 1–2 months at 13 °C, with high rot after 3 months at 13 °C. Colour is a late indicator past ~120 days; firmness, weight loss and ethanol track long-stored Eureka better ([Food Control 2024](https://www.sciencedirect.com/science/article/abs/pii/S0956713524004766)).
- **Sample size.** USDA AMS lemon inspection requires at least 25 contiguous fruit per sample ([AMS](https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions[1].pdf)). Ten fruit detect a 5 % decay lot about 40 % of the time; 25 fruit about 72 %.
- **Workforce.** 57 % of crop workers are Spanish-primary and 27 % speak no English, but 96 % have a phone with internet and only 18 % a tablet ([NAWS Report 17](https://www.dol.gov/sites/dolgov/files/ETA/naws/pdfs/NAWS%20Research%20Report%2017.pdf)). Ganaz found workers wanted "text notifications, no apps, and robust customer support in Spanish".
- **Second customer.** Limoneira Santa Paula rejoined Sunkist as a licensed packer on 1 November 2025 and packs ~4.7 M cartons per year; the natural independent site.

---

## 3. Ranked improvements

Effort: S = under a day, M = a few days, L = a sprint or more.

### A. Before the mid-October go-live

| # | Improvement | Why now | Effort |
|---|---|---|---|
| A1 | **One-tap Accept per recommendation, "Accept all remaining", phone cards, fetch save** (P2). | The pilot scorecard targets 95 % of recommendations with a recorded decision; the demo plan sits at 6 %. Every Monday costs the GM 16 open/pick/save/reload cycles. | M |
| A2 | **Capture: visible step errors, hidden file input, help behind a toggle, station remembered per device** (B4, P3). | The foreman path is the model's only input; a silent refusal to submit loses a sample. | S |
| A3 | **Spanish as default UI for foreman screens, English toggle**. | 57 % Spanish-primary workforce; Clarifresh already ships Spanish. Django i18n plus ~120 strings. | M |
| A4 | **Log capture time open→submit per sample** and show it on Readiness. | Scorecard target is 90 s median; nothing measures it today. | S |
| A5 | **Configurable fruit count (default 25) and USDA-style "double the sample if a tolerance is exceeded" prompt.** | Ten fruit is below the regulatory floor and misses a 5 % decay lot 60 % of the time. Keep 10 as a fallback where 25 is impractical, but record which. | M |
| A6 | **Room setpoint on `Room`, temperature-band degreening rate, and a separate decay clock** (weeks at ≥ 13 °C). | Linear CCI with a fixed buffer is wrong across rooms; sour rot on long-stored fruit is documented in California. Show the clock on the board next to colour. | M–L |
| A7 | **Board and calibration**: matte board stock, white-balance mode and device model stored per photo, reject frames without all four markers, CDF histogram matching as a scoring option. | Glossy cards dropped accuracy to 19–25 % in the 2026 study; WB mode interactions were significant in 2018. | M |
| A8 | **Market-regime flag on plan publish** (tight / normal / oversupplied) recorded with each decision. | The August 2026 flip shows weekly market context changes the right defer/pack call; without it the decision log is uninterpretable later. | S |
| A9 | **Lot detail fixes** (B2, B6, P4): overdue tone, whole bins, key/value metadata, non-zero defect counts, formatted room intervals. | Cheap, and the lot page is what the GM opens to check a recommendation. | S |
| A10 | **Register-station CTA on Readiness; QC screen to record final packout quality**. | Zero calibration records and zero direct labels are the two readiness gaps; both currently require Admin or a CSV. | S / M |

### B. During the pilot (weeks 3–10)

| # | Improvement | Why | Effort |
|---|---|---|---|
| B1 | **Lot QR/barcode scan** that fills lot, grower, room and receipt date. | Wrong lot ID is the largest foreman error source; Clarifresh treats scan as table stakes. | M |
| B2 | **Offline queue** with capture-time timestamps and automatic background sync. | Cold rooms have poor signal; Phase 1 item 5 in the action plan. | L |
| B3 | **Headline shift to "pack sequence" and "days remaining ± band"**; CCI moves to technical details. | Strella owns the sequence framing; GMs read days faster than an index. Gives a measurable accuracy KPI. | S–M |
| B4 | **Conditional alerts** ("lot X crosses threshold in 5 days") by email/text in addition to the Monday report. | Famous BI already delivers scheduled reports; ours must add forecast to be read. | M |
| B5 | **Firmness or weight-loss spot check for lots stored > 120 days.** | Colour is a late indicator on long-stored Eureka. | S (fields exist) |
| B6 | **Tenant name from settings**; drop hardcoded "Saticoy". | Needed before Limoneira or any second site. | S |

### C. Commercial and validation actions (no code)

| # | Action | Deadline / owner |
|---|---|---|
| C1 | Convert the pilot MOU to a **paid, refundable-on-miss** agreement (~$8–12k per plant, refunded if the GM cannot attribute ≥ 2× in avoided regrades or shrink). Price per plant with a usage floor; pitch in cents per carton. | Before go-live |
| C2 | **CDFA SCBGP 2027 concept proposal**, with a UC partner as applicant. | **21 Sep 2026, 9 a.m. PT** |
| C3 | Email CRB research staff to pre-position a **March 2027 category-5400 pre-proposal** with a UC co-PI. | October 2026 |
| C4 | Book **UC Lindcove packline / Fruit Quality Lab** for a phone-vs-Compac/colorimeter benchmark on ~300 fruit across three colour classes. | Before evaluation sampling |
| C5 | Pull **Saticoy's products (juice) return per carton from Famous**; it is not public and it is the single most important ROI input. Use $18.50–$23 fresh FOB as the 2025–26 range. | Phase 0.5 |
| C6 | Brief **CFO Laura Troost** as executive sponsor using the decision record as the "trust-based systems" story; brief the plant manager using their own job description ("quality, size, and color"). | Meeting prep |
| C7 | Re-read **Limoneira Q3 FY2026 results (9 Sep 2026)**; if pricing collapsed after August, pivot the ROI narrative to "protecting fresh share in an oversupplied market". | 9 Sep 2026 |
| C8 | Open the **Limoneira Santa Paula** conversation as the second, independent site. | Q4 2026 |
| C9 | Ask Sunkist/Sienz whether **Sunsortai per-run colour grades** can be exported per lot; that is packout truth for the model. | House meeting |

---

## 4. Caveats on the research

- Several trade sources (The Packer, FreshPlaza, Capterra, Clarifresh pricing) blocked automated reading; facts from them come from search snippets and are marked. A manual read of The Packer and FreshPlaza 2026 lemon coverage is worth an hour before the pitch.
- Limoneira's Q4 FY2025 release contained internally inconsistent full-year figures; the numbers above are the ones that reconcile with the 10-K.
- Vendor descriptions establish advertised capabilities, not verified performance.
- The full agent reports, with every citation, are in `docs/research-appendix-2026-09-07.md`.
