# CLARA Personal Health — Deep Market Research Dossier

Status: research complete; product changes intentionally not yet committed  
Date: 2026-07-25  
Decision horizon: 2026-2029  
Primary market: Viet Nam, with a Southeast Asia expansion path  
Audience: Founders, Product, Clinical Safety, Engineering, ML, Regulatory,
Partnerships and Growth

## 1. Executive conclusion

The market no longer has an open space for a product described only as a
"personal health assistant", "medical chatbot", "health record copilot" or
"proactive health recommender".

By July 2026:

- ChatGPT Health can use medical records and Apple Health across ordinary
  conversations, identify changes, relate records to daily life and personalize
  answers.
- Microsoft Copilot Health combines records from more than 50,000 US provider
  organizations, wearables, proactive insights, sourced health information and
  provider discovery.
- Perplexity Health combines records, wearables, files, biomarker trends,
  proactive insight and health memory.
- Amazon Health AI combines record-grounded guidance with booking, prescription
  renewal and near-immediate access to One Medical clinicians.
- Google/Fitbit, Samsung and Oura combine continuous sensor data with personalized
  coaching. Oura now links signals, laboratory panels and AI guidance to licensed
  physicians.
- Verily Me combines cross-provider records, clinician-reviewed preventive
  recommendations, guided symptom assessment and an AI companion.
- Guava already offers a broad personal health record, tracking, correlations,
  family profiles, visit preparation and contextual AI at USD 78 per year.

The initial CLARA idea—memory plus evidence plus recommendations plus an action
loop—is therefore necessary but not sufficient. It is a feature bundle that
incumbents can reproduce.

The defensible opportunity is narrower and more local:

> **CLARA should become the trusted interpretation and follow-through layer
> between Viet Nam's emerging longitudinal health data and the fragmented
> real-world actions a person or family must take.**

Vietnamese:

> **CLARA giúp mỗi gia đình hiểu điều gì đã thay đổi, điều gì đáng làm tiếp theo,
> và theo dõi cho đến khi việc đó thực sự được hoàn tất.**

The strategic wedge is not "more databases than ChatGPT". It is a
**Vietnam-first Personal Health Decision and Follow-through Network** built from:

1. a consumer-controlled, cross-provider health timeline;
2. reliable interpretation of Vietnamese records, prescriptions and daily
   context;
3. locally executable next steps across care, laboratories, pharmacies, benefits
   and family caregivers;
4. explicit verification of whether a recommendation was appropriate, completed
   and helpful;
5. a source-governed global medical knowledge fabric rather than an impossible
   claim of owning "all health databases in the world".

This position exploits a time-limited opening. Viet Nam is creating electronic
health books in VNeID and targeting annual health checks, but data remains
fragmented and requires standardization. At the same time, a 2025 national survey
of 3,550 Vietnamese adults found problematic health literacy in 67.3% of
participants despite sufficient eHealth literacy in most. The new product must
turn newly available data into comprehension and completed action without asking
ordinary people to become record keepers or medical researchers.

## 2. Research method and confidence

### 2.1 Sources reviewed

This review used, as of 2026-07-25:

- official product, support and pricing pages;
- official Vietnamese government and Ministry of Health publications;
- WHO, NLM, FDA, ClinicalTrials.gov, Europe PMC, SNOMED International, LOINC,
  NICE and Cochrane documentation;
- systematic reviews, randomized trials and observational studies indexed by
  PubMed;
- current CLARA architecture, implementation reports and the available licensed
  DrugBank-derived asset.

### 2.2 Evidence labels

| Label | Meaning |
|---|---|
| Observed | directly documented by an official source or the current repository |
| Supported | backed by peer-reviewed evidence, but not necessarily in Viet Nam |
| Hypothesis | commercially or behaviorally plausible; requires primary validation |
| Prohibited claim | cannot be marketed safely or truthfully with current evidence |

Competitor feature claims are treated as evidence of market scope, not proof of
clinical efficacy. Vendor user counts, evaluation results and outcome claims must
be independently checked before being used externally.

This dossier is not a legal opinion, medical-device determination, revenue
forecast or proof of product-market fit.

## 3. Category evolution

### 3.1 The category changed in less than one year

Consumer health AI moved through four rapid stages:

1. **Answering:** general LLMs explained symptoms, tests and treatment concepts.
2. **Grounding:** products added citations, files and medical records.
3. **Personalization:** products added health profiles, memory, wearables and
   longitudinal trends.
4. **Execution:** products added clinician access, bookings, prescriptions, labs
   and adaptive coaching.

The 2026 market is already entering a fifth stage: **continuous health
orchestration**, where a system watches multiple signals, recommends an action,
connects the user to a service and learns from the result.

A recent JMIR viewpoint documents the rapid launch wave from Verily, Amazon,
OpenAI, Anthropic and Microsoft and frames consumer-facing health AI as an
emerging segment with access and cost potential but unresolved safety,
accountability and equity risks:
[Big Tech and the Rise of Consumer-Facing Health AI Assistants](https://www.jmir.org/2026/1/e99230/).

### 3.2 Competitive market map

| Arena | Leaders/examples | Their structural advantage | CLARA implication |
|---|---|---|---|
| General AI distribution | ChatGPT Health, Copilot Health, Perplexity Health | hundreds of millions of existing users, frontier models, broad tool ecosystems | do not compete on generic answer quality or conversational polish alone |
| Device and sensor ecosystems | Google/Fitbit, Samsung Health, Apple Health, Oura | operating-system or hardware distribution and continuous passive data | integrate; do not attempt to out-sense device owners |
| Provider-integrated care | Amazon One Medical, K Health, Counsel, Verily | licensed clinicians, scheduling, prescribing and medical accountability | partner locally; pure AI cannot close clinical loops |
| Personal health records | Guava, MyChart, national portals | mature connectors or authoritative provider data | aggregation and timelines are table stakes |
| Diagnostics and longevity | Function Health, Oura Health Panels | owned lab purchasing flow, recurring biomarkers and high willingness to pay | avoid indiscriminate screening; use appropriate, guideline-aware testing |
| Symptom assessment | Ada and provider triage tools | structured probabilistic interview and regulated/evaluated intended use | a free-form chat intake is inferior for high-risk symptom workflows |
| Vietnamese care access | Medpro, YouMed, IVIE, eDoctor, VNeID | local provider inventory, identity, booking and human trust | local execution partnerships are a potential moat |
| Evidence workbenches | PubMed, Europe PMC, Elicit, Consensus, OpenEvidence and general deep research | scholarly retrieval or professional distribution | research evidence must support the consumer journey, not become the home screen |

## 4. Direct competitor deep dive

### 4.1 ChatGPT Health

Observed:

- launched to US users on 2026-07-23;
- can connect supported medical records and Apple Health;
- can compare current and prior tests, summarize changes and relate sleep,
  activity and workouts to the user's routine;
- can use connected health context in ordinary conversations with permission;
- has a Health home for records, trends and prior health conversations;
- is available across Free, Go, Plus and Pro plans;
- connected data and conversations using it are not used for model training or
  advertising.

OpenAI reports more than 300 million weekly users ask health questions and that
more than 70% of health conversations among early Health users occurred outside
the dedicated Health space. The second figure is especially important: consumers
do not naturally organize life into product modules. Health context must appear
when relevant, not require navigation into a clinical dashboard.

Source:
[Launching Health in ChatGPT](https://openai.com/index/health-in-chatgpt/).

Competitive conclusion:

- medical memory, record comparison, contextual chat, trends and appointment prep
  are baseline capabilities;
- CLARA cannot rely on a separate "CLARA Chat" destination as its primary UX;
- a small company cannot sustainably beat a frontier platform on every open-ended
  medical question;
- CLARA must win after the answer: local applicability, action, verification,
  longitudinal follow-through and accountable escalation.

### 4.2 Microsoft Copilot Health

Observed:

- US preview for Microsoft 365 Personal, Family and Premium subscribers;
- health profile, memory, Apple Health and medical-record connections;
- records from a stated network of more than 50,000 US provider organizations;
- proactive guidance, follow-up questioning and care navigation;
- information informed by thousands of health organizations and a Harvard Health
  relationship;
- input from a panel of more than 250 physicians across more than 24 countries;
- ISO/IEC 42001 certification for the AI management system.

Source:
[Copilot Health: Now in Preview](https://www.microsoft.com/en-us/microsoft-copilot/blog/2026/05/29/copilot-health-now-in-preview/).

Microsoft's study of more than 500,000 de-identified health conversations found:

- roughly one in five involved personal symptoms or condition discussion;
- one in seven personal health queries concerned another person;
- symptom and emotional-health queries increased at night;
- mobile skewed toward personal health while desktop skewed toward professional
  and academic work;
- many queries involved provider and insurance navigation.

Source:
[How people use Copilot for Health](https://www.microsoft.com/en-us/research/wp-content/uploads/2026/03/copilot-health-usage-report.pdf).

Competitive conclusion:

- family/caregiver support is a primary behavior, not a niche feature;
- night-time reassurance and safe escalation deserve their own service design;
- CLARA Research should not be mixed into a mobile consumer flow;
- health-system navigation is a core job and a strong localization opportunity.

### 4.3 Perplexity Health

Observed:

- included in US Pro and Max subscriptions at launch;
- connects EHRs through b.well, wellness applications through Terra and Apple
  Health;
- provides a Health hub with activity, fitness and biomarker tracking, proactive
  insights, AI summaries and health memories;
- explicitly does not diagnose, recommend specific treatment, provide
  personalized nutrition therapy or give emergency advice;
- medical-record connections are US-only at launch;
- the company describes it as a consumer wellness product to which HIPAA does not
  apply.

Source:
[What is Perplexity Health?](https://www.perplexity.ai/help-center/en/articles/14035438-what-is-perplexity-health).

Competitive conclusion:

- citations plus records plus proactive insight are no longer differentiators;
- privacy language must be precise about whether CLARA acts as a consumer product,
  processor for a provider or healthcare service;
- local care execution and regulated intended use are more defensible than search
  presentation.

### 4.4 Amazon Health AI and One Medical

Observed:

- an agentic assistant grounded in records, labs and medicines;
- answers questions, explains records, books appointments and handles medication
  renewals;
- can transition to direct-message, video or in-person One Medical care;
- Prime members are offered up to five introductory direct-message visits;
- pay-per-visit messaging is USD 29; Prime One Medical membership is USD 99 per
  year, versus USD 199 standard;
- Amazon reports that virtual-care visits nearly tripled year over year and that a
  majority now arrive through Health AI.

Sources:

- [Amazon expands Health AI](https://www.aboutamazon.com/news/retail/amazon-health-ai-agent-one-medical)
- [One Medical Prime pricing](https://www.aboutamazon.com/news/retail/one-medical-amazon-prime-benefit)

Competitive conclusion:

- "from insight to action" is already an incumbent promise;
- the moat is the transaction and licensed-care network, not the agent workflow;
- CLARA must secure Vietnamese provider, laboratory and pharmacy paths rather than
  simulate completion with links or reminders;
- marketplace incentives must not bias clinical prioritization.

### 4.5 Google/Fitbit, Samsung and Oura

Google/Fitbit now combines:

- personal health coaching built with Gemini;
- medical-record connections in the US;
- laboratory, medication and visit history;
- wearable, sleep, fitness, nutrition, cycle and mental-wellbeing signals;
- adaptive weekly plans and personalized daily messages;
- broader public-preview distribution, including Singapore.

Sources:

- [Fitbit medical-record and coach update](https://blog.google/products-and-platforms/devices/fitbit/fitbit-personal-health-coach-updates-2026/)
- [Fitbit coach expansion](https://blog.google/products-and-platforms/devices/fitbit/personal-health-coach-expansion/)

Samsung launched a Health Assistant beta on 2026-07-21 inside Samsung Health,
combining the device ecosystem's health signals with personalized guidance:
[Samsung Health Assistant beta](https://news.samsung.com/us/samsung-launches-health-assistant-beta-first-fully-integrated-ai-powered-assistant/).

Oura now combines:

- AI advice based on ring biometrics;
- memory and longitudinal coaching;
- USD 99 laboratory panels covering 50 biomarkers;
- PDF laboratory uploads;
- proactive suggestions to connect to Counsel Health;
- access to licensed physicians in eligible US states.

Sources:

- [Oura Advisor](https://support.ouraring.com/hc/en-us/articles/39512345699219-Oura-Advisor)
- [Oura and Counsel Health](https://ouraring.com/blog/he/counsel-integration-oura-app/)
- [Oura Health Panels](https://ouraring.com/blog/health-panels/)

Competitive conclusion:

- continuous sensing is an ecosystem game;
- CLARA should consume normalized summaries and ask for the minimum missing
  context;
- a recommendation based on one device score is not a medical conclusion;
- the local opportunity is combining ordinary clinical documents, medicine use,
  family observation and available sensors—not requiring premium hardware.

### 4.6 Verily Me

Observed:

- a free US consumer app;
- cross-provider medical history;
- preventive recommendations reviewed by licensed providers;
- a guided multi-turn symptom assessment that uses available history;
- meal-image logging and nutrition context;
- a FHIR-native platform that normalizes, deduplicates and enriches records;
- recommendations delivered through configurable, versioned workflows.

Sources:

- [Verily Me 2026 launch](https://verily.com/perspectives/verily-me-adds-new-features-offering-a-safe-and-private-space-to-check-symptoms-and-make-sense-of-health)
- [Verily Me platform architecture](https://verily.com/perspectives/verily-me-verily-pre-platform-first)

Competitive conclusion:

- clinician-reviewed recommendations and structured symptom interviews already
  exist in a free product;
- CLARA cannot claim that multi-agent architecture itself is consumer value;
- workflow versioning, normalization and clinical review are expected engineering
  discipline;
- local applicability and outcome evidence must be the differentiator.

### 4.7 Guava

Observed:

- a generous free tier with record and device sync, tracking, summaries, trends,
  correlations, sharing and uploads;
- a USD 78/year premium tier with automatic insights, family/caregiver profiles,
  lab extraction and contextual AI;
- a provider dashboard at USD 60/month for ten active patients, then USD 6 per
  active patient;
- connections to 100,000+ providers and devices according to the vendor.

Sources:

- [Guava plans](https://guavahealth.com/plans)
- [Guava Provider Dashboard](https://guavahealth.com/provider-dashboard)

Competitive conclusion:

- a health timeline, family profile, correlations, AI visit prep and PDF extraction
  do not justify premium pricing by themselves;
- B2B2C distribution through trusted care teams can lower acquisition cost and
  increase relevance;
- billing for active users and outcome-linked contracts are more credible than
  charging for every registered profile.

### 4.8 Function Health, Ada and portal products

Function Health charges USD 365/year for more than 160 annual lab tests, clinician
review, AI chat and adaptive "Protocols":
[Function membership](https://www.functionhealth.com/article/function365).

Ada provides a free structured symptom assessment backed by a curated knowledge
base and describes its consumer app as an EU MDR Class IIa medical device:
[Ada app](https://ada.com/app/) and
[Ada intended use](https://ada.com/help/what-degree-of-liability-does-ada-accept/).

MyChart already combines results, medicines, care plans, appointments, family
access, follow-up work and cross-organization records within participating
systems:
[MyChart features](https://www.mychart.org/l/en-us/explore/).

Competitive conclusion:

- screening volume is not inherently better care;
- structured interviews remain safer than casually prompting an LLM for certain
  symptom workflows;
- provider portals win authoritative transactions but remain institution-centric;
- CLARA should remain provider-neutral and make every external source's authority
  explicit.

## 5. What the market has commoditized

The following must be treated as table stakes or enabling infrastructure, not as
the headline:

- chat with a medical system prompt;
- multi-agent orchestration;
- retrieval-augmented generation;
- claim-level citations;
- medical-record upload and OCR;
- health memory;
- timelines and trend charts;
- wearable import;
- generic "proactive insights";
- appointment preparation;
- symptom checking;
- medicine reminders;
- family profiles;
- a dashboard with health scores;
- evidence matrices for researchers.

These may still be implemented exceptionally well. They simply do not constitute
a durable market position because incumbents already offer them or can add them.

## 6. Viet Nam market deep dive

### 6.1 Structural demand

WHO reports that noncommunicable diseases account for about 80% of deaths in Viet
Nam, with many cases undiagnosed or untreated. National policy is shifting from
treatment-centered care toward proactive prevention:
[WHO Viet Nam NCD update](https://www.who.int/vietnam/news/detail/15-12-2025-viet-nam-unites-to-tackle-top-causes-of-disease-and-death).

The World Bank reports that out-of-pocket spending remains about 40% of current
health expenditure despite high insurance coverage:
[Viet Nam out-of-pocket spending](https://documents.worldbank.org/en/publication/documents-reports/documentdetail/099501409262536925).

Implications:

- users care about cost, travel and avoiding unnecessary care, not only clinical
  sophistication;
- medication, chronic-condition and follow-up workflows have recurring value;
- product recommendations must include affordability and locally available paths
  without allowing commercial incentives to alter medical priority.

### 6.2 A national data inflection point

Observed government direction:

- more than 34 million electronic health books had been initiated, updated or used
  through VNeID by the end of January 2026;
- Viet Nam targets at least one annual free health check or screening and a
  longitudinal electronic health book for each person from 2026;
- the Ministry of Health is driving connection of periodic health-check data,
  insurance data and provider records;
- a July-September 2026 campaign is cleaning and standardizing 12 health-sector
  databases;
- IVIE has connected VNeID electronic identity and expects broader health-data
  interoperability.

Sources:

- [Viet Nam digital-health progress](https://moh.gov.vn/hoat-dong-cua-lanh-dao-bo/-/asset_publisher/k206Q9qkZOqn/content/tiep-tuc-inh-hinh-dien-mao-y-te-so-nang-cao-hieu-qua-phuc-vu-nguoi-dan)
- [Annual health-check policy](https://baochinhphu.vn/tu-nam-2026-to-chuc-kham-suc-khoe-dinh-ky-mien-phi-cho-nguoi-dan-102260506175509173.htm)
- [Health-data cleaning campaign](https://baochinhphu.vn/trien-khai-chien-dich-90-ngay-lam-sach-chuan-hoa-du-chuyen-nganh-y-te-102260715150004754.htm)
- [IVIE and VNeID](https://baochinhphu.vn/ket-noi-ung-dung-cham-soc-suc-khoe-so-ivie-bac-si-oi-voi-vneid-102260626072918987.htm)

This creates opportunity and risk:

- opportunity: more authoritative longitudinal data will exist;
- risk: VNeID may become the default record surface, so CLARA must add
  interpretation and execution rather than recreate a state portal;
- opportunity: messy transition data creates demand for normalization,
  reconciliation and plain-language explanation;
- risk: direct access to national data is not guaranteed and must not be assumed
  without a formal agreement.

### 6.3 Health literacy is the core consumer problem

A 2025 nationwide online survey of 3,550 adults found problematic health literacy
in 67.3% of respondents while 85.5% had sufficient eHealth literacy. Lower health
literacy was associated with several chronic conditions; results also varied by
education, residence and online information-seeking behavior:
[Health and eHealth literacy in Vietnam](https://pubmed.ncbi.nlm.nih.gov/41830724/).

This means:

- access to an app is not the same as ability to interpret a result;
- medical completeness can worsen anxiety and confusion;
- every CLARA explanation must answer "What does this mean for me?", "How urgent
  is it?", "What should I do next?" and "What can wait?";
- voice, image capture and caregiver participation are more important than dense
  clinical dashboards;
- comprehension and appropriate action are better product metrics than answer
  length or citation count.

### 6.4 Local competitor map

| Product | Observed strengths | Gap CLARA may address |
|---|---|---|
| VNeID electronic health book | national identity and authoritative public infrastructure | interpretation, reconciliation, consumer follow-through |
| Medpro | booking, remote consultations, labs, imaging, home services and payments | cross-provider longitudinal understanding before and after the transaction |
| YouMed | trusted provider marketplace, content, booking and teleconsultation | household continuity and neutral next-step orchestration |
| IVIE | doctors, anonymous questions, records, pharmacy and SOS; VNeID identity | evidence-governed automation and verified episode follow-through |
| eDoctor | information, testing and clinician access | longitudinal decision support and completion tracking |
| Long Châu and pharmacy networks | medicine distribution, vaccination and community reach | neutral medication reconciliation and safety, subject to conflict controls |

Sources:

- [Medpro](https://medpro.vn/)
- [YouMed](https://youmed.vn/dat-kham/bac-si)
- [IVIE](https://ivie.vn/)
- [eDoctor](https://edoctor.vn/)

No reviewed Vietnamese product publicly demonstrates the complete combination of:

- consumer-controlled cross-provider context;
- evidence- and authority-governed recommendations;
- DrugBank-backed medication safety;
- family/caregiver coordination;
- local service execution;
- verified outcomes that improve future recommendations.

This is a market hypothesis, not proof that none exists. It must be refreshed
quarterly.

## 7. Consumer jobs to be done

### 7.1 Highest-frequency jobs

Based on competitor usage research, Vietnamese market structure and health-literacy
evidence, the strongest jobs are:

1. **Something changed. Is it important?**  
   Interpret a symptom, result, prescription, discharge paper or wearable signal
   in personal context.

2. **What is the smallest safe next step?**  
   Decide whether to observe, self-care, contact a clinician, repeat a measurement,
   obtain a test or seek urgent care.

3. **Help me take care of someone else.**  
   Coordinate medicines, records, appointments and warning signs for a child,
   parent or partner.

4. **Help me use a short medical visit well.**  
   Reconstruct the timeline, identify the unresolved questions and leave with a
   clear plan.

5. **Do not let this get lost.**  
   Track a new medicine, test result, referral, follow-up or warning sign until the
   state is known.

6. **Tell me what changed over time, not every number.**  
   Surface meaningful deltas and explain uncertainty.

7. **Help me choose a feasible local path.**  
   Consider location, price, insurance, language, availability and caregiving
   constraints.

### 7.2 Primary segment hypothesis

The most promising starting segment is:

> Vietnamese adults aged approximately 28-55 who coordinate care for themselves
> and at least one family member, use multiple providers or pharmacies, and have a
> recurring medication, abnormal result or follow-up obligation.

Why:

- recurring pain is stronger than general wellness curiosity;
- caregiver behavior is already visible in conversational-AI usage;
- one household can generate multiple legitimate profiles and repeated episodes;
- the value of reconciliation and follow-through is easy to explain;
- the segment can be reached through employers, providers, pharmacies and labs.

This segment definition must be validated through interviews and observed task
completion. Age alone must not be used as a clinical proxy.

### 7.3 Deferred segments

- pure fitness optimization, dominated by sensor ecosystems;
- expensive longevity screening, requiring owned diagnostic pathways and careful
  overtesting controls;
- autonomous diagnosis or treatment selection;
- replacement of emergency services;
- specialist-grade clinical decision support sold directly to consumers;
- research-first professional workbench as the default consumer experience.

CLARA Research can remain a distinct expert mode and evidence service. It should
not determine the consumer information architecture.

## 8. Evidence on engagement and outcomes

### 8.1 The retention problem

A meta-analysis of app interventions for chronic disease estimated pooled dropout
at 43%, with higher attrition in real-world settings:
[App-based chronic-disease attrition](https://pubmed.ncbi.nlm.nih.gov/32990635/).

Systematic reviews identify privacy concerns, poor interoperability, low health
literacy, excessive workload, lack of customization and preference for direct
communication as barriers to personal-health-record adoption:
[ePHR adoption barriers](https://pubmed.ncbi.nlm.nih.gov/32641128/).

Implications:

- CLARA must not require daily manual logging to create core value;
- capture should accept a photo, file, voice note or connector and produce an
  immediate, reviewable result;
- reminders should be sparse, explain why they matter and stop when not useful;
- human help should appear at clinically or behaviorally meaningful points;
- retention is earned by resolved tasks, not streaks or notification volume.

### 8.2 Structured workflows can improve real care

A 2026 randomized trial of 2,069 patients found an LLM preassessment workflow
reduced specialist consultation duration by 28.7%, improved physician-perceived
care coordination and improved patient-reported ease of communication. The system
used structured history taking and a referral report rather than an unconstrained
chat:
[Primary-to-specialist transition RCT](https://pubmed.ncbi.nlm.nih.gov/41555035/).

Implications:

- workflow design and handoff artifacts can matter more than a larger model;
- locally co-designed evaluation can outperform passive fine-tuning on local
  conversations;
- CLARA should measure downstream consultation and coordination outcomes, not only
  answer rubrics.

### 8.3 Personalized nudging needs restraint

Reviews of just-in-time adaptive interventions support the promise of context-aware
personalization but also show heterogeneous methods and incomplete long-term
evidence:

- [JITAI behavior-change review](https://pubmed.ncbi.nlm.nih.gov/39542743/)
- [Context-aware behavior-change review](https://pubmed.ncbi.nlm.nih.gov/33085767/)

Implications:

- a recommender must model receptivity, burden and risk—not maximize messages;
- "no recommendation now" is a valid output;
- every nudge requires a purpose, expiry, suppression rule and measurable outcome;
- personalization should begin with stated constraints and observed completion,
  not opaque psychological inference.

## 9. Global medical knowledge fabric

### 9.1 The "all databases in the world" claim is not feasible

Medical knowledge is distributed across:

- openly accessible metadata;
- license-variable full text;
- regulator labels and safety reports;
- copyrighted systematic reviews and guidelines;
- licensed drug and terminology databases;
- national and provider-controlled clinical records;
- commercial evidence products;
- research registries with access conditions.

No responsible system can truthfully promise complete access. Coverage changes by
country, language, license, update cycle and intended use.

The viable promise is:

> **Auditable coverage of named authoritative sources, with provenance,
> licensing, freshness, applicability and known gaps visible for every released
> conclusion.**

### 9.2 Source-access matrix

| Domain | Preferred sources | Access posture | Product use |
|---|---|---|---|
| Biomedical literature | PubMed metadata/abstracts, Europe PMC | open APIs; abstract/full-text copyright varies | discovery, evidence graph, links and licensed/OA text only |
| Primary trials | ClinicalTrials.gov, WHO ICTRP | open API for CT.gov; WHO portal/web-service conditions | registry status, NCT/registry IDs, results and publication linking |
| Regulatory drug labels | DailyMed, openFDA, Drugs@FDA, EMA EPAR | public data/APIs with disclaimers | labeled indications, contraindications, warnings and provenance |
| Drug normalization | RxNorm/RxTerms | most API data available without license; some source terms restricted | ingredient and product resolution |
| Drug interactions | licensed DrugBank asset | licensed; usage and display must follow agreement | mandatory source for CLARA DDI conclusions |
| Laboratory terminology | LOINC | free for commercial and non-commercial use under its license | test normalization, units and reference-context mapping |
| Conditions/classification | ICD-11 API | CC BY-ND 3.0 IGO | classification and reporting, not a clinical ontology by itself |
| Clinical terminology | SNOMED CT | Viet Nam is not listed as a 2026 member; license/fees may apply | only after affiliate/license review |
| Global guidance | WHO guidelines and limited SMART Guidelines | public; machine-readable coverage is incomplete | global floor, with local adaptation |
| UK guidance | NICE syndication | application, security certification and international license fee; AI use requires approval | optional licensed guideline layer |
| Evidence synthesis | Cochrane | commercial reuse, scraping and AI use restricted without permission | metadata/linking or licensed content only |
| Vietnamese guidance | Ministry of Health documents and APIs where authorized | fragmented publication formats; legal/publication conditions vary | local authority layer after versioned curation |
| Vietnamese patient data | VNeID, insurance, hospitals, labs, pharmacies | formal integration/consent/partnership required | authoritative personal context; never assumed available |
| Wearables | Apple Health, Health Connect and vendor APIs | consent and platform/vendor rules | contextual signals, not autonomous diagnosis |

Official references:

- [NCBI APIs](https://www.ncbi.nlm.nih.gov/home/develop/api/)
- [Europe PMC developer resources](https://europepmc.org/developers)
- [ClinicalTrials.gov API](https://clinicaltrials.gov/data-about-studies/learn-about-api)
- [openFDA API](https://open.fda.gov/apis/)
- [RxNorm API](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html)
- [LOINC license](https://loinc.org/license)
- [ICD-11 API license](https://icd.who.int/docs/icd-api/license/)
- [SNOMED licensing](https://www.snomed.org/get-snomed)
- [WHO SMART Guidelines](https://www.who.int/teams/digital-health-and-innovation/smart-guidelines)
- [NICE syndication API](https://www.nice.org.uk/reusing-our-content/nice-syndication-api)
- [Cochrane website terms](https://www.cochrane.org/website-terms-and-conditions)

### 9.3 Important licensing consequences

- PubMed is not a license to reproduce every abstract or article.
- Europe PMC exposes full text only for a subset; article-level licenses govern
  reuse.
- openFDA states that its data is not uniformly validated for clinical production
  use.
- RxNorm normalizes drug concepts but its interaction API was discontinued; it
  does not replace DrugBank.
- NICE permits AI use only through an approved application and license; training
  on NICE content is not permitted.
- Cochrane prohibits scraping and AI training/validation under ordinary website
  terms.
- SNOMED use in a non-member territory requires license review and potentially
  annual fees or permission for web/mobile distribution.
- VNeID integration is a partnership and public-policy dependency, not an ordinary
  public API assumption.

The knowledge layer therefore needs a source registry and rights ledger before it
needs a larger vector database.

## 10. Regulation, safety and intended use

### 10.1 Viet Nam AI Law

Law 134/2025/QH15 took effect on 2026-03-01 and requires:

- human-centric operation and human oversight;
- provider self-classification before use;
- notification for medium- and high-risk systems;
- transparency when a user interacts with AI;
- incident handling;
- stronger healthcare reliability, real-world safety and health-data protection.

High-risk systems require conformity assessment. The July 2026 official list
specifically identifies AI surgical support/robots in the summarized healthcare
section, rather than automatically classifying every consumer wellness assistant
as high risk. That does not make a health recommender low risk: classification
still depends on intended use, possible harm and whether the system diagnoses,
prevents, monitors or treats.

Sources:

- [Viet Nam AI Law translation](https://en.baochinhphu.vn/viet-nams-law-on-artificial-intelligence-111260715113551787.htm)
- [High-risk AI list](https://baochinhphu.vn/danh-muc-he-thong-tri-tue-nhan-tao-co-rui-ro-cao-102260702152849868.htm)

### 10.2 Medical-device boundary

Decree 98/2021/ND-CP includes software in the medical-device definition when its
intended purpose includes diagnosis, prevention, monitoring, treatment or
alleviation of disease and it meets the remaining criteria:
[Decree 98/2021](https://vanban.chinhphu.vn/?docid=204442&pageid=27160).

Therefore:

- disclaimers do not override actual functionality or marketing;
- "personalized recommendation" can cross the boundary depending on its purpose
  and consequence;
- symptom assessment, medication decisions and monitoring alerts need separate
  intended-use and regulatory analysis;
- CLARA should define modes and claims before implementation, not retrofit safety
  language after launch.

### 10.3 Personal data

Law 91/2025/QH15 and its implementing framework took effect in 2026. Identifiable
health data is sensitive personal data. Product planning must assume:

- explicit, purpose-bound processing;
- data minimization;
- separate consent and revocation by connector and purpose;
- auditable access and disclosure;
- deletion/export and retention policies;
- processor/controller mapping for every partner;
- cross-border processing review;
- special handling for dependent and caregiver profiles.

The system must never infer that one household member may see another's data merely
because they share an account, device or payment method.

## 11. Business model and distribution

### 11.1 Price anchors

Current US/global anchors include:

| Product | Snapshot |
|---|---|
| ChatGPT Health | Health available in Free through Pro; Plus remains USD 20/month |
| Copilot Health | bundled with Microsoft 365 Personal/Family/Premium; Personal USD 9.99/month in the US |
| Guava | free; Premium USD 78/year |
| Oura Advisor | requires ring and membership; membership USD 69.99/year in the US |
| Amazon One Medical | USD 99/year for Prime members; standard USD 199/year; USD 29 message visit |
| Function Health | USD 365/year including extensive labs |
| Verily Me | standard consumer app is free |

Sources:

- [ChatGPT Health availability](https://openai.com/index/health-in-chatgpt/)
- [Microsoft 365 consumer pricing](https://www.microsoft.com/en-us/microsoft-365-copilot/pricing/individuals)
- [Guava pricing](https://guavahealth.com/plans)
- [Oura membership](https://support.ouraring.com/hc/en-us/articles/4409086524819-Oura-Membership)
- [Amazon Health AI pricing](https://www.aboutamazon.com/news/retail/amazon-health-ai-agent-one-medical)
- [Function membership](https://www.functionhealth.com/article/function365)
- [Verily Me standard offering](https://verily.com/solutions/verily-me/contact)

Implications:

- basic question answering cannot support a standalone premium;
- consumers compare CLARA with high-quality free products;
- paid value must come from durable household utility, verified services, human
  review or a sponsor-funded benefit;
- Viet Nam willingness to pay must be researched directly; US price conversion is
  not a pricing strategy.

### 11.2 Viable model hypotheses

Ranked for validation:

1. **B2B2C sponsored household benefit**  
   Employers, providers, insurers or membership programs fund the core service.
   Advantage: trusted distribution and lower consumer acquisition cost.

2. **Provider/lab/pharmacy continuity layer**  
   A partner pays for completed follow-up, medication reconciliation, visit
   preparation or appropriate escalation. Contracts should be linked to engagement
   or outcome measures, not generated messages.

3. **Freemium household subscription**  
   Free interpretation and emergency guidance; paid family coordination, advanced
   longitudinal review, service concierge and clinician review.

4. **Transactional care navigation**  
   Booking or service revenue can subsidize the product, but ranking must remain
   clinically neutral and disclose commercial relationships.

5. **Research/evidence professional tier**  
   CLARA Research can be sold separately to researchers and clinicians. It should
   not subsidize unsafe consumer medical claims.

### 11.3 Distribution moat

The strongest defendable distribution assets are:

- formal VNeID or national-health-data participation;
- hospital, laboratory, insurer and pharmacy integrations;
- Vietnamese clinician and patient co-design;
- family/caregiver network effects;
- locally verified service directory, pricing and eligibility;
- partner handoff and outcome-return APIs;
- trusted institution sponsorship.

Paid acquisition for a generic health chatbot is strategically weak because the
user can open an incumbent assistant immediately and at no additional cost.

## 12. White-space analysis

### 12.1 Where CLARA should not compete

Do not lead with:

- "our LLM is better than ChatGPT";
- "we use many agents";
- "we have RAG";
- "we cite PubMed";
- "we have all world health databases";
- "we provide proactive personalized insights";
- "we are a health super-app";
- "we diagnose anything";
- a clinical-looking dashboard with a proprietary universal health score.

These claims are weak, imprecise or unsafe.

### 12.2 Defensible wedge

The proposed wedge has five mutually reinforcing parts:

1. **Vietnamese health-document intelligence**  
   High-accuracy extraction, normalization and plain-language interpretation of
   local prescriptions, discharge summaries, lab formats and photographed paper.

2. **Household care graph**  
   Consent-aware relationships among people, medicines, providers, episodes,
   responsibilities and handoffs—without merging identities or exposing data.

3. **Local action graph**  
   A current map of appropriate providers, services, tests, pharmacies, prices,
   insurance/benefit constraints, access conditions and completion callbacks.

4. **Recommendation accountability**  
   Every recommendation states why it applies, what evidence and personal facts it
   uses, what could change it, when it expires and how success or harm will be
   observed.

5. **Outcome network**  
   The system learns from confirmed completion, clinician correction, repeated
   results and patient-reported benefit—not from engagement alone.

Large platforms can copy interface features. Reproducing local integrations,
rights-cleared knowledge, family workflows, verified outcomes and institutional
trust is slower.

### 12.3 Consumer experience principle

The home experience should answer three questions:

- **What changed?**
- **What matters now?**
- **What is the next feasible step?**

Chat remains an interaction method, not the product's organizing metaphor.

## 13. Strategic recommendation

### 13.1 Recommended category

Working English category:

> **Personal Health Decision and Follow-through Assistant**

Working Vietnamese category:

> **Trợ lý hiểu và theo sát sức khỏe gia đình**

This wording is intentionally more concrete than "health operating system" and
less clinically expansive than "AI doctor".

### 13.2 Recommended promise

> CLARA brings together the health information you choose, explains what changed
> in plain Vietnamese, helps you choose a safe and feasible next step, and keeps
> track until you know what happened.

### 13.3 Recommended beachhead

Start with three connected episode types:

1. new or changed prescription;
2. abnormal or newly available laboratory result;
3. post-visit/discharge follow-up.

Why these three:

- they begin with concrete, capturable artifacts;
- they have an authoritative source;
- they connect directly to medicine safety and follow-through;
- completion can be observed;
- they recur for chronic conditions and caregivers;
- they allow clear boundaries between explanation, recommendation and clinician
  decision.

### 13.4 Strategic role of CLARA Chat and Research

CLARA Chat becomes the conversational surface over the same episode, evidence and
action state. It should not create an independent medical truth.

CLARA Research becomes the evidence service that:

- builds reproducible searches;
- separates guideline, systematic review, primary trial and commentary;
- preserves PMID, DOI, NCT and study design;
- detects retractions, contradictions and applicability gaps;
- produces an evidence packet consumable by the recommendation layer;
- remains an expert mode for researchers and clinicians.

Neither multi-agent orchestration nor dynamic prompting should be marketed as
consumer differentiation. They are implementation choices that must outperform a
strong single-agent baseline on safety, correctness, latency and cost.

## 14. Validation agenda before major build

### 14.1 Primary discovery

Conduct at minimum:

- 20 household health coordinators;
- 10 adults with a recurring medication;
- 10 adults with a recent abnormal lab or hospital discharge;
- 8 clinicians across primary care, pharmacy and common chronic specialties;
- 5 employers/insurers/benefit buyers;
- 5 laboratories or provider-network operators.

Use observed artifacts and task walkthroughs, not only opinion questions.

Required questions:

- What happened the last time a result or prescription changed?
- Who noticed, explained, paid, booked and followed up?
- Which steps were forgotten or repeated?
- What information was unavailable at the decision moment?
- What would the user trust software to do automatically?
- When is a human required?
- What outcome would justify payment?

### 14.2 Smoke-test prototypes

Test without building the full platform:

1. prescription photo → reconciled medicine list → DrugBank DDI review → feasible
   next step;
2. lab PDF/photo → meaningful delta → one appropriate follow-up action;
3. discharge paper → household task assignment → completion verification;
4. caregiver share → consent and boundary comprehension;
5. overnight symptom concern → safe immediate response and escalation.

### 14.3 Pass criteria

Proceed only if:

- at least 70% of target participants can state the next step correctly after the
  flow;
- at least 60% prefer CLARA's artifact-to-action workflow over using a general
  chatbot with the same document;
- dangerous misunderstanding is zero in the pilot's release set;
- at least one distribution partner accepts a measurable pilot outcome;
- median manual effort is under two minutes for the first useful result;
- users understand who produced each recommendation and whether it is medical
  advice.

These are product gates, not clinical-efficacy claims.

## 15. Research-backed decision

The research rejects a broad "ChatGPT Health competitor with all world databases"
as the initial strategy. That position is too broad, already crowded and impossible
to substantiate.

The recommended strategy is:

> Build the Vietnam-first interpretation, decision and follow-through layer for
> ordinary people and families, powered by a rights-cleared global knowledge
> fabric and locally executable care network.

The next specification revision should:

- replace generic Care Loop language with the concrete three-question consumer
  experience;
- define the three beachhead episode types;
- make the source-rights ledger and local action graph first-class architecture;
- define regulatory intended-use boundaries by workflow;
- separate consumer Chat from expert Research while sharing evidence services;
- add household consent and caregiver boundaries;
- add recommendation expiry, counterfactuals and outcome verification;
- make integration and distribution milestones phase gates;
- remove any implication that multi-agent complexity or database count is the
  product moat.

No product specification should be treated as final until these changes are made
and the primary-discovery assumptions are tested.
