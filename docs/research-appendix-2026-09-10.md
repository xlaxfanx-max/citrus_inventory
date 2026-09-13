# Research appendix — 10 September 2026

Full reports from the three outside-research agents and the independent code review that fed `docs/product-review-and-research-2026-09-10.md`. Agent reports are reproduced as returned, with HTML entities decoded; nothing was added or removed except headings. Research date: 10 September 2026.

---

# Agent 1 — Lemon storage physiology and postharvest treatments: what an inventory system must record and when it should alarm

Scope note: 32 distinct web searches plus direct reads of UC Davis, Cargo Handbook, USDA lemon grade standards and inspection instructions, CRI South Africa packhouse chapter, EFSA, USDA GAIN, Saticoy Lemon, and ~20 journal abstracts. Several publisher pages (ScienceDirect, ResearchGate, APS full text) blocked direct fetching; abstracts were obtained via Europe PMC and Crossref instead.

## 1. Decay

**Pathogens and behaviour in storage.** Green mold (*Penicillium digitatum*) is the dominant wound pathogen; blue mold (*P. italicum*) grows faster below 10 C and can be the more common of the two in cold rooms ([Lucid citrus storage moulds](https://apps.lucidcentral.org/pppw_v10/text/web_full/entities/citrus_storage_moulds_197.htm)). Sour rot (*Geotrichum citri-aurantii*) is the long-storage lemon problem: it is not controlled by imazalil, TBZ, pyrimethanil or fludioxonil ([Redalyc review](https://www.redalyc.org/journal/813/81376287002/html/)), and a 2020-23 California packinghouse survey was triggered by "high levels of sour rot on propiconazole-treated lemon fruit that was stored for extended times" ([Nguyen, Förster, Adaskaveg 2025, Plant Disease 109:825](https://pubmed.ncbi.nlm.nih.gov/39441531/)). That paper also showed *G. candidum* behaves as a secondary pathogen favoured by senescent fruit (lemon sour rot 4.7% to 68.2% when tissue was chemically senesced): old lots rot from sour rot even with good sanitation. *Alternaria citri* enters through senescing buttons; *Phytophthora* brown rot is a pre-harvest infection expressed in storage ([Adaskaveg, Hao, Förster 2015](https://apsjournals.apsnet.org/doi/10.1094/PDIS-01-15-0040-RE)); Botrytis is a coastal wet-season issue ([UC IPM](https://ipm.ucanr.edu/agriculture/citrus/botrytis-diseases-and-disorders/)).

**Incidence vs time and temperature.** No published lot-level loss curve for commercial California lemon storage was found (gap). The best duration data: at 13 C, storage "for 3 months and longer resulted in a high incidence of rot", while below 10 C chilling injury appeared; intermittent warming allowed 6+ months ([Cohen 1988, HortScience 23:400](https://doi.org/10.21273/hortsci.23.2.400)). Kütdiken lemons kept 8-9 months at 10 C / 85-90% RH ([Pekmezci 1983](https://ishs.org/ishs-article/138_23/)). Inoculated-fruit data show how steep the untreated curve is: untreated lemons 94.4% green mold vs 15.1% (imazalil in wax) vs 1.3% (heated aqueous imazalil) at equal residue ([Smilanick et al. 1997, Plant Disease 81:1299](https://apsjournals.apsnet.org/doi/pdf/10.1094/PDIS.1997.81.11.1299)); sour rot 83.8% untreated vs 0-1.2% with in-line propiconazole drench applied within 16 h of inoculation ([McKay, Förster, Adaskaveg 2012](https://apsjournals.apsnet.org/doi/10.1094/PDIS-06-11-0525)). Timing matters: CRI advises treating within 24 h of picking when average temperature is 20 C or more, 48-72 h in cool weather, and notes one sound fruit carries ~50,000 spores into a dump tank ([Lesar 2003, CRI Packhouse Precautions](https://www.citrusres.com/wp-content/uploads/2021/08/Ch-9-2-Packhouse-precautions-July-2003.pdf)).

**Thresholds packers actually use.** The regulatory anchor is the USDA lemon grade: U.S. No. 1 and No. 2 allow not more than 1% decay at shipping point and 3% en route/destination, inside a 10% total-defect / 5% serious-damage tolerance; decay is "always serious damage when seen in any amount", and contact spot scores the same ([USDA Lemon Standard](https://www.ams.usda.gov/sites/default/files/media/Lemon_Standard%5B1%5D.pdf); [Lemons Inspection Instructions](https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions%5B1%5D.pdf)). Disagreement flag: one search summary reported "5% decay at shipping point / 7% at destination"; in the instructions the 5% figure is the combined sublimit for decay + contact spot + internal Alternaria + internal decline in No. 2, not a decay-only tolerance. A "5% dump" rule is industry folklore rather than published; treat it as a house parameter.

- **Record:** decay count by type (green/blue, sour, Alternaria/button, brown rot) per 25-fruit sample and per pack-out; harvest-to-first-treatment hours; treatment chemistry of the lot; contact-spot count.
- **Alarm:** any sour rot on a propiconazole-treated lot; sample decay >1% (lot can no longer pack U.S. No. 1 without regrade); >3% (destination-failure risk, pack now or regrade); harvest-to-treatment >24 h.

## 2. Chilling injury

**Thresholds.** Lemons are second only to grapefruit in chilling susceptibility. Symptoms: rind pitting, membranous stain, red blotch, oil-gland collapse; moderate-severe CI is "usually followed by decay" ([UC Davis Produce Facts: Lemon](https://postharvest.ucdavis.edu/produce-facts-sheets/lemon)). Freezing point -1.4 C; CI "occurs below 5 C or during long term storage already below 10 C"; 3-4 weeks at 3-5 C "is usually tolerated" ([Cargo Handbook](https://www.cargohandbook.com/Lemons)). Cohen (1988) saw membranosis, pitting and juice changes below 10 C over months. Membranous stain is scoreable "in any amount" in U.S. No. 1.

**Why 10-13 C.** It is a window between CI (below) and decay/senescence (above): 13 C for 3+ months gave high rot (Cohen 1988). Disagreement on the optimum: UC Davis says 12-14 C (54-57 F) for up to 6 months; Cargo Handbook says 10-11 C for yellow, 12-14 C for green fruit; Saticoy publishes 50-52 F (10-11 C) at 90-95% RH ([Saticoy Lemon Operations](https://saticoylemon.com/operations/)); Pekmezci found 10 C best. The maturity-dependent split (greener = warmer) is the reconciling reading.

**Conditioning / intermittent warming.** 7 days at 13 C after every 21 days at 2 C eliminated CI in Eureka and Villa franca and allowed 6+ months (commercial in Israel; Cohen 1988). Pre-conditioning at 10-27 C before 1 C storage reduces CI ([US patent 4,921,715](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4921715)). Saticoy's 40-45 F pre-coolers before loading are a deliberate short cold exposure consistent with the 3-4-week tolerance.

**Peteca (distinct from classic CI).** Oil-gland collapse and albedo lesions; first symptoms can appear 3-5 days after harvest, early-season fruit most susceptible ([Cronje 2015, Acta Hort](https://www.1stfruits.co.za/wp/wp-content/uploads/2016/02/Cronje_Etyl-Lemon-_Peteca_Acta-Hort_2015.pdf)). Undurraga et al. 2009 (Eureka, Chile): high incidence after 15 days at 11 C and constant to day 35; incipient at 7 C; appeared at 3 C only after 35 days; yellow fruit more susceptible than silver; 100% RH increases peteca ([Sci. Hortic.](https://www.sciencedirect.com/science/article/abs/pii/S0304423809001721)). Disagreement: Wild 1991 (Meyer) found storage at 10-25 C "had no effect", but wax + brushing aggravated it and polyethylene waxes induced more peteca than carnauba ([HortScience 26:287](https://doi.org/10.21273/hortsci.26.3.287)).

- **Record:** room set-point and logged temperature (min, and hours below 10 C and below 5 C cumulative per lot); colour class at entry; wax formulation; pitting/membranous-stain/peteca counts on each sample.
- **Alarm:** any reading below 5 C; cumulative >21 days below 10 C without a warming period; sustained >14 C; membranous stain or peteca on >0 fruit in a sample of a yellow lot (pack now).

## 3. Humidity and weight loss

**Targets.** UC Davis and Saticoy: 90-95% RH; Cargo Handbook: 90%; Pekmezci: 85-90%; Florida guide: 90-95% for pallet bins, 85-90% for fibreboard cartons ([UF/IFAS CH081](https://ask.ifas.ufl.edu/publication/CH081)). Upper bound: 100% RH raises peteca, and condensation feeds mold.

**Rates.** Published lemon weight-loss data are sparse. Eureka in air at 8 C / 85-90% RH lost 3.52% in 20 days (about 1.2%/week), 2.14% under CA ([Ma et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6601498/)). McCornack (1975) found RH mattered more than temperature and that ambient-RH fruit "became soft and developed peel injury associated with dehydration" ([FSHS](https://journals.flvc.org/fshs/article/download/98129/94128)). Ben-Yehoshua showed lemon softening is "highly correlated with declining water potential" and that film-sealing at 13 C held Eureka 6 months ([Ben-Yehoshua et al. 1983](https://pubmed.ncbi.nlm.nih.gov/16663193/); [Cohen et al. 1990](https://doi.org/10.21273/jashs.115.2.251)). The commonly quoted "5% weight loss = shrivel/unsaleable" and "reached in 10-12 weeks at 85% RH / 11 C" appear only in secondary/engineering sources ([Ingener](https://ingener.by/refrigeration-systems/food-processing-refrigeration/fruit-processing/citrus-processing/lemon-lime-storage/)); treat 5% as a rule of thumb. Storage wax exists precisely to cut this loss (Saticoy applies storage wax after washing "to prevent shrinkage", pack wax later).

- **Record:** room RH (logged), wax type/date, and a tagged-fruit or tare-weighed reference bin per lot to compute cumulative % weight loss.
- **Alarm:** RH below 85% or above 97% for more than a shift; cumulative weight loss 3% (warning) and 5% (pack or downgrade); soft/wilted count on the sample.

## 4. Ethylene

Lemons produce very little ethylene but are moderately sensitive; degreening at 1-10 ppm for 1-3 days at 20-25 C "may accelerate deterioration rate and decay incidence" (UC Davis). Above ~20 ppm causes senescence and button loss ([Degreening of Citrus Fruit review](http://www.globalsciencebooks.info/Online/GSBOnline/images/0812/TFSB_2(SI1)/TFSB_2(SI1)71-76o.pdf)). Long-exposure trials at 0.001 to 1 µL/L showed higher ethylene increased calyx senescence, weight loss, softening and respiration; the authors recommend storage rooms at 0.1 µL/L or lower ([Alhassan et al. 2019, Foods 8:19](https://pmc.ncbi.nlm.nih.gov/articles/PMC6351945/)). Senescent buttons are the entry for *Alternaria citri*; pre-harvest GA3 or post-harvest 2,4-D delay button senescence. This is why storage rooms must not share air with degreening rooms (typically 3-5 ppm at 28-29 C, 90-95% RH).

Disagreement flag: Cronje (2015) reported 3 ppm ethylene gave 0% peteca vs 18% in air and 41% in a closed container, a real, cultivar/season-specific benefit that conflicts with the general "exclude ethylene" rule. Do not generalise it. Also note a 2020 paper showing low temperature drives natural lemon degreening independently of ethylene ([Mitalo et al.](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7410192/)).

- **Record:** room ethylene (ppm) if sensed; room-to-degreening adjacency/air-sharing flag; 2,4-D/GA3 treatment date; % buttons missing or browned in each sample.
- **Alarm:** room ethylene >0.1 ppm (warning), >1 ppm (critical); button loss rising between samples; any lot placed in a room adjacent to an active degreening room.

## 5. Postharvest treatments, resistance, residues

**Fungicides and rates.** Imazalil 1,000 ppm aqueous or 2,000 ppm in water-wax; TBZ same; SOPP 2% at pH 11.5-12 with contact under 2 min; fludioxonil + azoxystrobin 600 + 600 ppm; pyrimethanil as a rotation partner (UF/IFAS CH081). CRI: imazalil 500 ppm dip, 2,4-D 250 ppm, hot water 3 min at 47 C, and lemons must "wilt for 12 to 24 hours" before SOPP or red staining results (Lesar 2003). Heated aqueous imazalil (38-50 C) beats wax application for both control and residue loading (Smilanick 1997); 2% sodium bicarbonate buffering raises imazalil loading ([Smilanick et al. 2005](https://my.ucanr.edu/sites/Postharvest_Technology_Center_/files/232051.pdf)). Sour rot: propiconazole 64-512 µg/mL, best within 8-24 h on lemon (McKay 2012); natamycin 1,000 µg/mL cut lemon green mold 88.5% and natamycin mixes in storage coating gave >85% control of green mold and sour rot; no natamycin resistance ever documented ([Chen, Förster, Adaskaveg 2021](https://pubmed.ncbi.nlm.nih.gov/33320038/)). Brown rot: potassium phosphite 1,500 µg/mL within 18 h gave >96% reduction; phosphite-resistant Phytophthora now exist ([Plant Disease 2020](https://apsjournals.apsnet.org/doi/10.1094/PDIS-06-20-1414-RE)).

**Resistance.** California packinghouse *P. digitatum* triple-resistant to imazalil/TBZ/SOPP rose from 43% (1988) to 74-77% (1990-94); none found in groves ([Holmes & Eckert 1999](https://pubmed.ncbi.nlm.nih.gov/18944698/)). Resistance risk ranked natamycin ~zero, fludioxonil low, pyrimethanil high ([IR-4 natamycin brief](https://ir4.cals.ncsu.edu/fooduse/PerfData/4782.pdf)). Sour rot: moderately and highly propiconazole-resistant *G. citri-aurantii* in California with no fitness cost ([Nguyen 2025](https://pubmed.ncbi.nlm.nih.gov/39441531/); [CYP51A mutations 2025](https://pubmed.ncbi.nlm.nih.gov/40324180/)).

**Growth regulators and coatings.** 2,4-D sodium salt 500 ppm dip retards calyx abscission and Alternaria ([Ma et al. 2014](https://academic.oup.com/jxb/article/65/1/61/427883)) but is prohibited in many export markets. GA3 pre-harvest 10-20 g a.i./acre Oct-Dec delays rind senescence ([UC IPM](https://ipm.ucanr.edu/agriculture/citrus/delaying-fruit-senescence-with-gibberellic-acid-ga3/)). Storage coating vs pack wax: staged aqueous fungicide plus fungicide in the storage coating held decay to ≤10.7% (Chen 2021); polyethylene-type waxes raised peteca vs carnauba on Meyer (Wild 1991). High-temperature curing (30-37 C, 90-98% RH, 65-72 h) controls green/blue mold without fungicide but is commercially impractical ([Plaza et al. 2004](https://pubmed.ncbi.nlm.nih.gov/15307674/)); classic lemon "curing" is 58-60 F, 85-90% RH ([FAO](https://www.fao.org/4/x5014e/X5014e0b.htm)).

**MRLs.** EU: imazalil lemons currently 5 mg/kg, proposed 7 ([EFSA 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12368512/)); TBZ 7, pyrimethanil 4-5. Japan classes postharvest fungicides as food additives with mandatory carton and retail labelling; permitted on citrus: imazalil (5 ppm), OPP/SOPP (10), TBZ (10), fludioxonil, diphenyl; pyrimethanil was not permitted as of 2012 ([USDA GAIN 2012](https://apps.fas.usda.gov/newgainapi/api/report/downloadreportbyfilename?filename=Guide+to+Japanese+Labeling+Requirements+for+Post+Harvest+Fungicide_Tokyo_Japan_8-17-2012.pdf)); verify in the [Japan MRL database](https://jpn-pesticides-database.go.jp/prdb/en/index_en.pl). Korea: Positive List System with 0.01 ppm default ([USDA GAIN 2018](https://www.fas.usda.gov/data/south-korea-implementation-positive-list-system-maximum-residue-limits)). Sour rot is uncontrolled by the EU/Japan-friendly benzimidazole/imidazole set, so export lots carry higher sour-rot exposure in long storage.

- **Record:** per lot: each treatment (a.i., ppm, solution temperature, aqueous vs coating, date/time, tank age), 2,4-D yes/no, storage-coating type, intended market(s).
- **Alarm:** treatment applied >24 h after harvest; lot tagged for Japan/Korea/EU carrying a non-permitted a.i.; green mold appearing on imazalil-treated lots or sour rot on propiconazole lots (rotate chemistry, shorten hold); lot age beyond 12 weeks without a natamycin/propiconazole sour-rot treatment.

## 6. CA, 1-MCP, ozone, UV-C, hot water

CA: 5-10% O2 and 0-10% CO2 "can delay senescence including loss of green color"; 10-15% CO2 is fungistatic but risks off-flavour (UC Davis). Ma et al. 2019 found 6% O2 + 8% CO2 best over 20 days at 8 C. No evidence of commercial CA for lemons in California; CA slows colouring, the opposite of a Ventura house's goal. 1-MCP: in Shamouti oranges it blocked degreening but increased chilling injury, decay and off-flavours (Porat et al. 1999); no lemon-specific commercial use found. Ozone suppresses sporulation and delays decay but "slowed down the development of the colouring process" ([Palou/Smilanick](https://www.researchgate.net/publication/251329175_Use_of_ozone_in_storage_and_packing_facilities)). UV-C is mainly wash-water disinfection. Hot-water dips gave 0-1% decay on Italian lemons but throughput is the obstacle; California houses instead heat fungicide solutions (48-54 C per [UC IPM brown rot](http://ipm.ucanr.edu/PMG/r107100711.html)). Intermittent warming and film-sealing are proven for 6 months but neither is reported in Californian use.

- **Record:** room atmosphere or ozone dosing if used (they change colour-rate); flag lots in such rooms for a separate colour-model term.
- **Alarm:** CO2 >10% or O2 <5% in any CA/sealed room; ozone use on lots that need to colour on schedule.

## 7. Best-practice reference documents

- [UC Davis Postharvest Center, Lemon Produce Facts (Arpaia & Kader)](https://postharvest.ucdavis.edu/produce-facts-sheets/lemon)
- [USDA Agriculture Handbook 66 (2016 PDF)](https://www.ars.usda.gov/is/np/CommercialStorage/CommercialStorage.pdf)
- [USDA U.S. Standards for Grades of Lemons](https://www.ams.usda.gov/sites/default/files/media/Lemon_Standard%5B1%5D.pdf) and [Inspection Instructions](https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions%5B1%5D.pdf)
- [CRI South Africa, Lesar 2003, Packhouse Precautions](https://www.citrusres.com/wp-content/uploads/2021/08/Ch-9-2-Packhouse-precautions-July-2003.pdf); [CRI peteca research summary 2015](https://www.citrusresourcewarehouse.org.za/home/document-home/news-articles/south-african-fruit-journal-safj/sa-fruit-journal-2010-2012/safj-2015/april-may-2015/2704-sa-fruit-journal-april-may-2015-cri-progress-in-research-on-control-of-peteca-spot-of-lemon-fruit-could-ethylene-metabolism-influence-susceptibility/file)
- [UF/IFAS 2025-26 Decay Control of Florida Fresh Citrus](https://ask.ifas.ufl.edu/publication/CH081)
- [UC IPM Citrus guidelines](https://ipm.ucanr.edu/agriculture/citrus/)
- [Cargo Handbook, Lemons](https://www.cargohandbook.com/Lemons)
- Industry statements: [Saticoy Lemon Operations](https://saticoylemon.com/operations/); [Limoneira 10-K](https://www.sec.gov/Archives/edgar/data/1342423/000134242325000039/lmnr-20251031.htm) ("storage life... one to 18 weeks depending upon maturity"); [Sunkist Lemons](https://sunkist.com/en-us/our-citrus/lemons)
- Argentine/Spanish: [Olmedo 2021 brown rot](https://pubmed.ncbi.nlm.nih.gov/33275277/); [Palou/Plaza curing](https://pubmed.ncbi.nlm.nih.gov/15307674/)

- **Record:** which reference set-point (10-11 C yellow, 12-14 C green) each room is run to, so forecasts and alarms use the right band.
- **Alarm:** room set-point outside the 10-14 C band for its colour class.

## Consolidated minimum data model and alarm ladder

Per room (logged): temperature (min/mean), RH, ethylene ppm, CO2/O2 or ozone if applicable, adjacency to degreening. Per lot: harvest date/time, treatment events (a.i., ppm, temperature, method, time since harvest), storage-coating type, colour class at entry, market tags, reference weight. Per sample (25 fruit): decay by type, contact spots, pitting/membranous stain/peteca, button loss, soft/wilted count, cumulative weight loss.

Alarm ladder (severity ascending): RH <85% or >97%; ethylene >0.1 ppm; treatment >24 h after harvest; weight loss 3%; any reading <5 C or >14 C; cumulative 21 days <10 C; weight loss 5%; decay >1% or any sour rot / membranous stain; decay >3% or contact spots present.

Key disagreements to encode as house-configurable: optimum temperature (10-11 vs 12-14 C, resolved by colour class); peteca temperature dependence (Undurraga vs Wild); ethylene as harmful (Alhassan, UC Davis) vs protective against peteca (Cronje); 5% weight-loss and 5% decay "rules" (secondary sources only) vs the published 1%/3% USDA decay tolerances.


---

# Agent 2 — Citrus (lemon) packinghouse inventory management: processes and standards

Scope note: about 50 searches/fetches. Several primary PDFs (USDA lemon standard and inspection instructions, CRI toolkit, Sunkist sell sheet) were read directly; a few sources (NSW DPI lemon manual, Argentine protocol PDF, PrimusGFS module, Zespri SLA) were blocked or unreadable and are flagged.

## 1. Storage rotation: FIFO vs FEFO vs quality-based

No citrus extension body publishes a formal "FEFO" rule for lemon storage. What exists is a consistent *quality-based* principle: storability is set by colour stage at harvest, and rotation should follow it.

- UC Davis Postharvest: "Lemons picked at the dark-green stage have the longest postharvest life while those picked fully-yellow must be marketed more rapidly." Optimum 12–14 °C, 90–95 % RH, storage "up to 6 months." ([UC Davis lemon fact sheet](https://postharvest.ucdavis.edu/produce-facts-sheets/lemon))
- Cargo Handbook: yellow lemons 10–11 °C, green lemons 12–14 °C; 3–6 months; dark-green fruit "retains quality longer than yellow-picked." ([Cargo Handbook](https://www.cargohandbook.com/Lemons))
- Peer-reviewed (Eureka, 10 °C): fruit harvested green stores ~90 days; fruit harvested yellow is suitable for ~30 days; weight loss, TSS and TA rise with storage time. ([Sci. Hortic. 2019](https://www.sciencedirect.com/science/article/abs/pii/S0304423819300718))
- Citrus Australia / NSW DPI lemon manual notes juice content rises up to 16 % and acid up to 24 % during storage (water moves from peel to pulp), so stored fruit is *not* simply degrading on every axis. ([Citrus Australia](https://www.citrusaustralia.com.au/growers-industry/post-harvest/); [NSW DPI manual ch. 16](https://www.dpi.nsw.gov.au/__data/assets/pdf_file/0008/137753/16-lemon-postharvest.pdf), PDF blocked)
- Argentina's official fresh-lemon quality protocol caps prolonged storage at **6 months** at 10–14 °C / 85–90 % RH, and requires packing within 72 h of harvest. ([CDA](https://www.cda.org.ar/detalle_noticia.php?id=30279))
- Citrus Research International's packhouse handbook (South Africa) Toolkit 5.3 lists what an inventory control system must manage: "inventory levels, prioritising high value produce, stock turn, optimal throughput, tracking and control, e.g. accurate management and movement of de-greening bins, less reliance on manual data entry, accurate inventory naming and labelling," plus real-time KPI scoreboards. No rotation rule. ([CRI Toolkit 5.3](http://www.citrusresourcewarehouse.org.za/home/document-home/best-practice-handbook/citrus-packhouse-best-practice-handbook/workflow-5-logistics/toolkit-5-3-warehouse-and-stock-management))
- Analogue: Stemilt (apples) uses harvest-time quality tests to "create a schedule to open CA rooms and begin packing": release order is quality-driven, not date-driven. ([Stemilt](https://www.stemilt.com/storing-apples-pears/))

Gap: Limoneira's 10-K says lemon storage life "generally ranges from one to 18 weeks" versus UC Davis "up to 6 months" for green fruit. Nobody publishes how houses pick the next lot when colour, age, decay and customer spec conflict; that logic is house tacit knowledge.

**Implies for the app:** the priority engine should be quality-based with age as a tie-breaker (colour stage at receipt → expected remaining life → observed decay/condition → age), and it should model that green fruit gains value in storage for weeks before it starts losing it.

## 2. Room management

- **Organisation.** Saticoy's own page: fruit is "grouped by size and grade and sent to storage," held at 50–52 °F / 90–95 % RH with high-volume air to colour up, then re-washed, pack-waxed, re-run through optical grading and hand inspection before packing; pre-coolers 40–45 °F. ([Saticoy operations](https://saticoylemon.com/operations/)) Bee Sweet: incoming bins go "directly into temporary storage" for degreening before the line. ([DC Velocity](https://www.dcvelocity.com/articles/29455-bee-sweet-citrus-juices-up-its-packing-operations))
- **Stacking/airflow.** Bins are stacked several high by forklift; degreening rooms duct air through the channels between bin stacks. Blocked aisles and pushed-against-wall pallets are a documented decay cause. ([UF/IFAS HS195](https://ask.ifas.ufl.edu/publication/HS195); [PEI cold chain guide](https://peitrade.com/citrus-export-cold-chain-guide/)) This is the structural reason true FEFO is hard: the oldest bin is often at the back/bottom of a stack.
- **Temperature bands.** UC Davis 12–14 °C; Saticoy 10–11 °C; Cargo Handbook 10–11 °C yellow / 12–14 °C green; Sunkist foodservice sheet 41–42 °F (retail/short-term). Chilling injury appears below ~10 °C on prolonged storage, though "3 to 4 weeks at 3–5 °C… is usually tolerated."
- **Logging/alarms.** GFSI schemes (PrimusGFS, SQF 9, BRCGS 9) require documented temperature control with critical limits, calibration schedules and trendable records; FDA expects logging frequent enough to catch excursions "in a timely manner," commonly read as hourly or better. Vendor guidance: warning alarm at ~80 % of allowable deviation; 72-hour multi-point mapping before use. ([Central Valley Cold Storage](https://centralvalleycoldstorage.com/temperature-monitoring-fsma-compliance-cold-storage/); [7Seas](https://www.7seasmatrix.com/temperature-controlled-warehousing-guide-best-practices-and-challenges/)) Auditors compare room thermometers against the product being stored and require separate chambers for products with different optimum temperatures.
- **Inspection frequency.** No citrus source states a walk-through interval. CRI's decay chapter gives process rules: treat fruit with fungicide within 24 h of picking in hot weather (48–72 h if ≤15 °C); lemons must wilt 12–24 h before SOPP; never repack decayed fruit without full sanitation; local-market fruit held in a separate building; formaldehyde fumigation of cold rooms. ([CRI Ch. 9](https://www.citrusres.com/wp-content/uploads/2021/08/Ch-9-2-Packhouse-precautions-July-2003.pdf))
- **Regrading.** Standard practice is a second optical/hand grade at pack-out (Saticoy), so storage inventory is "pre-grade" and the pack grade is only known when the lot runs.

**Implies for the app:** room is a first-class object with setpoint band, logger feed and alarm thresholds; bin position/stack depth should be captured so the planner can flag "oldest lot is buried"; expect a pre-grade vs final-grade delta and record it per lot.

## 3. Grade standards: "ready to pack" and "no longer saleable"

**USDA lemon standard (current, effective 13 May 2026 after the seedless amendment).** ([AMS standard PDF](https://www.ams.usda.gov/sites/default/files/media/Lemon_Standard%5B1%5D.pdf); [AMS notice](https://www.ams.usda.gov/content/usda-proposes-revisions-grade-standards-lemons))
- Grades: U.S. No. 1, U.S. Export No. 1, U.S. Combination (≥40 % No. 1), U.S. No. 2. No No. 3.
- Colour: "well colored" = yellow with not more than a trace of green; "fairly well colored" (No. 1 and No. 2) = yellow area exceeds green; "moderately well colored" (Export No. 1) = greenish-yellow or yellow exceeds green. Colour failures score against a separate **10 %** tolerance.
- Firm (No. 1) = yields not more than slightly to moderate pressure; fairly firm (No. 2) = may yield to moderate pressure but not soft.
- Shipping-point tolerances, No. 1: 10 % other defects, within which 5 % serious damage, within which **1 % decay**. No. 2: 10 %, with 5 % for decay/contact spot/Alternaria/endoxerosis combined, 1 % decay. Export No. 1 itemised: decay 1 %, contact spot 3 %, growth cracks 3 %, Alternaria 3 %, softness 5 %, dryness 5 %.
- En route/destination, No. 1: 12 % total, 7 % serious damage, **3 % decay**.
- Per-sample rule: not more than 1.5× a tolerance of ≥10 %, 2× a tolerance <10 %, at least one decayed fruit allowed per sample if the lot average complies.
- Seedless: ≤6 fruit with seeds per 100-count composite; "seedless" on ≥95 % of containers.
- "Mature" is not defined in the federal standard; maturity is left to state law.

**USDA inspection procedure.** Minimum 25 fruit per sample; shipping point ≥1 sample per 200 containers and ≥3 per lot; market 1 % of containers up to 2,000; double sample (≥50) when a tolerance is exceeded. Decay, internal decline and red blotch are always serious damage in any amount; membranous stain is damage when visible, serious when it "materially detracts"; oleocellosis is damage above a ½-inch aggregate. Defects are classed Quality (fixed) vs Condition (changes in storage). ([AMS Lemons Inspection Instructions](https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions%5B1%5D.pdf))

**California standard.** 3 CCR 1430.30 defines serious damage thresholds (aging ≥25 % surface dried/hardened; internal decline = core gumming full length; scars ≥25 %; smudge >1/3; red blotch ≥10 %). 1430.31 tolerances: 5 % internal decline/sunburn/drying, 10 % freezing (5 % severe), 5 % other, **15 % aggregate**. ([3 CCR 1430.30](https://regulations.justia.com/states/california/title-3/division-3/chapter-1/subchapter-4/article-22/section-1430-30); [3 CCR 1430.31](https://www.law.cornell.edu/regulations/california/3-CCR-1430.31)) Juice minimum: UC Davis cites "28 or 30 % by volume depending on grade"; the FAC §42941-series text was not retrieved; verify with the QC bench. CDFA's Citrus Program is run through county commissioners in nine counties including Ventura. ([CDFA](https://www.cdfa.ca.gov/is/i_&_c/citrus.html))

**Sunkist grades.** Public sheets list two marks, "Sunkist" and "SK"; trade listings equate SK with "Choice" and Sunkist with "Fancy." Sizes 63–235. Sunkist's colour vocabulary (dark green/light green/silver/yellow) is not published. ([Sunkist sell sheet](https://foodservice.sunkist.com/wp-content/uploads/sites/3/2015/12/P9836_Lemon_FS_SellSheet_Downloadable.pdf))

**Export.** EU/UNECE: minimum 20 % juice; green (not dark green) allowed if juice met. ([EU Reg 2023/2429](https://eur-lex.europa.eu/eli/reg_del/2023/2429/oj/eng)) Argentina: 30 % domestic / 35 % export, ≥70 % of fruit with typical colour, 15 % aggregate defects. Korea: packinghouse Fuller Rose Beetle affirmation letter plus Septoria copper program (15 Oct–30 Nov) and NAVEK sampling. China: signed SOPs, Phytophthora monitoring and copper treatment, MRL documentation. Japan: post-harvest fungicides are regulated as food additives and must be labelled on the carton. ([CCQC advisory 2025/26](https://www.cacitrusmutual.com/2025/10/09/ccqc-advisory-required-documentation-and-treatments-for-2025-2026-citrus-export-season/))

**Implies for the app:** encode the USDA tolerance ladder (1 % decay shipping point / 3 % destination, 5 % serious, 10 % colour) as the "pack-eligible" test, the CA 15 % aggregate as "still legal," and give each lot an export-eligibility flag set by grove/packinghouse program, not by fruit quality alone.

## 4. Traceability and compliance

- **FSMA 204.** Fresh citrus is **not** on the Food Traceability List. The compliance date is **20 July 2028** after a 30-month extension, and the Continuing Appropriations Act 2026 bars enforcement before then. ([FDA](https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods); [Rutgers](https://cumberland.njaes.rutgers.edu/2025/02/03/food-safety-modernization-act-fsma-traceability-rule-section-204-update/))
- **PTI.** Voluntary but retailer-driven: GS1-128 with GTIN (AI 01), lot (AI 10), pack date (AI 11/13), plus human-readable commodity/size/pack date/shipper. ([PTI guide](https://producetraceability.org/wp-content/uploads/2022/04/Revised_PTI_Best_Practices_for_Formatting_Case_Labels_Mar_2021__FINALV2.1.pdf)) Sunkist cartons carry a Sunkist traceability barcode; Saticoy states grower-to-receiver traceability. Lot-code structure is not public.
- **GFSI.** PrimusGFS expects recall/traceback tests at least every six months; BRCGS sets a 4-hour target; reconciliation is commonly expected at ≥95 %.
- **Pool accounting.** The Sunkist Commercial Packinghouse License Agreement (Limoneira, effective 1 Nov 2025) states packers "may adopt reasonable plans for pooling fruit and the proceeds," must return net proceeds to growers after packing charges, must not account for their own fruit more favourably than for other growers, and must furnish Sunkist "detailed, accurate and complete information concerning the amount, volume and value of all citrus fruit packed or handled for each Packer Grower." ([Justia](https://contracts.justia.com/companies/limoneira-co-2897/contract/1329782/)) Pool definitions live in each association's bylaws; the mechanism dates to the 1924 USDA bulletin ([AgEcon Search](https://ageconsearch.umn.edu/record/348545)). Because a grower's return is the pool's average realisation for the grade/size/period in which their fruit was *packed and sold*, the pack date, not the receipt date, determines which pool a bin lands in.

**Implies for the app:** every bin must carry grower, block, receipt date and a pack-event record (date, grade, size, cartons) that can be exported for pool statements; a "pool period" attribute on pack events will let the planner show growers why holding vs packing changed their return.

## 5. Shrink accounting and KPIs

- **Packout / fresh utilisation.** Worked example: 1,000 bins → 73 % fresh, 17 % juice, 10 % cull. ([Umbrex](https://umbrex.com/resources/umbrex-explainers/agriculture-food-explainers/packout-rate/)) Limoneira reports "fresh utilization" as its headline lemon metric. ([Limoneira 10-K FY2025](https://www.sec.gov/Archives/edgar/data/1342423/000134242325000039/lmnr-20251031.htm))
- **Weight loss.** 8 °C, 85–90 % RH: 3.5 % at 20 days in regular air. ([PMC6601498](https://pmc.ncbi.nlm.nih.gov/articles/PMC6601498/)) Argentina's protocol builds in a ≥4 % pack-weight overage.
- **Decay.** Hot-water + wax + fungicide can hold decay to ~2 % vs 26.7 % untreated. CRI: delayed or inadequate precooling is "the single most important reason for high waste figures."
- **Kiwifruit analogue.** Zespri tracks "condition checking, repacking, fruit loss, and taste compensation" as storage-age-driven costs and requires notification of any line under 4.0 kgf firmness; KiwiStart pays growers to release fruit early because "a balanced supply over time reduces storage costs and fruit loss." ([Zespri Kiwiflier Nov 2024](https://www.zespri.com/content/dam/zespri/nz/publications/Kiwiflier/kiwiflier-2024/KF-464-November-2024.pdf))
- **Gap.** No public lemon benchmark exists for repack loss %, dump %, days-in-storage or room-fill %.

**Implies for the app:** report fresh packout %, repack/downgrade %, dump %, estimated weight loss (from days × rate), average and max days-in-storage by colour class, and room fill %; let the house set its own targets, since no industry benchmarks exist to import.

## 6. Process examples

- **Saticoy:** two-pass process (wash/Sunsort pre-grade → storage by size and grade at 50–52 °F → second wash, pack wax, second optical grade, hand inspection → pack → 40–45 °F pre-cool); three plants; GFSI-certified. ([Saticoy](https://saticoylemon.com/operations/))
- **Limoneira:** Santa Paula and Yuma houses; ~4.5–5.2 M cartons/yr; now a Sunkist-licensed packer sharing "storage, washing, and packing capabilities across the Sunkist network," with $5 M projected savings. ([Blue Book](https://www.bluebookservices.com/limoneira-citrus-rejoins-sunkist-growers/))
- **Bee Sweet (Fowler):** ~3,500 bins/day; incoming fruit goes straight to degreening/temporary storage before the line.
- **Tucumán (Argentina):** cold storage plus degreening rooms; 10–12 °C by customer requirement. ([Citromax](https://www.citromax.com/packing-house/))
- **Apples (Washington):** presized fruit is returned to bins "until needed"; bins "are often made up of pooled grower lots." ([WSU](https://treefruit.wsu.edu/web-article/apple-pre-sizing-and-packing/))

**Implies for the app:** the Saticoy two-pass flow means the app's inventory unit is the *pre-graded bin* (size/colour known, final grade unknown); plan and forecast at that level, then reconcile against the pack-out record.

## Key disagreements and gaps
1. Storage setpoint: 10–11 °C (Saticoy, Cargo Handbook yellow) vs 12–14 °C (UC Davis). Model it as a colour-dependent band.
2. Storage life: Limoneira "1–18 weeks" vs UC Davis "up to 6 months" vs Argentina "max 6 months."
3. Lemon juice minimum: 28/30 % (UC Davis); federal standard has no "mature" definition; CA statute text not retrieved.
4. No published rotation rule, inspection interval, or shrink benchmark for lemon rooms anywhere.
5. Unreadable/blocked: NSW DPI lemon manual ch. 16, Argentine protocol PDF, PrimusGFS Module 5, CRI Toolkit 6.4, Zespri SLA, 1924 USDA bulletin full text.

## References
- UC Davis Postharvest, Lemon fact sheet: https://postharvest.ucdavis.edu/produce-facts-sheets/lemon
- USDA AMS, U.S. Standards for Grades of Lemons (eff. 13 May 2026): https://www.ams.usda.gov/sites/default/files/media/Lemon_Standard%5B1%5D.pdf
- USDA AMS, Lemons Inspection Instructions: https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions%5B1%5D.pdf
- 3 CCR 1430.30 / 1430.31: https://regulations.justia.com/states/california/title-3/division-3/chapter-1/subchapter-4/article-22/section-1430-30 ; https://www.law.cornell.edu/regulations/california/3-CCR-1430.31
- FDA Food Traceability Final Rule: https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods
- PTI case-label best practices: https://producetraceability.org/wp-content/uploads/2022/04/Revised_PTI_Best_Practices_for_Formatting_Case_Labels_Mar_2021__FINALV2.1.pdf
- Sunkist Commercial Packinghouse License Agreement (Limoneira): https://contracts.justia.com/companies/limoneira-co-2897/contract/1329782/
- Limoneira 10-K FY2025: https://www.sec.gov/Archives/edgar/data/1342423/000134242325000039/lmnr-20251031.htm
- Saticoy Lemon Association, Operations: https://saticoylemon.com/operations/
- CRI, Ch. 9 Packhouse Precautions (2003): https://www.citrusres.com/wp-content/uploads/2021/08/Ch-9-2-Packhouse-precautions-July-2003.pdf
- CRI Packhouse Best Practice Handbook, Toolkit 5.3: http://www.citrusresourcewarehouse.org.za/home/document-home/best-practice-handbook/citrus-packhouse-best-practice-handbook/workflow-5-logistics/toolkit-5-3-warehouse-and-stock-management
- Cargo Handbook, Lemons: https://www.cargohandbook.com/Lemons
- Argentine fresh lemon quality protocol (CDA summary): https://www.cda.org.ar/detalle_noticia.php?id=30279
- EU Delegated Reg. 2023/2429: https://eur-lex.europa.eu/eli/reg_del/2023/2429/oj/eng
- CCQC export advisory 2025/26: https://www.cacitrusmutual.com/2025/10/09/ccqc-advisory-required-documentation-and-treatments-for-2025-2026-citrus-export-season/
- Sci. Hortic. 2019, harvest maturity × storage: https://www.sciencedirect.com/science/article/abs/pii/S0304423819300718
- Umbrex, packout rate: https://umbrex.com/resources/umbrex-explainers/agriculture-food-explainers/packout-rate/
- Zespri Kiwiflier Nov 2024: https://www.zespri.com/content/dam/zespri/nz/publications/Kiwiflier/kiwiflier-2024/KF-464-November-2024.pdf
- Stemilt: https://www.stemilt.com/storing-apples-pears/ ; WSU pre-sizing: https://treefruit.wsu.edu/web-article/apple-pre-sizing-and-packing/
- DC Velocity, Bee Sweet: https://www.dcvelocity.com/articles/29455-bee-sweet-citrus-juices-up-its-packing-operations
- UF/IFAS HS195 degreening rooms: https://ask.ifas.ufl.edu/publication/HS195
- McKay & Stevens 1924, USDA bulletin (pools): https://ageconsearch.umn.edu/record/348545


---

# Agent 3 — Decision science and validation for quality-based lemon inventory

Scope note: ~20 distinct searches plus direct fetches. Several primary PDFs (Hertog 2014, ScienceDirect items, USDA lemon instructions) were paywalled or blocked, so some numbers come from abstracts or from secondary citations; those are flagged.

## 1. Quality-driven rotation (FEFO / dynamic shelf life / storage-potential programs)

- **Jedermann, Nicometo, Uysal & Lang (2014)**, *Phil. Trans. R. Soc. A* 372:20130302, is the canonical FEFO paper. Its case study is bananas in a sensor-equipped ("intelligent") container: green life has a Q10 of 3.46, so a 2 °C lower setpoint buys ~28 % more green life; the cooling-rate parameter reached 10 % accuracy after 4 days of data; and the authors warn that per-box green life carries a ±5-day SD, so shelf life is only predictable as a container average. The paper itself gives no FIFO-vs-FEFO waste number.
- The waste number that is repeatedly cited comes from the group's later survey: pilot studies (strawberries at a US distribution centre; bananas) showed losses of highly perishable products could be cut by **8–14 % of transported volume** by scheduling deliveries according to FEFO (as cited in Jedermann et al., "15 Years of Intelligent Container Research", Springer 2021). Simulation-heavy and berry/banana-specific; nothing comparable exists for citrus.
- **Hertog, Uysal, McCarthy, Verlinden & Nicolaï (2014)**, *Phil. Trans. R. Soc. A* 372:20130306, is the companion paper on how kinetic quality models feed FEFO (abstract only accessible). Its base is **Hertog et al. (2005)**, *Acta Hort.* 682:843–850: a stochastic kinetic model for tomato colour in which each fruit's "biological age" is a random variable; from the initial colour *distribution* of a batch it predicted how that distribution propagated at 12/15/18 °C with R²adj = 0.96 in an independent validation. Tijskens' "biological shift factor" work says biological age within and between batches is approximately normal.
- **Wu et al. (2025)**, *Environ. Sci. Technol.* (PMC12269072): a Monte-Carlo LCA of IoT-driven dynamic shelf life (zero-order Arrhenius model calibrated on 58 shelf-life records). Dynamic shelf life extended usable life by **13.8 % for fruit** (7.3–16.4 % across categories); behavioural interventions delivered only 3.2–6.5 % waste reduction.
- **Kiwifruit (Zespri/NZ)** is the closest commercial analogue. Storage release is governed by firmness, not pack date: the industry metric is the firmness of the **third-softest fruit in a 90-fruit sample** (Seeka 2022 Harvest Grower Guide); Zespri's 2021 service-level agreement requires coolstores to notify any line whose average firmness falls below 4.0 kgf, sets ship-by ISO weeks "depending on storage characteristic", and monitors firmness at the coolstore door. The "time payment" scheme explicitly pays growers for storage potential (NZKGI Chapter 6). The published model behind this (Hayward firmness + storage-breakdown model, *Postharvest Biol. Technol.* 2021/22) explains 93 % of firmness variance from at-harvest firmness/SSC/dry matter plus temperature history.
- **Apple/pear**: WSU's harvest guidance is a categorical version of the same idea: background colour + 25–35 % starch conversion + firmness >15 lb "qualifies for a good storage candidate", and lots are re-sampled at the warehouse "to determine if fruit will be packed immediately or stored".

Gaps: FEFO gains are reported for short-life produce with steep decay; nobody has published a citrus number. Jedermann's ±5-day per-box SD is a reminder that lot-average forecasts are the realistic ambition.

**Implies for the app/pilot**: the pack plan is a FEFO allocation problem with "days to colour band" as remaining shelf life. Model it as a distribution (Hertog) not a point, and set the pilot's headline claim at the conservative end of the 8–14 % range, measured on a lot-average basis.

## 2. Lot-level estimation from a 25-fruit sample

**Standard error of the lot mean**: SE = s/√n. With n = 25 the 95 % half-width is 0.39·s. If within-lot CCI SD is ~2 units, the lot mean is known to ±0.8 CCI; if SD is ~4 units, ±1.6. Halving that needs n = 100. No published within-lot CCI SD for lemons was found.

**Percentiles are much harder than means.** The k-th smallest of n fruit estimates roughly the k/(n+1) quantile, so with 25 fruit the 2nd-lowest is the ~8th percentile and nothing below the ~4th percentile is observable. Zespri's rule (3rd of 90 ≈ 3rd percentile) needs 90 fruit precisely because they decide on the tail. If the pack decision must be "at most 10 % of fruit still below the band", the cleaner tool is a one-sided normal tolerance bound: lower bound = x̄ − k·s, with k ≈ 1.84 (n = 25, 90 % coverage, 95 % confidence) or k ≈ 2.29 for 95 % coverage. Hertog's alternative is to fit the distribution and compute the fraction crossing the threshold at each forecast date.

**Acceptance sampling**: USDA's lemon inspection instructions base both internal-defect plans on an **initial 25-fruit sample** (continuing to five consecutive clean samples), and grades apply tolerances per sample against percent-nonconforming. ANSI/ASQ Z1.4 is attributes sampling for percent defective and says nothing about estimating a continuous mean; it would be misapplied to CCI. OECD's *Guidelines on Objective Tests* contain a colour-gauge method but no sample-size statistics.

**Implies**: report the lot mean with its SE; do not display sub-10th-percentile claims from 25 fruit. Let the plant choose the decision statistic (mean vs. tolerance bound) and in the first two weeks measure within-lot SD on a few 50–100-fruit samples to decide whether 25 is enough.

## 3. Forecast validation and pilot evaluation

**Metrics in the literature**: persimmon peak-harvest date MAE ≈ 3 days; apple maturity date RMSE 7.5–8.1 days (hybrid ML + process model); Egyptian strawberry export lots RMSE 0.41 days on shelf life (800 lots). Citrus: 'Rustenburg' navel (10,800 fruit, 3 orchards): XGBoost RMSE 0.217 on a 5-point acceptance score, R² 0.891; 'Valencia': SVR RMSE 0.195, R² 0.884; storage time was the dominant feature, then temperature and humidity (Horticulturae 2022). Kinetic kiwifruit models within 6.5 % of measured quality indices.

**Protocols**: the strawberry study is the best worked example of leakage control: stratified 5-fold CV on 640 lots plus a 160-lot holdout never touched in training. No agreed accuracy bar exists. Because repeated samples within a lot are correlated, random fruit-level splits inflate skill; **leave-one-lot-out** and **forward-chaining hindcast** (fit on samples up to day t, predict later samples) are the honest tests.

**Censoring**: Hough, Langohr, Gómez & Curia (2003), *J. Food Sci.*, introduced survival analysis to shelf life: the event time is interval-censored when observations are periodic (band reached somewhere between sample k and k+1) and right-censored when the product is removed before the event, exactly a lot packed or juiced before reaching the band. Fit Weibull/log-logistic AFT models and evaluate calibration by comparing the predicted CDF of "band reached by date d" with the Kaplan–Meier estimate. Evaluating only lots that reached the band is selection bias.

**Power for a 1–2-month pilot** (two-proportion formula, α = 0.05, 80 % power):

| Baseline dump/downgrade rate per lot | 20 % relative reduction | 50 % |
|---|---|---|
| 10 % | 3,213 lots/arm | 434 |
| 20 % | 1,447 | 199 |
| 30 % | 858 | 120 |

A binary lot-level outcome cannot show a 10–20 % reduction in a pilot. A continuous per-lot outcome can: detecting a 3-point drop in % downgraded fruit with SD 5 needs ~44 lots/arm; with SD 8, ~112. Design: interleave (alternate weeks, or split rooms) rather than pure pre/post, because October→December colour behaviour drifts seasonally; pre-register the primary endpoint as forecast skill (RMSE-days vs. a naive "all lots at the mean rate" baseline, plus calibration) and treat waste as secondary.

**Implies**: log every sample with lot, room, and pack/divert date so the dataset is survival-ready; report RMSE in days against the naive baseline via leave-one-lot-out; size the waste claim on a continuous outcome with ≥45 lots per arm.

## 4. Temperature-history modelling

- **Arrhenius/Q10**: Q10 = 2 ↔ Ea ≈ 12.2 kcal/mol, 3 ↔ 19.4, 4 ↔ 24.5 (Giannakourou & Taoukis 2020). Rate error from a temperature error ΔT is Q10^(ΔT/10): for **±1 °C, ±7 % of days at Q10 = 2, ±12 % at Q10 = 3, ±13 % at Q10 = 3.46**. Caveat: lemon degreening is bell-shaped (Mitalo et al. 2020), so Arrhenius is valid only on the rising limb, ~5–15 °C, consistent with the temperature-band approach.
- **Thermal history matters more than parameters**: Giannakourou & Taoukis (2020, double Monte Carlo) found temperature variability tripled prediction uncertainty relative to kinetic-parameter uncertainty (±71 vs ±26 days).
- **Grapefruit** degreening onset depended on the 14-day mean of daily minimum temperatures reaching 13–14 °C (*Sci. Hort.* 2013), a trailing-window feature matching the Murcia work.
- **Loggers vs setpoint**: Badia-Melis et al. (2015, *Sensors*, 90 RFID loggers in 1,848 m³ commercial chambers) found ~3 °C daily swings inside chambers and systematically warmer fronts near doors, recommending zone-specific placement; Jedermann's container needed 20 sensor positions and found cooling-rate constants spanning 0.31–0.96 across positions. EN 12830 requires logger error + uncertainty < 1 °C.

**Implies**: use logger data at the pallet zone, not the room setpoint; carry per-room ΔT uncertainty into the forecast interval (±1 °C ≈ ±1 week on a 10-week hold at Q10 ≈ 3).

## 5. Decision rules under uncertainty and human factors

- **Cost–loss rule** (Thompson 1952; Murphy 1977): act when P(event) > C/L. For "pack now vs hold": hold a lot only when P(band reached by ship date) × (price uplift) exceeds the expected cost of holding (decay/dump + storage). Equivalent newsvendor form: critical fractile Cu/(Cu+Co). FAO's marketing guidance is blunt that holding perishables for price rarely pays; colour gain is the only justification for a lemon hold.
- **Prediction intervals beat point dates**: Joslyn & LeClerc (2012, *J. Exp. Psychol.: Applied*): uncertainty forecasts improved decisions, increased trust, and attenuated the trust loss after forecast errors; 85 % of participants voluntarily requested uncertainty information. Leffrang (2025, *J. Forecasting*) shows uncertainty visualisation raises utilisation of algorithmic advice.
- **Override behaviour**: Fildes et al. (2009, *Int. J. Forecasting*, 60,000 forecasts): 75–80 % of system forecasts were manually adjusted; large adjustments helped, small ones hurt, upward adjustments were biased. Dietvorst, Simmons & Massey (2018): people use an imperfect algorithm far more if they can modify it, even slightly. Zia et al. (2026, *Front. AI*, 771 certified crop advisors): each +1 % accuracy raised adoption odds 4.4 %; distrust cut odds ~40 %; advisors want to edit recommendations and calibrate locally. No packinghouse-operator override rates exist in the literature.

**Implies**: show a date range and P(band by date), state the plant's C/L threshold explicitly, allow and log overrides (the override log is itself pilot evidence), and expect ~75 % adjustment at first.

## 6. Data standards a small app should adopt

- **Lot identity**: PTI/GS1-128 case labels carry GTIN (AI 01) + Batch/Lot (AI 10, ≤20 alphanumeric, case-sensitive, upper-case recommended) and optionally pack date (AI 13). Store the lot key as the GS1 lot string so it joins to the packer's PTI labels.
- **Quality/sensor events**: GS1 EPCIS 2.0 (ISO/IEC 19987:2024) adds `sensorElementList` for temperature/humidity in JSON-LD; OpenEPCIS is an open-core implementation. No produce-specific colour-index schema exists.
- **Loggers**: no open interchange format; vendors export CSV/PDF; EN 12830 defines accuracy classes. Ingest CSV with (logger_id, timestamp, °C) and keep raw files.

## References

- Jedermann R, Nicometo M, Uysal I, Lang W (2014). Reducing food losses by intelligent food logistics. https://pmc.ncbi.nlm.nih.gov/articles/PMC4006168/
- Jedermann R et al. (2021). 15 Years of Intelligent Container Research. https://link.springer.com/chapter/10.1007/978-3-030-88662-2_11
- Hertog M et al. (2014). Shelf life modelling for FEFO warehouse management. https://royalsocietypublishing.org/rsta/article/372/2017/20130306/59084
- Hertog M et al. (2005). Incorporating biological variation in postharvest modelling. Acta Hort 682. https://www.ishs.org/ishs-article/682_109
- Tijskens L et al. The biological shift factor. https://ishs.org/ishs-article/687_3/
- Wu et al. (2025). Dynamic shelf life LCA. https://pmc.ncbi.nlm.nih.gov/articles/PMC12269072/
- Hayward kiwifruit firmness/SBD model (2021). https://www.sciencedirect.com/science/article/abs/pii/S0925521421003288
- Seeka 2022 Harvest Grower Guide. https://www.seeka.co.nz/vdb/document/605
- Zespri 2021 SLA. https://www.zespri.com/content/dam/zespri/nz/corporate-information/regulatory-affairs/sla-service-level-agreement/2021-SLA-Redacted.pdf
- NZKGI Kiwifruit Book ch. 6. https://www.nzkgi.org.nz/wp-content/uploads/2024/12/J003459_NZKGI_KF_Book_24_R2C_FINAL_CHAPTER_SIX.pdf
- WSU Apple Harvest. https://treefruit.wsu.edu/web-article/harvest-apples/
- USDA AMS Lemons Inspection Instructions. https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions[1].pdf
- ASQ, ANSI/ASQ Z1.4. https://asq.org/quality-resources/z14-z19
- OECD Guidelines on Objective Tests. https://www.oecd.org/content/dam/oecd/en/topics/policy-sub-issues/fruits-and-vegetables/guidelines-on-objective-tests.pdf
- Egyptian strawberry export ML (2025/26). https://pmc.ncbi.nlm.nih.gov/articles/PMC13434681/
- Rustenburg navel shelf-life models (2022). https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9266293/ ; Valencia. https://www.mdpi.com/2311-7524/8/7/570
- Apple maturity-date hybrid model. https://pubmed.ncbi.nlm.nih.gov/42538841/ ; persimmon harvest date. https://doi.org/10.3390/agriengineering7060180
- Hough G, Langohr K, Gómez G, Curia A (2003). Survival analysis applied to sensory shelf life. https://ift.onlinelibrary.wiley.com/doi/abs/10.1111/j.1365-2621.2003.tb14165.x
- Interval-censored grapevine phenology (2025). https://arxiv.org/pdf/2510.09702
- Giannakourou M, Taoukis P (2020). Holistic uncertainty in shelf-life prediction. https://pmc.ncbi.nlm.nih.gov/articles/PMC7353492/
- Kiwifruit kinetic shelf-life models. https://www.sciencedirect.com/science/article/abs/pii/S002364382031598X
- Mitalo et al. (2020). Low temperature modulates lemon peel degreening. https://academic.oup.com/jxb/article/71/16/4778/5831195
- Grapefruit temperature and peel colour onset (2013). https://www.sciencedirect.com/science/article/pii/S0304423813002859
- Badia-Melis R et al. (2015). RFID+WSN fruit storage monitoring. https://pmc.ncbi.nlm.nih.gov/articles/PMC4435195/
- EN 12830 accuracy requirement (cited in). https://doi.org/10.3390/s25092911
- Murphy AH (1977) cost-loss model; summary. https://www.cawcr.gov.au/projects/verification/value/relativevalue_more.html
- Joslyn S, LeClerc J (2012). Uncertainty forecasts improve decisions. https://www.apa.org/pubs/journals/features/xap-18-1-126.pdf
- Leffrang (2025). Visualizing uncertainty in forecasts. https://onlinelibrary.wiley.com/doi/full/10.1002/for.3222
- Fildes R, Goodwin P, Lawrence M, Nikolopoulos K (2009). https://www.sciencedirect.com/science/article/abs/pii/S0169207008001362
- Dietvorst B, Simmons J, Massey C (2018). Overcoming algorithm aversion. https://faculty.wharton.upenn.edu/wp-content/uploads/2016/08/Dietvorst-Simmons-Massey-2018.pdf
- Zia A et al. (2026). DCE with certified crop advisors. https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1747663/full
- FAO Horticultural marketing, ch. 8. https://www.fao.org/4/a0185e/a0185e0a.htm
- PTI case-label best practices. https://producetraceability.org/wp-content/uploads/2022/04/Revised_PTI_Best_Practices_for_Formatting_Case_Labels_Mar_2021__FINALV2.1.pdf
- GS1 EPCIS 2.0. https://www.gs1.org/standards/epcis ; OpenEPCIS. https://openepcis.io/


---

## Independent code review of the `prelaunch-items` diff (10 September 2026)

Reviewer: separate agent, read-only, ran the suite (133 OK), `makemigrations --check` clean, recompiled `django.mo` and byte-compared it to the `.po`. Blockers 1 and 3 were re-verified by hand against `forecast/model.py:78-121`, `forecast/services.py:82` and `config/settings.py:134-139`.

### Blockers

1. **Temperature prior is applied retroactively to days already spent, keyed to the current room.** `forecast/model.py:85-86` scales the prior by the current room setpoint, then the `prior_from_one_point` and `prior_from_receiving_color` paths compute `cci_now = anchor + prior × elapsed_days` with that scaled prior. Moving a 30-day-old dark-green lot from a 55 °F room into a 41 °F room drops the factor to ~0.14, re-stages the lot and pushes the crossing past the horizon, so the pack-by date disappears with no new observation. This contradicts the model's own invariant ("passing time alone must never move a deadline forward"). The OLS path is unaffected. Fix: integrate `temperature_rate_factor(setpoint)` over the room-exposure intervals (already computed by `room_exposure_intervals()`) for the elapsed term, and use the current room's factor only from today forward. Add a test that a room move with no new sample leaves `cci_now` unchanged.
2. **The `MODEL_VERSION` bump blanks every board until the nightly rebuild.** Every stored prediction now fails `review_blockers` ("Rebuild forecast with the current model") until `build_predictions` runs at 02:15. Neither the Dockerfile nor `scripts/web.sh` runs it. Fix: run `build_predictions` as a release step after `migrate` and say so in the deploy notes.

### Should-fix before launch

3. **`LANGUAGE_CODE` never reaches templates.** `config/settings.py` lacks `django.template.context_processors.i18n`, so `<html lang>` is "en" on Spanish pages and both toggle buttons show `aria-pressed="false"`. The existing test passes only because it matches the `<button lang="es">` attribute. One-line fix plus tighten the assertion to `<html lang="es"`.
4. **Publishing with "Not set" silently inherits the previous plan's market regime** (`forecast/plans.py:54-55` treats `''` like "unknown"). Use `None` as the automated sentinel and pass `''` through.
5. **Language cookie lacks Secure / HttpOnly / SameSite** while session and CSRF cookies have them. Set `LANGUAGE_COOKIE_SECURE`, `LANGUAGE_COOKIE_HTTPONLY`, `LANGUAGE_COOKIE_SAMESITE='Lax'`.
6. **Capture has no recovery path when the POST fails.** `static/capture.js:104-106` disables Save and never re-enables it; a back-navigation from a failed POST restores a disabled button and an empty file input. Minimum fix: re-enable on `pageshow` when `e.persisted`. There is no offline queue.
7. **Frozen evidence notes are language-dependent at write time.** `lots/planning.py:84-86` returns translated strings that `publish_plan` freezes into JSON; a Spanish-toggled publisher writes Spanish notes for every reader. Wrap publish in `translation.override('en')` or store codes.

### Nice-to-have

- `forecast/views.py:263` `if form` should be `is not None`.
- `plan-decisions.js` updates the Accept-all label but the inline confirm still quotes the server-rendered count.
- `plan_accept_remaining` on a locked plan records `after_lock=True` without saying so; not idempotent under two concurrent GMs.
- Lot detail falls back to the plan's regime when the decision has none; `plan_market` can change it later, so show "—".
- Middleware runs two group queries per request on top of the three in the roles context processor; cache the group set.
- Language cookie outlives logout: a GM on the foreman's phone gets Spanish. Clear it on logout.
- Settings help says setpoints are °F while the warm threshold is °C; 55 °F = 12.8 °C counts as cool. Put the °F equivalent in the help text.
- `Sample.fruit_count` model default stays 10 while the setting default is 25; admin/import samples show "of 10".
- Untranslated fragments in Spanish screens: board `aria-label`s, warm-clock `title`, defect labels, market-regime labels; plan detail is reachable by foremen but untranslated.
- `static/app.css` drops `position: sticky` from every `th` (intentional, but app-wide).

### Model/science consistency

Three notions of temperature coexist: the prior uses a single current setpoint; the warm clock uses setpoint history from room moves; `environment_features` computes trailing measured RoomCondition temperature and stores it in `Prediction.inputs`, but nothing consumes it. Units are consistent (everything converts through `Room.setpoint_c`; readiness and the warm clock share `warm_storage_temp_c`). `ModelSettings` defaults are sane and validated.

### Test coverage gaps

- Room move without a new sample leaves `cci_now` / `pack_by` unchanged (would have caught blocker 1); `rebuild_for_lot` passing the room setpoint and storing `warm_storage`.
- `plan_market` invalid value; `plan_accept_remaining` as foreman (403) and after lock; `packout_quality` cross-plant 404 and validation re-render.
- `warm_exposure` when the current room has no setpoint.
- `color_correct(method='curve')` non-monotone fallback and `score_photo` reading the method from settings.
- `_capture_seconds` four-hour cap; `set_language` cookie attributes.
- No JS harness: `capture.js` and `plan-decisions.js` are hand-verified only.

### Reviewer's readiness verdict

Coherent change set with solid plumbing: every new endpoint is role-gated and plant-pinned, CSRF rides on the fetch path, migrations are additive and reversible, the Spanish catalogue is complete and compiled. Blockers 1 and 2 plus item 3 should land in the same commit; 4 to 7 can follow in the first pilot week.
