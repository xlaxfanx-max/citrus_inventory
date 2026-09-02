# How packinghouses track fruit ripening — research & source brief

Prepared 20 Aug 2026. Citrus-weighted, with apple/avocado sources included where the method transfers.

---

## The short version

There is no single "ripeness tracker." Packinghouses run **five separate layers**, and they rarely talk to each other. That disconnect is the interesting part for an inventory product.

| Layer | What is measured | Where | Data typically captured |
|---|---|---|---|
| 1. Lot maturity at intake | Brix, titratable acidity, Brix:acid ratio, color | QC bench, destructive sample | Paper/spreadsheet, per lot |
| 2. In-line internal quality | Brix / dry matter / internal defects per fruit | Grading line, NIR | Sorter PLC, rarely exported |
| 3. Color & degreening | Citrus Color Index, chlorophyll loss | Degreening room + camera grader | Room controller + operator eyeball |
| 4. Room / storage state | Ethylene, CO₂, temp, RH | Storage & ripening rooms | Building automation, IoT sensors |
| 5. Shelf-life / allocation | Predicted remaining life, FEFO order | Planning | Mostly absent — this is the gap |

---

## 1. Lot maturity testing (the legal / contractual baseline)

Citrus is unusual: maturity is **regulated**, so packers already generate maturity data on every lot before packing. That data exists and is usually stranded.

- **CDFA citrus maturity regulations (California)** — the Brix:acid ratio and color standards packers must certify against. Useful for understanding what QC labs are *already* required to record.
  https://www.cdfa.ca.gov/is/docs/Citrus_Maturity_FSR.pdf
- **USDA AMS, Determination of Maturity for Imported Fresh Grapefruit (Section 8e)** — the sampling and juice-testing procedure, written out step by step.
  https://www.ams.usda.gov/sites/default/files/media/Determination_of_Maturity_for_Imported_Fresh_Grapefruit_Under_Section_8e_A_081622.pdf
- **Echeverria, "Brix and Acid Determinations" (UF/IFAS Citrus Quality Control Short Course)** — practical lab method used in Florida packinghouses.
  https://irrec.ifas.ufl.edu/flcitrus/pdfs/short_course_and_workshop/quality_control/Echeverria-Brix_and_Acid_Determinations_high.pdf
- **Florida 2024–25 orange maturity standards (Fla. Admin. Code R. 20ER24-3)** — and note that Florida *lowered* processed-citrus maturity standards, which shows these thresholds move.
  https://www.law.cornell.edu/regulations/florida/Fla-Admin-Code-Ann-R-20ER24-3 · https://www.freshplaza.com/north-america/article/9779690/florida-lowers-maturity-standards-for-processed-citrus/
- **"The Brix/Acid Ratio" (Springer, in *Analysis of Nonalcoholic Beverages*)** — background on why the ratio is the accepted maturity proxy and where it misleads.
  https://link.springer.com/chapter/10.1007/978-94-011-3700-3_4

**Why it matters:** every packer has per-lot Brix/acid history. Almost none use it to sequence what gets packed or shipped first.

---

## 2. Non-destructive per-fruit sensing (NIR / Vis-NIR)

This is the most mature technology and the best-documented literature.

- **Walsh, Blasco, Zude-Sasse & Sun (2020), "The uses of near infra-red spectroscopy in postharvest decision support: A review," *Postharvest Biology and Technology* 163:111139.** The anchor review — covers in-line NIR for segregating fruit into storage vs. immediate-market streams. *(Publisher blocks automated fetch; abstract accessible via the link.)*
  https://www.sciencedirect.com/science/article/abs/pii/S0925521419308129
- **Cavaco, Passos, Pires, Antunes & Guerra (2021), "Nondestructive Assessment of Citrus Fruit Quality and Ripening by Visible–Near Infrared Reflectance Spectroscopy," IntechOpen. DOI 10.5772/intechopen.95970.** The best citrus-specific source. Findings worth quoting: SSC models reach **R² 0.85–0.96 (RPD 1.87–4.92)** on benchtop/handheld; titratable acidity needs **>1000 nm**; maturity index (SSC/TA) is only moderately predictable; on-tree/field measurement drops **below R² 0.80**. Also flags that most calibrations lack multi-season, multi-orchard external validation — the real adoption blocker.
  https://www.intechopen.com/chapters/75090
- **Ogawa et al. (2026), "A Practical Approach for Predicting Avocado Ripeness Using a Portable Vis-NIR Device and Sensory-Based Indexing Under Various Storage Temperatures," *AgriEngineering* 8(4):130.** Directly ties spectra + storage temperature to **days-to-ripe**: at 25 °C a fruit at index 3 hits eating-ripe in ~1.1 days; at 15 °C, ~3.1 days; ripening effectively stops near 12 °C. Explicitly frames the output as enabling FEFO. This is the closest published example of "sensor reading → inventory decision."
  https://doi.org/10.3390/agriengineering8040130
- **Cubero/Blasco group and others on avocado dry matter by NIR** — dry matter is the accepted maturity index and predicts ripening time.
  https://www.mdpi.com/2223-7747/12/17/3135
- **Vendor context (what is actually installed on lines):**
  - TOMRA **Inspectra²** — NIR, non-destructive internal inspection for apples, avocados, citrus, kiwifruit; markets citrus specifically as "grade high-brix product for premium export." https://www.tomra.com/food/machines/inspectra2
  - GREEFA **iFA** — light transmitted through the whole fruit; grades on Brix and internal defects (glassiness, internal browning). https://www.greefa.com/product/internal-quality-ifa/
  - Aweta **Inscan Pulse** for citrus — spectroscopy for sugar content, granulation, internal disorders, per-fruit maturity level. https://www.aweta.com/en/produce/citrus
  - Sunkist **Sunsortai** (2022) — imaging + AI for defects/decay, notably **not** maturity. Good evidence that the AI-vision wave went after defects, not ripeness. https://www.foodengineeringmag.com/articles/100320-sunkist-research-and-tech-services-launches-next-gen-citrus-fruit-sorter

**Caveat to carry:** vendors publish almost no independent accuracy or throughput data. Cavaco et al. say so explicitly ("performance data remain limited due to proprietary concerns").

---

## 3. Chlorophyll / delta-absorbance (IAD) — ripening as a continuous index

Standard in pome and stone fruit; conceptually the cleanest "ripening clock."

- **Nondestructive Apple Ripening Stage Determination Using the Delta Absorbance Meter at Harvest and after Storage, *HortTechnology* 27(1):54.** https://journals.ashs.org/horttech/view/journals/horttech/27/1/article-p54.xml
- **A Study on the Potential of I_AD as a Surrogate Index of Quality and Storability in 'Gala' Apple, *Agronomy* 9(10):642.** Directly about using an index to predict **storability** — i.e. which bins should be stored longest. https://doi.org/10.3390/agronomy9100642
- **Determination of optimal harvest boundaries for Honeycrisp using a new chlorophyll meter, *Can. J. Plant Sci.*** https://cdnsciencepub.com/doi/10.4141/cjps2013-241
- **Penn State Extension, "Determining Apple Fruit Maturity and Optimal Harvest Date"** — the practitioner-facing version (starch-iodine, DA meter, ethylene). https://extension.psu.edu/fruit-harvest-determining-apple-fruit-maturity-and-optimal-harvest-date
- **Overview of the DA-Meter in field and postharvest use (Postharvest.biz).** https://www.postharvest.biz/news/all-about-the-da-meter-the-instrument-to-measure-the-ripening-stage-in-the-tree-and-postharvest-26883

**Citrus note:** IAD is not established for citrus (non-climacteric, chlorophyll degrades in the peel via degreening rather than tracking internal ripening). Do not assume it transfers.

---

## 4. Color, degreening and the citrus-specific problem

Citrus doesn't ripen after harvest in the usual sense — it de-greens. Packinghouses therefore track *color*, and the degreening room is a genuine inventory bottleneck.

- **Porat, R. (2008), "Degreening of Citrus Fruit," *Tree and Forestry Science and Biotechnology* 2(SI1):71–76.** The operational reference. Concrete parameters: **1–5 ppm ethylene** (many packers now run 1–2 ppm; >5–10 ppm adds no speed but adds decay), **20–25 °C** (Florida runs ~29 °C to shorten time at the cost of color quality), **90–95 % RH**, ~**1 air exchange/hour** with automatic exchange when CO₂ exceeds 0.25 %, **3–5 days** typical. Monitoring is visual plus ethylene sensors. Risks: *Penicillium* green mold, *Diplodia* stem-end rot, calyx abscission.
  http://www.globalsciencebooks.info/Online/GSBOnline/images/0812/TFSB_2(SI1)/TFSB_2(SI1)71-76o.pdf
- **"Quality of Postharvest Degreened Citrus Fruit," IntechOpen.** https://www.intechopen.com/chapters/82262
- **UF/IFAS Postharvest program, ethylene & degreening resources.** https://irrec.ifas.ufl.edu/postharvest/index/ethylene.shtml
- **Vidal, Talens, Prats-Montalbán, Cubero, Albert & Blasco (2013), "In-Line Estimation of the Standard Colour Index of Citrus Fruits Using a Computer Vision System Developed For a Mobile Platform," *Food and Bioprocess Technology* 6(12):3412–3419. DOI 10.1007/s11947-012-1015-2.** Real-time CCI estimation, **R² = 0.925** against a spectrophotometer — cheap, proven, and directly usable to decide which lots need degreening and for how long.
  https://link.springer.com/article/10.1007/s11947-012-1015-2

---

## 5. Hyperspectral imaging (research-stage for ripeness)

- **Wang, Lu, Wang, Miao, Liu, Shui, Gao & Gao (2025), "In situ nondestructive identification of citrus fruit ripeness via hyperspectral imaging technology," *Plant Methods* 21(1):77. DOI 10.1186/s13007-025-01354-z.** 'Shiranui' mandarin, 400–1000 nm, three ripeness classes; SPA-BP model reports **99.19 % / 100 %** accuracy. Treat with scepticism: single orchard, ripeness labels came from grower judgement, not instrumented reference. Good for citing that the method works; bad as evidence it generalizes.
  https://plantmethods.biomedcentral.com/articles/10.1186/s13007-025-01354-z
- **Naqvi, Balasubramaniam, Li, Liu & Li (2025), "Four-Dimensional Hyperspectral Imaging for Fruit and Vegetable Grading," *Agriculture* 15(15):1702.** VNIR + SWIR + 3D structured light. Worth knowing that it targets **defects and geometry, not maturity** — and argues for interpretable decision trees over deep learning for trust and traceability in grading.
  https://doi.org/10.3390/agriculture15151702
- **"Insights into recent developments and obstacles in automated fruit ripeness classification," *ScienceDirect* (2025)** — survey of what still blocks deployment. https://www.sciencedirect.com/science/article/pii/S2949736125001368
- **Conventional NIR vs. Hyperspectral Imaging: Similarities, Differences, Advantages, and Limitations, *Molecules* 30(12):2479.** Useful for deciding which to build against. https://www.mdpi.com/1420-3049/30/12/2479

---

## 6. Room-level and continuous monitoring (ethylene / IoT)

- **Strella Biotechnology** — ethylene biosensors in storage rooms, DCs and retail ripening rooms; claims 2 B lb of produce monitored, 20 M lb of shrink saved, 26 countries. The clearest commercial precedent for "monitor the room, predict maturity, resequence inventory."
  https://www.strellabiotech.com/ · distributor detail: https://qasupplies.com/strella-sensors/ · independent write-up: https://www.washingtonpost.com/climate-solutions/interactive/2021/food-waste-climate-change-strella-biotechnology/
- **AgroFresh FreshCloud** — storage-quality analytics; recently added AI imaging and orchard analytics (Aerobotics, Neolithics). Shows the incumbent chemistry vendors moving into the data layer.
  https://www.agrofresh.com/solutions/freshcloud/ · https://www.thepacker.com/news/packer-tech/agrofresh-expands-digital-ecosystem-ai-powered-imaging-analytics
- **Clarifresh** — AI-assisted QC data capture for fresh produce packhouses. https://clarifresh.com/

---

## 7. Turning ripeness data into inventory decisions — the thin spot

This is where the literature is smallest and the product lives.

- **"Utilizing preharvest and packinghouse data in combination with storage trials to develop an intelligent logistic management system for 'Orri' mandarins," *Postharvest Biology and Technology* (2025).** The single most on-point paper: citrus, packinghouse data, storage trials, logistics decisions. *(Publisher blocks automated fetch — full text not read; details from title/indexing. Worth buying or requesting from the authors.)*
  https://www.sciencedirect.com/science/article/pii/S092552142500064X
- **Otieno, Owoyemi, Goldenberg, Yaniv, Carmi & Porat (2022), "Effects of packinghouse operations on the flavor of 'Orri' mandarins," *Food Science & Nutrition* 10(3). DOI 10.1002/fsn3.2778.** Sampled at four line stages. Ethanol rose from **36 ppm at harvest to 800–1,840 ppm after 6 weeks**; waxing plus hot-air drying drove off-flavor; Brix and acidity stayed flat. Important implication: **the standard maturity metrics did not detect the quality loss** — the packing operations themselves changed the product.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC9007302/
- **Jedermann et al., "Reducing food losses by intelligent food logistics," *Phil. Trans. R. Soc. A* 372:20130302.** The foundational FEFO / dynamic-shelf-life-routing paper. https://royalsocietypublishing.org/doi/10.1098/rsta.2013.0302
- **Ugwu et al. (2026), "Digital twins for food processing and shelf-life," *Frontiers in Food Science and Technology* 6:1813819.** Names four adoption barriers: limited observability, dataset bias/domain shift, lifecycle maintenance of calibrations, and the **"decision translation gap"** — forecasts only cut waste if they land in a workflow with predefined thresholds and defined interventions.
  https://doi.org/10.3389/frfst.2026.1813819
- **Options for reducing food waste by quality-controlled logistics using intelligent packaging along the supply chain, *Food Additives & Contaminants*.** https://www.tandfonline.com/doi/full/10.1080/19440049.2017.1315776
- **A Model for Fresh Produce Shelf-Space Allocation and Inventory Management with Freshness-Condition-Dependent Demand, *INFORMS Journal on Computing*.** The OR formulation. https://pubsonline.informs.org/doi/10.1287/ijoc.1070.0219
- **Advanced Digital Solutions for Food Traceability: NIRS, RFID, Blockchain, IoT, *J. Sens. Actuator Netw.* 14(1):21.** Covers linking per-lot quality readings to identity through the packhouse. https://www.mdpi.com/2224-2708/14/1/21

---

## Takeaways for the citrus inventory product

1. **The sensing problem is largely solved; the plumbing is not.** NIR graders, CCI cameras and QC labs all produce maturity data per lot or per fruit. It dies in the sorter PLC or a clipboard. Integration, not new sensors, is the wedge.
2. **Citrus needs its own model.** Non-climacteric fruit means IAD, ethylene-evolution and climacteric shelf-life models from apple/avocado do not transfer. Citrus "ripening" in a packinghouse is really degreening kinetics plus decay risk plus rind quality.
3. **Degreening rooms are the highest-value scheduling target.** 3–5 days at 20–25 °C with a hard decay clock, monitored by eye. Colour index cameras (R² 0.925, cheap) plus room data would let you sequence rooms rather than guess.
4. **Brix:acid won't tell you what you need.** The Orri flavor paper shows quality degrading while Brix and acidity stayed flat. Any shelf-life model built only on maturity ratio will look right and be wrong.
5. **Cite the decision-translation gap early.** Both the digital-twin review and the NIR review make the same point: the value is in the intervention thresholds, not the prediction accuracy.

---

## Access notes

ScienceDirect, Royal Society and Semantic Scholar blocked automated retrieval during this research. Abstracts are reachable at the links above; the 'Orri' logistics paper (2025) and the Walsh et al. NIR review are the two to prioritize obtaining in full.
