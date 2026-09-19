# A4 — Academic literature map: reversible pseudonymisation at the tool boundary (2023–Sep 2026)

Excavated 2026-09-20. Quotes are verbatim where marked with ». Grades: [A] reproduced/strong · [B] single study · [C] position/design · [D] preprint claim unverified.

---

## PART 1 — PAPER CARDS

### 1.1 Hou et al. — "A General Pseudonymization Framework for Cloud-Based LLMs: Replacing Privacy Information in Controlled Text Generation"
- **Venue/year:** arXiv 2502.15233v1, 21 Feb 2025 (v1 only as of fetch). Authors: Shilong Hou, Ruilin Shang, Zi Long, Xianghua Fu, Yin Chen (Shenzhen).
- **URL:** https://arxiv.org/abs/2502.15233
- **Mechanism (own words):** Three stages — detection (NER + patterns), candidate generation (an LLM proposes same-type replacements), replacement — applied to the prompt; the cloud LLM answers over the pseudonymised prompt; then the SAME three stages are run in reverse over the output, reusing the forward mapping, and restoration is direct string substitution. A local 1.5B Qwen is fine-tuned on 20k samples to do the detection/generation stages.
- **Consistency:** » "the detection and candidate generation in the restoration process can refer to the results of the pseudonymization process, while the replacement operation itself is identical." Restoration: detected entities q^j in output Y′ are » "directly replac[ed] with p′^j … resulting in the final output Y."
- **Structured outputs / tool calls:** NOT addressed. Only plain-text NLP tasks.
- **Key numbers (conditions):** 1,000-sample test subsets of SQuAD 2.0, XSum, CNN/DailyMail, SAMSum, MNLI, WMT14 de-en. Cloud LLM simulated by Qwen2.5-14B-Instruct; local = Qwen2.5-1.5B-Instruct (20k fine-tune samples, 3 epochs, lr 1e-4). Utility retained relative to the un-pseudonymised 14B baseline: ≥95% on SQuAD 2.0 / CNN-DM / SAMSum / MNLI; ≥90% on XSum; ~85% on WMT14. Privacy metric = 1 − cosine(X, X′) with all-mpnet-base-v2. **No seeds reported. No multi-turn. No agent.**
- **Limitation (verbatim):** » "The primary limitation of this work is that the pseudonymization process is implemented through three relatively independent processing stages rather than an end-to-end machine learning approach." … » "For the sake of experimental efficiency, this work employs the same entity replacement method in both the restoration and pseudonymization processes." … » "certain tasks, such as text continuation, remain unexplored … it may generate entities not present in the input text."
- **Grade:** [B] single study, single model pair, no seeds. Relevant to items 1, 5 (consistency within one prompt only), 4 (same-type realistic fakes).

### 1.2 Xiao et al. — "Say Something Else: Rethinking Contextual Privacy as Information Sufficiency"
- **Venue/year:** arXiv 2604.06409v1 [cs.CR], 7 Apr 2026. Authors: Yunze Xiao, Wenkai Li, Xiaoyuan Wu, Ningshan Ma, Yueqi Song, Weihao Xuan (CMU, MIT, U Tokyo, 2077AI).
- **URL:** https://arxiv.org/abs/2604.06409
- **Mechanism (own words):** Frames "what should the model say instead" as an Information Sufficiency task; compares four disclosure strategies the model can adopt when composing a reply (no protection, suppression, generalisation, pseudonymisation = substitute a plausible alternative). A simulated receiver asks up to two follow-up questions — the "probed" multi-turn condition — and leakage is re-scored after the follow-ups.
- **Metric:** IS-AD = (1 − HLS) × Util; HLS = Headline Leakage Score (1.0 exact, 0.5 category, 0 none).
- **Key numbers (conditions):** 792 scenarios × 7 frontier LLMs (Gemini 3.1 Pro, GLM-5, GPT-5.4, Kimi K2.5, MiniMax M2.1, MiniMax M2.5, Qwen3-8B) = 22,176 transcripts. Under probing: pseudonymisation IS-AD 0.764 (best), suppression 0.730, generalisation 0.664 (Pareto-dominated by the no-protection baseline). Vulnerability gap under follow-ups Δvuln: generalisation +11.8 pp (up to +16.3 pp on Gemini); pseudonymisation +3.9 pp (most stable).
- **Pareto claim (verbatim):** » "Pseudonymization emerges as the only strategy for which all seven models consistently reside near the Pareto frontier."
- **Limitation:** LLM judges; receiver non-adversarial, capped at two follow-ups; utility = functional equivalence only, » "not downstream consequences"; U.S.-centric norms.
- **Grade:** [B] single study; 7 models is broad but one judge design. NOTE: this is the MODEL choosing to pseudonymise in its own reply, not a gateway substituting before the model — the finding transfers only as evidence that a plausible-substitute strategy degrades least under multi-turn probing (item 5).

### 1.3 Deußer et al. — "On the Impact of Anonymization on the Performance of Large Language Models"
- **Venue/year:** arXiv 2609.11335v2 [cs.CL], 15 Sep 2026 (preprint). Authors: Tobias Deußer, Max Hahnbück, Lorenz Sparrenberg, Tobias Uelwer, Christian Bauckhage, Rafet Sifa (U Bonn, Fraunhofer IAIS, Microsoft Germany, Lamarr).
- **URL:** https://arxiv.org/abs/2609.11335
- **Mechanism (own words):** Takes 11 existing benchmarks (science reasoning, MedQA, emotional intelligence, commonsense, IFEval, MUSR multi-step, RGB retrieval-augmented, TruthfulQA, translation …), anonymises the INPUT with five techniques, and re-scores the same models. Techniques: pseudonymisation "London"→"<LOC>-1" (consistent identifier per entity), generalisation "[CITY]", masking "Lo****", randomisation "Xj92Lp", redaction "[REDACTED]".
- **Key numbers (conditions):** 6,210 unique samples (≤500–1,000 per benchmark), temperature 0. Average drop across benchmarks: Qwen2.5-72B −6.9 pp; Teuken-7B −2.3 pp; GPT-4o-mini "substantial". Per task under pseudonymisation: RGB (RAG) −22 to −47 pp (the paper's own word: catastrophic); MedQA/MMLU-Pro/HellaSwag −3 to −10 pp; ARC, IFEval <5 pp; TruthfulQA IMPROVES (+8 pts Llama-3.1). Technique comparison (GPT-4o-mini on MedQA/MUSR/RGB): pseudonymisation and randomisation/masking preserve most; generalisation and redaction give » "largest performance drops".
- **Consistent vs inconsistent / realistic vs placeholder:** NOT compared. Their "pseudonymisation" is a TAGGED placeholder ("<LOC>-1"), not a format-preserving realistic fake. So the number is a ceiling on the damage of an entity-tagged scheme, not a measurement of a realistic-fake scheme.
- **Limitation (verbatim):** » "For most benchmarks, a maximum of 500 samples were randomly selected" … » "Domains such as coding and mathematics were excluded, as they typically do not involve PII".
- **Grade:** [B] single study, broad (11 benchmarks, several models), no seeds (temp 0), no agent/tool axis. THE number that contradicts "a few pp": −22…−47 pp on retrieval-augmented tasks, because the retrieved passages and the question no longer share surface forms — which is exactly the shape of a tool RESULT coming back masked while the model's question was masked with a different key (item 3).

### 1.4 Zharmagambetov et al. (Meta FAIR) — "AgentDAM: Privacy Leakage Evaluation for Autonomous Web Agents"
- **Venue/year:** arXiv 2503.09780, v1 Mar 2025 → v3 1 Oct 2025; presented at ICML 2025 Workshop on Computer-Use Agents; OpenReview id SP0X5rm6f3. Authors: Arman Zharmagambetov, Chuan Guo, Ivan Evtimov, Maya Pavlova, Ruslan Salakhutdinov, Kamalika Chaudhuri.
- **URL:** https://arxiv.org/abs/2503.09780 · code https://github.com/facebookresearch/ai-agent-privacy
- **Mechanism (own words):** 246 web-navigation tasks on WebArena/VisualWebArena (Reddit, GitLab, Shopping). Human annotators write a "data seed" (plot + sensitive_data), an LLM expands it into user_data; the agent must complete the task while using sensitive data only if necessary ("data minimization in action"). Six sensitive categories (contact, religious/political, employment, financial, education, medical). Defense = a reasoning-enhanced system prompt.
- **Two axes:** Utility = task success rate; Privacy = 1 − leakage rate.
- **Key numbers (verbatim table):** GPT-4o 0.455/0.638 → with defense 0.415/0.915; GPT-4o-mini 0.341/0.541 → 0.321/0.821; GPT-4-turbo 0.480/0.748 → 0.423/0.894; Llama-3.2-90b 0.321/0.776 → 0.293/0.923; Llama-3.3-70b 0.402/0.882 → 0.386/0.939; Claude-3.5-Sonnet 0.350/0.902 → 0.309/0.935. **Utility cost of the privacy defense: −1.6 to −5.7 pp task success** (n = 246 tasks, single run per model reported, no seeds).
- **Verbatim on the utility cost:** » "With reasoning-enhanced system prompt, privacy performance noticeably increases for all models but still does not go above 94%. Moreover, we observe a degradation in task performance when this mitigation is applied." » "Close inspection indicates this mostly occurs due to false denial-of-service (e.g., the model refuses to comment on a post)."
- **Verbatim limitation/position:** » "asking LLMs directly about privacy may lead to an overestimation of privacy 'in action', and hence to evaluate privacy properly, we do need end-to-end measurements of data minimization in AI agents."
- **Grade:** [B] single study, but the ONLY agent benchmark found that publishes utility AND privacy per model with and without a mitigation. NOTE: the mitigation is a PROMPT, not a gateway substitution — the agent still SEES the real data. So AgentDAM measures "does the agent refrain", not "does the agent behave identically when it never sees the value". Items 13 (partially), 2 (tool-call args are real because the agent holds real data).

### 1.5 Siyan et al. — "PAPILLON: Privacy Preservation from Internet-based and Local Language Model Ensembles"
- **Venue/year:** NAACL 2025 Long (aclanthology 2025.naacl-long.173); arXiv 2410.17127 v1 Oct 2024 → v3 25 Mar 2025. Columbia + Stanford.
- **URL:** https://arxiv.org/abs/2410.17127
- **Mechanism (own words):** Two local-model modules: a Prompt Creator rewrites the user query into a PII-free prompt for the remote model; an Information Aggregator combines the remote answer with the ORIGINAL query locally to produce the final answer. Both prompts are optimised jointly with DSPy MIPROv2 on a metric = quality − leakage + well-formedness (150 train / 150 val examples). No mapping table, no restoration step: the remote model never gets a pseudonym, it gets a rewritten query.
- **Dataset:** PUPA — 901 WildChat instances with explicit PII (237 original + 664 newly annotated).
- **Key numbers:** Llama-3.1-8B local + GPT-4o-mini remote: quality preserved 85.5%, leakage 7.5%. Baselines on PUPA-TNB: GPT-4o-mini unredacted 88.2%; GPT-4o-mini REDACTED 77.2% (i.e. naive redaction costs 11 pp of quality); Llama-3.1-8B alone 81.5%. Llama-3.2-1B: 58.0% / 39.3% leakage; Mistral-Small: 85.3% / 27.4% leakage. Quality and leakage are LLM-judged.
- **Restoration:** none — » the Information Aggregator "aggregates C_R and the original query q"; nothing is put back into the remote model's view and no tool calls exist.
- **Limitation (verbatim):** only queries » "where disclosure of PII is explicit"; » "metrics rely heavily on large language models"; » "PAPILLON does not always produce the most intuitive, privacy-conscious prompts".
- **Grade:** [B] peer-reviewed single study; relevant to items 1 (answer is "reversed" by re-aggregation, not by mapping), and as the source of the ONE clean redaction-cost number: −11 pp quality for naive redaction on PUPA.

### 1.6 Vīksna & Skadiņa (Tilde / U Latvia) — "Anonymise: A Tool for Multilingual Document Pseudonymisation"
- **Venue/year:** RANLP 2025, pp. 1327–1332, DOI 10.26615/978-954-452-098-4-154. Demo paper.
- **URL:** https://acl-bg.org/proceedings/2025/RANLP%202025/pdf/2025.ranlp-1.154.pdf
- **Mechanism (verbatim — THE inflected-pseudonym recipe):** » "The pseudonymisation using grammatically suitable substitutes is challenging for morphologically rich languages, as the tool should provide the pseudonym in the correct form, e.g., inflection, gender, and number. The Stanza (Qi et al., 2020) library is used to determine the grammatical features of each token. … For multi-word entity mentions, grammatical features of the headword are used. The pseudonyms are selected from a pre-defined list of candidate entities. The list of substitutes was obtained from the WMT monolingual news datasets (Kocmi et al., 2024) by applying the NER and Stanza parser. Extracted named entities are stored together with their grammatical information as potential pseudonym candidates."  I.e. they do NOT inflect a lemma; they harvest already-inflected surface forms from a corpus with their features and pick a candidate whose features match the original mention's headword.
- **Consistency:** related-work mention only — » "Text de-identification systems may include a linker component to produce global pseudonyms, consistent on a document level … a named entity recognition, an entity linking, and a substitution engine (Francopoulo and Schaub, 2020)."
- **Languages:** EN, ET, LT, LV (MultiLeg). **Russian: not covered.**
- **Numbers:** NER only — MultiLeg P/R/F1 ALL 0.78/0.93/0.85 vs EC tool 0.73/0.29/0.42 and MAPA 0.72/0.30/0.42; TAB token recall R_di+qi 0.950 vs TAB-Longformer 0.919, precision 0.551. **No measurement of the morphology-aware substitution itself** (no agreement-error rate, no downstream retention).
- **Grade:** [C]/[B] — a demo paper; the substitution mechanism is described, not evaluated.

### 1.7 Vīksna & Pinnis — "Pseudonymisation for Morphologically Rich Languages"
- **Venue/year:** TSD 2026 (Text, Speech and Dialogue), LNCS, Springer; DOI 10.1007/978-3-032-37249-9_20 (chapter 20). Paywalled; only the abstract and reference list were reachable.
- **URL:** https://link.springer.com/chapter/10.1007/978-3-032-37249-9_20
- **Abstract (verbatim):** » "Existing approaches typically rely on masking techniques or pseudonymise PI using replacement lists or random surrogates. For analytic languages, such as English, this approach works well; however, in morphologically rich languages, where words exhibit complex inflectional paradigms, pseudonyms must agree in case, number, and gender with the syntactic role in the sentence. We introduce a method that produces pseudonyms for PI entities while maintaining grammatical compatibility with the surrounding text. We evaluate our approach on named entity recognition and sentiment analysis tasks in English and Polish. Our results show that the data pseudonymised using our morphology-aware pseudonymisation method remains useful for the downstream tasks."
- **References visible:** Sweeney 1996 (Scrub), Walkowiak et al. 2023 "Anonymizer for Polish language", Woliński 2006 Morfeusz (Polish morphological analyser) — so the Polish arm uses Morfeusz-style analysis.
- **Numbers:** not reachable (paywall). The claim is "remains useful for downstream tasks" (NER + sentiment, EN + Polish) — the SAME shape as Yermilov 2023, measured on training-data utility, NOT on an LLM reading the text at inference and NOT on a tool call.
- **Grade:** [D] until the chapter is read — the only peer-reviewed paper found whose TITLE is the inflection problem. **Nothing for Russian**, and nothing about the reverse direction (a model re-inflecting the fake, item 7).

### 1.8 Yermilov, Raheja, Chernodub (Grammarly) — "Privacy- and Utility-Preserving NLP with Anonymized Data: A case study of Pseudonymization"
- **Venue/year:** arXiv 2306.05561v1, 8 Jun 2023; TrustNLP @ ACL 2023.
- **URL:** https://arxiv.org/abs/2306.05561
- **Mechanism (own words):** Three pseudonymisers — NER-PS (spaCy/FLAIR detection + Wikidata replacement matched on gender & language-of-origin for persons, industry & country for orgs, type & country for locations, random draw within the filter), Seq2Seq-PS (BART-base trained on NER-PS outputs), LLM-PS (GPT-3 1-shot extraction + ChatGPT 1-shot replacement, "different entities of same type"). Utility measured by TRAINING downstream models on pseudonymised text.
- **Key numbers:** CNN/DailyMail summarisation (BART-base) ROUGE-1/2/L: original 42.82/20.13/36.33; NER-PS(spaCy) 41.93/19.38/29.36; NER-PS(FLAIR) 40.25/18.04/27.97; Seq2Seq-PS(FLAIR) 36.04/15.07/24.73; LLM-PS 38.62/16.57/26.34. IMDB classification (BERT-base) F: 88.42 original vs 88.06–88.15 pseudonymised (≈ −0.3 pp). So: classification is nearly free; summarisation loses 1–7 ROUGE-1 and ~7–12 ROUGE-L.
- **Limitation (verbatim):** » "Using closed-source LLMs may not be an acceptable solution for many settings since it requires sending a (potentially sensitive) text to a third-party API"; English only; PERSON/LOCATION/ORG only.
- **Grade:** [B] — the canonical "realistic same-type fake" utility study; training-time utility, not inference-time agent utility.

### 1.9 Chen et al. — "Hide and Seek (HaS): A Lightweight Framework for Prompt Privacy Protection"
- **Venue/year:** arXiv 2309.03057v1, 6 Sep 2023 (no later version). Code/datasets open-sourced.
- **URL:** https://arxiv.org/abs/2309.03057
- **Mechanism (own words):** A small local Hide-Model (either spaCy NER + label tags, or a fine-tuned BLOOMZ-560M/1.7B that GENERATES a substituted sentence) replaces private entities in the prompt; the cloud LLM does the task; a local Seek-Model (BLOOMZ, LoRA) takes (original input, anonymised input, cloud output) and re-writes the cloud output with the real entities. The training data are made by prompting a big LLM with » "Substitute given words in the text into other random words." — i.e. random SAME-TYPE substitutes ("FBI"→"CIA", "August 10, 2023"→"September 15, 2025", "Washington DC"→"New York City"). Restoration is GENERATIVE (a model re-writes), not a mapping lookup.
- **Scope (verbatim):** » "The text conversion tasks include but are not limited to machine translation, polishing, summarization, and other tasks, but do not include knowledge retrieval, article continuation, and the like."
- **Key numbers:** Classification (BBC news, micro-F1): no-obscure 91.20; generative 560m 91.36 (+0.17%); generative 1b7 90.98 (−0.24%); label-based 90.14 (−1.16%). Translation (DeepL reference) ROUGE-L: no-obscure 54.69; generative 560m 51.73; label-based 560m 50.89; generative 1b7 53.33; label-based 1b7 52.70 — i.e. −1.4 to −3.8 ROUGE-L AFTER the seek model restores. Adversarial black-box recovery similarity (difflib) 0.31–0.33 (lower = harder to recover). n not stated per table; no seeds.
- **Limitation (verbatim):** » "Since HaS replaces the entity words in the prompt, it leads to tasks that rely on the precise semantics of the replaced entity words, such as knowledge retrieval and text continuation, being unable to use HaS." » "it cannot hide other words and sentence structures, such as verbs and other non-named entity words".
- **Grade:** [B] single study, small models, no multi-turn, no tool calls. Historic anchor for item 1 (reversible answer), and the first paper to state in print that entity substitution breaks retrieval-dependent tasks — which Deußer 2026 later measures.

### 1.10 Li & Xu (Case Western) — "ToolMinimize: Auditing and Rewriting LLM Agent Tool Calls to Minimize Privacy Exposure"
- **Venue/year:** PST 2026 (Privacy, Security and Trust, Ottawa, 26–28 Aug 2026); arXiv 2608.24957v1, 25 Aug 2026.
- **URL:** https://arxiv.org/abs/2608.24957
- **Mechanism (own words):** Middleware between argument construction and tool execution; classifies argument fields (40+ regexes + entity extraction + semantic analysis, 10 categories, 4 sensitivity levels per GDPR Art. 9) and rewrites them by removal / generalisation / substitution with schema-valid synthetic values / truncation, honouring per-field `minimum_necessary` annotations in the tool schema. **Not reversible: the tool receives the minimised data, never the real value.** This is the OPPOSITE design from a pseudonymisation gateway — it assumes the tool should NOT get the real value.
- **Key numbers:** » "81–88% of tool calls contain unnecessary PSD under default prompts"; with explicit privacy instructions still 36–76% (GPT-4o 81.5%→36%; Claude 3.5 Sonnet 87.5%→50%; Llama-3.3-70B 81%→76%); privacy cost reduction 81.2–92.0% on 307 live tool calls (270 scenario×model pairs, 90 author scenarios + 25 real MCP schemas); » "100% argument-level task validity" = schema-valid and all minimum_necessary fields kept. End-to-end: » "16 of 20 scenarios (80%) return functionally equivalent results" against mock endpoints.
- **Limitation (verbatim list):** » "TCR scope: schema-validity, not end-to-end (80%; 4/20 maps failures)", » "user agency: ToolMinimize decides unilaterally", » "false positives: on benign inputs detection fires on 20% and rewriting on 10%", » "defense: 1/10 encodings (field splitting) still evades".
- **Grade:** [B] single study, mock endpoints. Relevant as the only paper found that PUBLISHES "argument-level task validity" as a metric — a name for item 2's measurement, even though its design keeps tools blind. Its 80% end-to-end equivalence is the honest number for "an intervention at the tool boundary changes outcomes one time in five".

### 1.11 Shao et al. — "PrivacyLens: Evaluating Privacy Norm Awareness of Language Models in Action"
- **Venue/year:** NeurIPS 2024 Datasets & Benchmarks; arXiv 2409.00138 v1 29 Aug 2024 → v3 14 Mar 2025.
- **URL:** https://arxiv.org/abs/2409.00138
- **Mechanism (own words):** Privacy-sensitive seeds (contextual-integrity tuples) → expanded into vignettes → into agent trajectories where an LM agent with tools (email, messaging) must complete a task; leakage judged at the ACTION level (what the agent actually sent), not the probe level. 493 seeds (per Privacy-in-Action's reuse).
- **Key numbers (abstract):** » GPT-4 leaked in 25.68% and Llama-3-70B in 38.69% of cases even when instructed to be privacy-conscious. Helpfulness is scored (1–3) but the abstract does not present a utility-vs-privacy trade-off table.
- **Limitation (verbatim):** » "(1) the contextual and long-tailed nature of privacy-sensitive cases, and (2) the lack of evaluation approaches that capture realistic application scenarios."
- **Grade:** [A]-ish as a benchmark (peer-reviewed, reused by 2025–26 work); NOT a pseudonymisation study — measures whether the agent leaks by norm, not whether a gateway changes its behaviour.

### 1.12 Wang et al. (Wuhan U + Microsoft) — "Privacy in Action: Towards Realistic Privacy Mitigation and Evaluation for LLM-Powered Agents"
- **Venue/year:** arXiv 2509.17488v1, 22 Sep 2025.
- **URL:** https://arxiv.org/abs/2509.17488
- **Mechanism (own words):** PrivacyChecker — a module that extracts information flows (sender, recipient, subject, type, transmission principle), judges each flow Yes/No for contextual appropriateness, optionally under a customisable guideline; applied to the agent's outbound actions. PrivacyLens-Live: 493 static PrivacyLens cases turned into live multi-tool environments (Gmail + Notion, 150 samples; extended with Calendar/Slack/Messenger, 36 cases with 2- and 3-tool chains).
- **Key numbers:** Leak rate / helpfulness (1–3): GPT-4o 33.06% → 8.32%, helpfulness 2.69 → 2.45; DeepSeek-R1 36.08% → 7.30%, 2.58 → 2.35; Qwen3-14B 37.52% → 15.91%, 2.65 → 2.49. So the mitigation costs 0.16–0.24 helpfulness points on a 3-point scale (≈ 5–8% of the scale).
- **Pseudonymisation:** » not mentioned. **Tool choice/argument change:** no explicit statement; case study reports » "noisier trajectories with failed or redundant tool calls" in live settings, attributed to implementation noise.
- **Limitation:** limited tool integrations; residual leakage = incorrect judgment 18/36, judge-action gap 11/36, extraction failures 3/36; higher leakage in 3-tool than 2-tool chains.
- **Grade:** [B]. Relevant to item 13 as a second "mitigation costs helpfulness" number, but for a JUDGE-style mitigation, not substitution.

### 1.13 Karpova (HSE MIEM) — «О реализации метода обезличивания персональных данных»
- **Venue/year:** Вестник компьютерных и информационных технологий № 6, 2013.
- **URL:** https://publications.hse.ru/pubs/share/folder/6lznn8cw57/83784965.pdf
- **What it is:** relational-DB shuffling (перемешивание) — » "Значения каждого атрибута нумеруются и разбиваются на подмножества. Внутри каждого i-го подмножества данные перемешиваются путем циклической перестановки". Reversible by parameters. **Not text, not NER, no morphology.** Included only as evidence of where the Russian «обезличивание» literature sits: structured records, the 152-ФЗ / Роскомнадзор приказ №996 method list (введение идентификаторов, изменение состава или семантики, декомпозиция, перемешивание).
- **Grade:** [C] — irrelevant to text; cited to state honestly that the Russian-language academic strand on free-text pseudonymisation with declension was NOT found.

### 1.14 Baroud et al. (DFKI / TU Berlin / Charité) — "MultiGraSCCo: A Multilingual Anonymization Benchmark with Annotations of Personal Identifiers"
- **Venue/year:** LREC 2026 (aclanthology 2026.lrec-1.529); arXiv 2603.08879 v1→v3 (14 Mar 2026); data on Zenodo.
- **URL:** https://arxiv.org/abs/2603.08879
- **Mechanism (own words):** 63 German synthetic clinical texts (GraSCCo, ~43k tokens, 1,438 PHI + 1,140 new indirect-identifier annotations) machine-translated by GPT-4.1 into 10 languages incl. **Russian, Polish, Ukrainian**, with the instruction that » "Named entities (e.g., patient names, hospitals, cities, locations) must be translated and replaced with natural-sounding random {target_language} equivalents." Native speakers checked 10 documents per language.
- **Morphology:** the paper says names are » "adapted culturally, contextually, and linguistically to the target language" but there is **no explicit treatment of case/gender agreement or transliteration** for the Slavic languages — it is delegated to the translating LLM and not validated separately.
- **Numbers:** de-identification baselines (mmBERT) — Russian micro-F1 0.850 monolingual / 0.867 multilingual; Polish 0.839 / 0.874.
- **Limitation (verbatim):** » "the patient's and doctor's names are sometimes identical" (inherited from GraSCCo); » "our translated corpus may not follow linguistic or stylistic features unique to the target languages and contexts."
- **Grade:** [B]. The ONLY peer-reviewed 2026 anonymisation benchmark found that contains Russian; it measures DETECTION, not substitution quality, and not declension.

### 1.15 Lahjouji & Colaco — "Agents That Know Too Much: A Data-Centric Survey of Privacy in LLM Agents"
- **Venue/year:** arXiv 2606.26627v1, 25 Jun 2026.
- **URL:** https://arxiv.org/abs/2606.26627
- **What it says (verbatim):** defence category "privacy-preserving transformations": » "Redaction removes sensitive spans, pseudonymization replaces identifiers, abstraction replaces a value with a less specific one, and summarization retains the substance while dropping detail." … » "The common limitation is that a transformation strong enough to protect can be strong enough to break the task." Cites MaskSQL (Abedini 2025) for abstraction in text-to-SQL and Zeng 2025 for synthetic substitution in retrieval. On evaluation: » "all of this against utility, since a trivial agent that returns nothing leaks nothing" and » "Few evaluations cover more than two or three of these dimensions"; its Table 6 has no utility column. On memory: » "It persists across sessions, so data written for one user or task can resurface for another." On tools: » "The sensitive units are the arguments the agent passes, the responses it receives, and the side effects the calls produce."
- **Open problems (its §8, paraphrased list):** policy placement; composing guarantees; **preserving utility**; **detecting violations in intermediate channels (tool arguments, memory writes)**; contextual reasoning; forgetting/revocation; enforcement outside the model; third-party capabilities (MCP); end-to-end evaluation.
- **Grade:** [C] survey. Useful because it independently names items 2, 3, 8 and 13 as OPEN and cites no paper that does reversible substitution at the tool boundary.

### 1.16 Charpentier & Lison — "Re-identification of De-identified Documents with Autoregressive Infilling"
- **Venue/year:** ACL 2025 main long (aclanthology 2025.acl-long.60); arXiv 2505.12859, 19 May 2025.
- **URL:** https://arxiv.org/abs/2505.12859
- **Mechanism (own words):** attacker holds a background corpus; a retriever picks passages relevant to the masked document; an infilling LM predicts the content of each masked span. Evaluated on Wikipedia biographies, court rulings, clinical notes.
- **Key numbers:** » up to 80% of masked text spans recovered; recovery rises with background-knowledge availability.
- **Masks vs surrogates:** NOT compared — the attack targets MASKS ([REDACTED]-style). It says nothing about whether a realistic surrogate is easier or harder to see through.
- **Grade:** [A]-ish (ACL main) for the claim "masking ≠ anonymisation given background knowledge"; silent on pseudonyms.

### 1.17 Lermen, Paleka, Swanson, Aerni, Carlini, Tramèr — "Large-scale online deanonymization with LLMs"
- **Venue/year:** arXiv 2602.16800 v1 18 Feb 2026 → v2 25 Feb 2026.
- **URL:** https://arxiv.org/abs/2602.16800
- **Mechanism (own words):** » "(1) extract identity-relevant features, (2) search for candidate matches via semantic embeddings, (3) reason over top candidates to verify matches and reduce false positives." Works on raw pseudonymous user text (Hacker News ↔ LinkedIn, Reddit ↔ Reddit, single user split temporally).
- **Key numbers:** » "up to 68% recall at 90% precision compared to near 0% for the best non-LLM method."
- **Relevance:** the linkage signal is CONTENT and STYLE, not the identifier — i.e. the exact re-identification channel a name-substitution gateway leaves untouched. » "practical obscurity protecting pseudonymous users online no longer holds".
- **Grade:** [B] single study, strong authors; numbers depend on candidate-pool construction.

### 1.18 Li, Wen, Li — "LLM Anonymization Against Agentic Re-Identification" (AURA)
- **Venue/year:** arXiv 2605.30848 v2, 1 Jun 2026.
- **URL:** https://arxiv.org/abs/2605.30848
- **Mechanism:** » "an LLM-powered mask-reconstruct framework that decouples privacy localization from utility-preserving reconstruction and selects candidates with adversarial privacy and utility-retention checks." Threat model: » "Agentic LLMs with web search change the threat model for text anonymization: weak contextual cues can become cross-referenceable evidence for re-identification". Evaluated on real-user interview transcripts.
- **Numbers:** not in the abstract; body not fetched. **Grade:** [D].

### 1.19 Deußer et al. — "A Survey on Current Trends and Recent Advances in Text Anonymization"
- **Venue/year:** arXiv 2508.21587v1, Sep 2025.
- **URL:** https://arxiv.org/abs/2508.21587
- **What it says (verbatim):** on LLM anonymisers » "LLMs can remove or replace identifiable spans while preserving fluency, though consistency and completeness remain challenges." Consistent pseudonym replacement is treated as a TOOL feature (ANOPPI » "assigning identifiers for consistent pseudonym replacement"; PSILENCE » "employs NER and coreference resolution for consistent entity replacement"), never as a measured property. On residual risk: » "quasi-identifiers, contextual information, and even linguistic style can also lead to re-identification". Open questions list: multilingual/low-resource, DP vs fluency, LLM-driven re-identification, stylometric fingerprints — **no item for agents, tool calls, multi-turn, or reversibility**.
- **Grade:** [C] survey. Its silence is the finding: as of Sep 2025 the anonymisation community's own map has no square for the tool boundary.

### 1.20 Vīksna & Skadiņa is 1.6; Xu & Li ToolMinimize is 1.10 — cross-ref only.

---

## PART 2 — THEORY: why reversible pseudonymisation ≠ anonymisation (Q3) and the two named problems (Q4)

### 2.1 EDPB — "Guidelines 01/2025 on Pseudonymisation" (adopted 16 Jan 2025, version for public consultation)
- **URL:** https://www.edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf
- **§22 (verbatim):** » "Pseudonymised data, which could be attributed to a natural person by the use of additional information, is to be considered information on an identifiable natural person, and is therefore personal. This statement also holds true if pseudonymised data and additional information are not in the hands of the same person."
- **§95 — linkage raises attributability (verbatim):** » "those means may be applied not only to individual pseudonymised records, but also to the result of a linkage of records relating to the same data subject. Such linkage may happen within the same dataset and with other data that were pseudonymised in the same or a similar way. Linked data might allow for attribution to a specified person while individual data records do not, because it contains more attributes to match with other data."
- **§101 — quasi-identifiers (verbatim):** » "If a combination of those attributes are sufficient to attribute at least part of the pseudonymised data to data subjects, then they are called quasi-identifiers. Demographic data are prime examples of such attributes: age, gender, languages spoken, marital or family status, profession, income. … This would enable them to attribute the data to those persons without the use of the pseudonymisation secrets, i.e. without the need to reverse the pseudonymising transformation."
- **§115–119 — the SCOPE of consistency is a design choice with a named risk ladder (verbatim):** » "controllers need to define which sets of personal data will be pseudonymised consistently. For example, they may decide to pseudonymise all data they collect on the same day consistently … but preventing linkage of records of data collected on different days." §116 person pseudonyms: » "The risk of unauthorised attribution is comparatively high. Correspondingly, this type of pseudonymisation may not significantly reduce the severity of risks associated with unlawful or unauthorised disclosure of the pseudonymised data." §119 transaction pseudonyms: » "contributes most effectively to data minimisation and data protection by default, since it prevents unlawful or unauthorised linkage of pseudonymised data across transactions by the pseudonyms they contain."
- **Grade:** [A] — regulatory guidance, the authoritative EU statement. Maps DIRECTLY onto item 8 (a per-customer consistent substitute is a "person pseudonym"; a per-conversation one is a "relationship/role-relationship pseudonym"; the EDPB ladder says the second is safer and the first "may not significantly reduce" disclosure risk).

### 2.2 Pfitzmann & Hansen — "A terminology for talking about privacy by data minimization: Anonymity, Unlinkability, Undetectability, Unobservability, Pseudonymity, and Identity Management" v0.34, 10 Aug 2010
- **URL:** https://dud.inf.tu-dresden.de/literatur/Anon_Terminology_v0.34.pdf
- **§11.2 "Linkability due to the use of a pseudonym across different contexts" (verbatim):** » "a) person pseudonym: A person pseudonym is a substitute for the holder's name which is regarded as representation for the holder's civil identity. It may be used in many different contexts" … » "e) transaction pseudonym: For each transaction, a transaction pseudonym unlinkable to any other transaction pseudonyms and at least initially unlinkable to any other IOI is used". » "In general, unlinkability of both role pseudonyms and relationship pseudonyms is stronger than unlinkability of person pseudonyms. … Ultimate strength of unlinkability is obtained with transaction pseudonyms, provided that no other information, e.g., from the context or from the pseudonym itself, enabling linking is available." » "Anonymity is the stronger, … the less often and the less context-spanning pseudonyms are used and therefore the less data about the holder can be linked".
- **Footnote 80 (the drift warning, verbatim):** » "If a role-relationship pseudonym is used for roles comprising many kinds of activities, the danger arises that after a while, it becomes a person pseudonym".
- **Grade:** [A] — the canonical formalisation; cited by the EDPB (fn. 33). THIS is the theoretical name for "consistent pseudonym enables linkage": it is linkability across contexts, and the pseudonym LATTICE is the trade-off Pseudex's `pseudonym_scope` (customer vs conversation) walks.

### 2.3 Sweeney — k-anonymity and quasi-identifiers (not re-fetched; well established)
- Sweeney, L. "k-anonymity: a model for protecting privacy", IJUFKS 10(5):557–570, 2002; Sweeney 2000 "Simple Demographics Often Identify People Uniquely" (Carnegie Mellon Data Privacy WP-3): 87% of the US population uniquely identified by {5-digit ZIP, gender, date of birth}; Golle 2006 (WPES) re-estimated 63% on Census 2000. Also Sweeney 1996 "Replacing personally-identifying information in medical records, the Scrub system" (AMIA) — the first realistic-surrogate text de-identifier, cited by Vīksna & Pinnis 2026.
- **What can honestly be claimed from it:** substituting NAMES leaves {age, gender, profession, city, employer, dates} in the text; by Sweeney/EDPB §101 those attributes alone can attribute the record. A name-substitution gateway therefore reduces DIRECT identifiability and does not, on its own, produce anonymised data. **Grade:** [A].

### 2.4 Carrell, Malin, Aberdeen, Bayer, Clark, Wellner, Hirschman — "Hiding in plain sight: use of realistic surrogates to reduce exposure of protected health information in clinical text"
- **Venue/year:** JAMIA 20(2):342–348, 2013. https://academic.oup.com/jamia/article-abstract/20/2/342/897812
- **Mechanism:** replace DETECTED identifiers with realistic same-type surrogates so that the few identifiers the detector MISSED are » "difficult to distinguish from the synthetic surrogates" (HIPS theory). Follow-up: iCAIRD Safe Haven 2022 (PMC9644981) » "provides minimal risk of misidentification".
- **Relevance to items 4 and 11:** the whole point of format-preserving fakes in the medical literature is that a leak becomes INVISIBLE — which is exactly why a real bearer of a fake name walking into the traffic (item 11, "forwards" collision) cannot be seen by anyone downstream either. HIPS is the argument FOR realistic fakes and simultaneously the reason the fake==real problem is undetectable from the outside.
- **Grade:** [A] (replicated in a second cohort, 2022).

### 2.5 The two Q4 problems in the literature — verdict
- **"Consistent pseudonym enables linkage":** NAMED and formalised — Pfitzmann–Hansen §11.2 (2010) and EDPB 01/2025 §95, §115–119. Not named in any LLM-agent paper found; the agent literature (Hou 2025, HaS, survey 2508.21587) treats consistency purely as a UTILITY feature.
- **"Fake collides with real" (a surrogate that IS a real person, or the real bearer arriving later):** NOT found as a named problem in any academic paper 2023–2026. Closest: (i) HIPS (2013) — realism is the goal, collisions are the unexamined cost; (ii) the EDPB's "pseudonym" is a token, so the question does not arise in its model; (iii) Yermilov 2023 draws surrogates from Wikidata — i.e. from REAL people by construction, without comment; (iv) a 2026 GitHub issue on an OSS gateway (tomorrowflow/blindfold #397, not academic) describes » "a plausible surrogate sent to a world-acting tool searches the public web for a real stranger". The only formal neighbour is the pseudonym-COLLISION literature for structured pseudonymisation (ENISA "Data Pseudonymisation: Advanced Techniques", 2021: deterministic pseudonyms must be collision-free), which is about two subjects sharing one pseudonym, not a pseudonym sharing a string with a real subject. **This is an open square on the map and an article can claim it.**

---

## PART 3 — remaining cards (structured-output restoration, the sanitiser family, verified classics)

### 3.1 Abedini, Mohapatra, Emerson, Shafieinejad, Cresswell, He (Waterloo / Vector / Layer 6) — "MaskSQL: Safeguarding Privacy for LLM-Based Text-to-SQL via Abstraction"
- **Venue/year:** arXiv 2509.23459 v1 27 Sep 2025 (v2 exists); OpenReview JxtqDIECwd.
- **URL:** https://arxiv.org/abs/2509.23459
- **Mechanism (own words):** the NL question and the schema are abstracted — » "Table names are mapped to symbols like T_i, and columns to C_i", literal values to V_i with a side sentence saying which column each belongs to; the remote LLM writes SQL over the symbols; » "Using the symbol lookup table created during abstraction, all abstract symbols are replaced with their corresponding concrete values"; a local SLM then repairs the SQL using execution feedback. **This is the closest published analogue to item 2 — a mapping table restoring placeholders INSIDE a structured, executable output.**
- **Key numbers (300 complex BIRD-dev queries):** MaskSQL full policy 55.66% execution accuracy; lenient policy 62.66%; untrusted GPT-4.1 direct 75.66%, DIN-SQL+GPT-4.1 73.66%; trusted Qwen-2.5-7B 50.66%. Ablation: WITHOUT the reconstruction step 34.33%. Privacy: masking recall 61.36%, re-identification score 75.47%.
- **Limitation (verbatim):** » "Since only a subset of tokens is abstracted within the NL question, the surrounding context may be exploited to re-identify the abstract tokens." » "incorrect mapping can lead to syntax errors (e.g. joins applied with incorrect column names)."
- **Grade:** [B]. The number to remember: restoring placeholders into an executable artefact costs **−13 to −20 pp** vs the un-masked model, and the restoration step itself is worth +21 pp — i.e. restoration is where the utility lives, not detection.

### 3.2 Lison, Pilán, Sánchez, Batet, Øvrelid — "Anonymisation Models for Text Data: State of the art, Challenges and Future Directions" (ACL 2021)
- **URL:** https://aclanthology.org/2021.acl-long.323.pdf
- **VERIFIED verbatim (pdftotext; an earlier LLM summary of this fetch fabricated quotes and was discarded):** fn.1 » "GDPR also introduces the equivalent concept of pseudonymisation, which is a useful privacy-enhancing measure, but it does not qualify as full anonymisation." §3.1 » "The problem of replacing identifiers with surrogate values is rarely addressed in NLP. Most approaches simply replace detected identifiers with dummy values such as X, although some models attempt to preserve the gender of person names and provide dedicated rules for e.g. dates and addresses (Sweeney, 1996; Alfalahi et al., 2012; Eder et al., 2019; Chen et al., 2019) or to a somewhat broader range of identifiers (Volodina et al., 2020). A few studies have analysed the re-identification risk of de-identified or pseudonymised texts (Carrell et al., 2013; Meystre et al., 2014b). The data utility of de-identified texts is analysed in Meystre et al. (2014a), concluding that the impact of de-identification is small, but non-negligible." Definition box: » "Quasi Identifier: Information (such as gender, …" and » "the combination of gender, birth date and postal code can" [identify].
- **Grade:** [A] (ACL long, ~500 citations). It says nothing about surrogate collisions or cross-document linkage — those sentences do not exist in the paper.

### 3.3 Lohr, Eder, Hahn — "Pseudonymization of PHI Items in German Clinical Reports" (Stud Health Technol Inform / MIE 2021; PubMed 34042748)
- **From the indexed abstract (not the full text):** a system built for the CodE Alltag German e-mail corpus, adapted to clinical reports, » "replaces identified Protected Health Information items with semantic type-conformant, yet fictitious surrogates. The generated substitutes were evaluated for grammatical correctness, semantic and medical plausibility with particularly low error rates (less than 1%)."
- **Relevance:** the only paper found that REPORTS an error rate for grammatical correctness of generated surrogates in an inflected language (German: case on articles/adjectives, weak/strong declension). Sibling: Eder, Krieg-Holz, Hahn 2019 "De-identification of emails: Pseudonymizing privacy-sensitive data in a German email corpus" (RANLP 2019), CodE Alltag 2.0 (LREC 2020).
- **Grade:** [B]; full text not read.

### 3.4 CALD-pseudo 2024 — Workshop on Computational Approaches to Language Data Pseudonymization (EACL 2024)
- **URL:** https://aclanthology.org/volumes/2024.caldpseudo-1/
- Ten papers; languages: Swedish (×3), Norwegian, Spanish, English. **No Russian, no Polish, no Czech.** Relevant items: PSILENCE (Cabrera-Diego & Gheewala) » "same pseudonym throughout one document" (item 5 at document scope); Simancek & Vydiswaran — Markov-based pseudonymisation designed to » "mask name recognition misses" (HIPS again); Muñoz Sánchez et al. "Did the Names I Used within My Essay Affect My Score?" — the CHOICE of substitute name shifts an automated essay scorer's output, i.e. direct evidence that a pseudonym is not behaviourally neutral for a downstream model (item 13, negative direction).
- **Grade:** [B] each; the workshop's existence is evidence the field has a venue, and its language list is evidence Russian is absent from it.

### 3.5 The prompt-sanitiser family (the "known" list — brief, from abstracts/known results)
- **Casper** (Chong et al., arXiv 2408.07004, Aug 2024): browser extension; rule filter + ML NER + local-LLM topic identifier; 98.5% PII detection, 89.9% topic detection on 4,000 synthesised prompts. No restoration, no utility metric. [B]
- **InferDPT** (Tong et al., arXiv 2310.12214, v1 Oct 2023 → v8 Mar 2026): token-level DP perturbation of the prompt (RANTEXT, ε=6) + local extraction module; » "comparable to that of non-private GPT-4" on three generation datasets; >90% protection against embedding-inversion. Irreversible by design; no entity identity survives, so no tool call can be made on it. [B]
- **DP-Prompt / TextObfuscator / DP-Forward** (2023): DP paraphrase or representation noise for classification; the survey line in InferDPT's related work: » "mainly designed for classification tasks". Irreversible. [B]
- **ProPILE** (Kim et al., NeurIPS 2023, arXiv 2307.01881): a PROBING tool for PII memorised in training data — orthogonal to inference-time pseudonymisation. [A]
- **AirGapAgent** (Bagdasarian et al., CCS 2024, arXiv 2405.05175): minimisation by a separate "data minimiser" LLM that decides which user-profile fields the task needs; a context-hijacking attack cut a Gemini Ultra agent's protection from 94% to 45%, AirGapAgent kept 97%. Utility reported as "task-relevant fields shared"; no pseudonymisation, no restoration. [B]
- **ConfAIde** (Mireshghallah et al., ICLR 2024): four-tier contextual-integrity probe; GPT-4 leaks in 39% of tier-4 (agent-like summarisation) cases; no mitigation, no utility. [A]
- **PII-Bench** (Shen et al., arXiv 2502.18545, Feb 2025): "query-aware" masking — only PII irrelevant to the user's query is masked; 2,842 samples, 55 subcategories. This is the one benchmark whose premise is that masking must NOT damage the answer; it scores masking precision/recall given the query, not agent task success. [B]
- **PrivLM-Bench** (Li et al., ACL 2024): measures leakage of DP-fine-tuned models; training-side, out of scope. [A]
- **"Cloaked Classifiers: Pseudonymization Strategies on Sensitive Classification Tasks"** (Ravichandran et al., arXiv 2406.17875, 2024): compares placeholder vs realistic pseudonyms for training classifiers; title only verified. [D]
- **"Protecting De-identified Documents from Search-based Linkage Attacks"** (arXiv 2510.06383, Oct 2025): the search-engine variant of the re-identification threat; title only verified. [D]
- **Zeng et al. 2025** (cited by the agent survey) — replacing private records with generated substitutes for RAG; not fetched. [D]

### 3.6 Russian-specific — what was actually found (Q2 verdict)
- **Corpora with Russian:** NEREL (Loukachevitch et al., RANLP 2021 / LRE 2023: 56k nested entities, 39k relations) — general NER, not PII-labelled; RuNNE-2022 shared task; MultiGraSCCo (LREC 2026, §1.14) — PHI/IPI labels, Russian F1 0.85–0.87, no substitution eval; DialogPII (arXiv 2606.30312, 2026) — synthetic multilingual dialogue PII, 19 types, Russian listed; Meddies-PII (arXiv 2609.12544, Sep 2026) — 1M synthetic clinical docs in 17 languages incl. Russian, detection only. MASSIVE ru-RU (FitzGerald et al. 2022) is a SLU slot corpus with person/place slots — usable as a recall instrument, never designed for PII.
- **Russian academic work on inflected SUBSTITUTION:** none found. Search terms tried: обезличивание/деидентификация/анонимизация текстов + склонение/согласование/род, Dialogue/AINL/RuSSIR/Slavic NLP 2025, "Russian de-identification pymorphy/Natasha". Slavic NLP 2025 (ACL workshop) has no pseudonymisation paper. The Russian-language hits are (a) Karpova 2013 (relational shuffling, §1.13), (b) 2024–2026 practitioner posts on Habr (Just AI «динамическая анонимизация», «Русский Маскарад», PII-Guard) — grey literature that DOES state the gender-agreement problem (» "Kozlova said" → male verb form if gender is not carried in the tag) but reports no measurement — and (c) the regulatory frame (152-ФЗ; Roskomnadzor приказ №996 method list; УК ст. 272.1 since Dec 2024).
- **Nearest peer-reviewed work on grammatically agreed substitution in an inflected language:** Vīksna & Pinnis TSD 2026 (Polish + English; Morfeusz; downstream NER/sentiment retention — numbers paywalled), Vīksna & Skadiņa RANLP 2025 (LV/LT/ET/EN; Stanza-feature-matched candidate lists; mechanism only), Lohr/Eder/Hahn 2021 (German; <1% grammatical error on surrogates), Alfalahi/Brissman/Dalianis 2012 (Swedish; gender-preserving names). **Zero papers measure the REVERSE direction — a model re-inflecting or transliterating the fake and the gateway resolving it (item 7).**

---

## PART 4 — SYNTHESIS

### 4.1 Answers to the four questions

**Q1(a) consistent pseudonyms across turns.** Treated as an implementation FEATURE, never as a measured axis. Hou 2025 (§1.1) reuses the forward mapping inside ONE request; PSILENCE/ANOPPI keep one pseudonym per DOCUMENT; the EDPB (§2.1 §115) says the SCOPE of consistency is a design decision with a risk ladder. The only multi-turn measurement is Xiao 2026 (§1.2): under two adversarial follow-ups a plausible-substitute strategy degrades least (+3.9 pp leak vs +11.8 pp for generalisation), but that is the MODEL choosing to pseudonymise its own reply, not a gateway. Nobody measures "same person, turn 1 vs turn 12, same fake?".

**Q1(b) reversing pseudonyms in structured outputs / function calls.** One paper: MaskSQL (§3.1) — symbol table restored into SQL; −13…−20 pp execution accuracy vs the un-masked model, and the restoration step is worth +21 pp on its own. ToolMinimize (§1.10) sits at the same boundary but deliberately keeps the tool BLIND (irreversible minimisation) and reports "argument-level task validity 100%" (schema-valid) but only 80% functional equivalence end-to-end. Nobody restores a realistic fake NAME/ADDRESS inside JSON tool arguments and measures whether the tool call still succeeds.

**Q1(c) utility cost — numbers with conditions.**
| Study | Substitution | Task / model | Cost |
|---|---|---|---|
| Yermilov 2023 | Wikidata same-type realistic fakes (train-time) | IMDB cls BERT-base | −0.3 pp F |
| Yermilov 2023 | same | CNN/DM summ. BART-base | −1…−7 R-1, −7…−12 R-L |
| HaS 2023 | random same-type, generative restore | BBC cls | −0.24…−1.16 pp F1 |
| HaS 2023 | same | translation (DeepL ref) after restore | −1.4…−3.8 R-L |
| Hou 2025 | LLM-generated same-type, string restore | SQuAD/CNN-DM/SAMSum/MNLI, Qwen-14B | ≤5% relative loss |
| Hou 2025 | same | XSum / WMT14 | ~10% / ~15% relative |
| PAPILLON 2025 | naive REDACTION baseline | PUPA, GPT-4o-mini | −11 pp quality (88.2→77.2) |
| Deußer 2026 | tagged placeholder <LOC>-1 | MedQA/MMLU-Pro/HellaSwag | −3…−10 pp |
| Deußer 2026 | same | ARC, IFEval | <5 pp |
| Deußer 2026 | same | **RGB (RAG)** | **−22…−47 pp** |
| Deußer 2026 | same | TruthfulQA | **+8 pp** (Llama-3.1) |
| MaskSQL 2025 | symbol table into SQL | BIRD-dev 300, GPT-4.1 | −13…−20 pp exec. acc. |
| AgentDAM 2025 | (prompt defence, not substitution) | WebArena 246 tasks | −1.6…−5.7 pp task success |
| Privacy-in-Action 2025 | (flow-judge, not substitution) | PrivacyLens-Live | −0.16…−0.24 on a 3-pt helpfulness scale |
| ToolMinimize 2026 | irreversible arg minimisation | 20 mock scenarios | 80% functionally equivalent |
No study reports seeds or CIs for any of these. Deußer runs at temperature 0 on ≤500 samples/benchmark.

**Q2 Russian / inflected languages.** No Russian paper. Polish/Latvian/Lithuanian/Estonian (Vīksna 2025/2026), German (Lohr/Eder/Hahn 2021, <1% grammatical error), Swedish (Alfalahi 2012, gender only). All FORWARD direction (make the fake agree with the sentence). None measure the reverse (model re-inflects the fake; gateway must resolve it) and none measure agent tool calls.

**Q3 theory.** Pseudonymised text is personal data (EDPB 01/2025 §22; Lison 2021 fn.1); quasi-identifiers survive name substitution (EDPB §101; Sweeney 87%/Golle 63%); linkage of consistently-pseudonymised records raises attributability (EDPB §95); the pseudonym-scope lattice person > role/relationship > transaction (Pfitzmann–Hansen §11.2; EDPB §115–119); content/style re-identification needs no identifier at all (Lermen/Carlini/Tramèr 2026: 68% recall @ 90% precision from raw pseudonymous text; Charpentier & Lison ACL 2025: 80% of masked spans recoverable with background corpus). Honest claim available to an article: "a reversible gateway removes DIRECT identifiers from what the provider sees; it does not anonymise, and it does not defend against inference from content."

**Q4 the two problems.** "Consistent pseudonym enables linkage" — formalised (Pfitzmann–Hansen 2010; EDPB 2025), never named in the LLM-agent literature. "Fake collides with real" — NOT in any paper found; the closest academic neighbour is HIPS (Carrell 2013), which WANTS leaks to be indistinguishable from fakes and therefore also makes a real bearer indistinguishable from a fake. Both halves of the collision (backwards: fake == some real value already in the vault; forwards: a real person bearing the fake arrives later) are unclaimed territory.

### 4.2 Gap map — the 13 transparency items vs literature

| # | Item | Literature status | Best citations |
|---|---|---|---|
| 1 | reversible answer | **HAS** (plain text only) | HaS 2023; Hou 2025; PAPILLON (re-aggregation, no mapping) |
| 2 | tool-call args restored | **ONE ANALOGUE** (SQL symbols), no names/addresses | MaskSQL 2025; ToolMinimize 2026 (same boundary, opposite design) |
| 3 | tool results re-masked | **NONE** — only a warning shape | Deußer 2026 RGB −22…−47 pp (masked question vs unmasked passages); agent survey 2606.26627 names tool responses as a surface |
| 4 | format-preserving fakes | **HAS** (medical de-id) | Carrell 2013 HIPS; Yermilov 2023; Hou 2025 |
| 5 | multi-turn consistency | **PARTIAL** (document scope; one adversarial-probe study) | PSILENCE 2024; Xiao 2026 |
| 6 | streaming | **NONE** | — |
| 7 | agent rewrites the fake (inflection/translit/initials) | **NONE** | (forward direction only: Vīksna 2025/26; Lohr 2021) |
| 8 | memory / cross-conversation scope | **THEORY ONLY** | EDPB §115–119; Pfitzmann–Hansen §11.2; agent survey §memory; GateMem 2026 (memory governance, no pseudonyms) |
| 9 | partial mentions & corrections | **NONE** | — |
| 10 | morphology of inflected languages | **PARTIAL** (PL/LV/LT/ET/DE/SV; none RU; forward only) | Vīksna & Pinnis TSD 2026; Vīksna & Skadiņa RANLP 2025; Lohr/Eder/Hahn 2021 |
| 11 | fake == real collisions | **NONE** | (HIPS as the reason it is invisible) |
| 12 | deployment / residency | **NONE academic** (regulatory only) | EDPB §36–41 "pseudonymisation domain" |
| 13 | measured "agent unaffected" | **PARTIAL** — measured for prompt/judge defences, NOT for substitution; no benchmark has a control arm for a gateway | AgentDAM 2025 (−1.6…−5.7 pp); Privacy-in-Action 2025; ToolMinimize 2026 (80%); Muñoz Sánchez 2024 (name choice moves a scorer) |

Nine of thirteen have no direct literature; items 3, 7, 9, 11 have nothing at all; items 6 and 12 are engineering, not research.

### 4.3 The three papers an article MUST cite
1. **Deußer et al. 2026, arXiv 2609.11335** — the broadest measurement of what input anonymisation costs an LLM: near-free on reasoning, catastrophic (−22…−47 pp) on retrieval-augmented tasks, and it IMPROVES truthfulness. It is the number that separates "masking the prompt" from "masking the prompt while the tool result stays unmasked", which is the whole product.
2. **EDPB Guidelines 01/2025 on Pseudonymisation** (with Pfitzmann–Hansen 2010 behind it) — the authoritative statement that pseudonymised data stays personal (§22), that quasi-identifiers survive (§101), and that the SCOPE of pseudonym consistency is the safety lever (§115–119). It turns `pseudonym_scope` from an implementation detail into a regulator-named design decision.
3. **AgentDAM (Zharmagambetov et al., Meta, 2025)** — the only agent benchmark that publishes task success AND leakage per model with and without a mitigation, and shows the mitigation's cost is mostly false refusals. It is the template for the missing control-arm experiment, and citing it lets the article say honestly that no such measurement exists for substitution.
(Runner-up if a fourth is allowed: MaskSQL — the only published restoration-into-structured-output number.)

### 4.4 Numbers that contradict "pseudonymisation costs agent accuracy only a few pp"
- **Deußer 2026, RGB retrieval-augmented: −22 to −47 pp** under consistent-tag pseudonymisation of the input (GPT-4o-mini / Qwen2.5-72B / Llama-3.1 / Teuken-7B; 500 samples; temp 0). Mechanism: the question's entities no longer string-match the retrieved passages. An agent whose TOOL RESULT is not re-masked with the same key is in exactly this regime.
- **MaskSQL 2025: −13 to −20 pp execution accuracy** on BIRD when literals are replaced by symbols and restored in the SQL; −41 pp if restoration is skipped.
- **PAPILLON 2025: −11 pp answer quality** for naive redaction (88.2 → 77.2), the baseline a customer will compare against.
- **Hou 2025: ~15% relative loss on translation** (WMT14) even with restoration.
- **ToolMinimize 2026: 20% of end-to-end scenarios not functionally equivalent** after a tool-boundary rewrite (irreversible; mock endpoints).
- **Muñoz Sánchez et al. 2024 (CALD-pseudo):** the identity of the substitute name alone shifts an automated essay scorer — a fake is not behaviourally neutral even when the task never asks about the name.
- Counter-direction: **Deußer 2026 TruthfulQA +8 pp**, and **Xiao 2026** where pseudonymisation is the strategy that loses LEAST under probing — so the sign is task-dependent, and "a few pp" is a defensible claim only for classification/QA over text the model does not need to match against external records.

### 4.5 Method notes for whoever re-uses this file
- 30 fetches used: 28 WebFetch + 1 tavily extract + local pdftotext on 6 saved PDFs (RANLP 2025, HaS, Karpova 2013, text-anonymisation survey, EDPB 01/2025, Pfitzmann–Hansen v0.34, Lison 2021).
- **One WebFetch summary (Lison 2021) returned invented quotations that mirrored the prompt's wording; it was caught by re-reading the PDF text.** Every » quote above from a PDF was taken from pdftotext output, not from the summariser. Quotes from HTML pages (arXiv html) were not independently re-verified beyond the summariser.
- Paywalled and unread: Vīksna & Pinnis TSD 2026 body; Lohr/Eder/Hahn 2021 body; AURA 2605.30848 body; the agent survey's Table 6.
- Not searched (out of scope by brief): commercial gateways, OSS projects, DP fine-tuning, training-data memorisation.
