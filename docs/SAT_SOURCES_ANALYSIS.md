# SAT_SOURCES_ANALYSIS.md — Анализ источников

> **Назначение:** детальный анализ каждого источника: прочитан ли, качество, что взяли, индексация.
> **Связь с PROJECT_BIBLE:** раздел 1.8 (списки A, B, C) + требования К5 (≥30 не старше 5 лет, ≥30% ВАК, ≥20% Scopus/WoS).
> **Последнее обновление:** 16.04.2026

---

## Статистика (обновлять при добавлении источников)

- **Всего уникальных источников:** ~53 (Z: 10, P: 31 минус 3 дубликата, N: 11, D: 5, минус P20 = 2 источника)
- **Не старше 5 лет (2021–2026):** ~19 → нужно добить до ≥30
- **ВАК/РИНЦ:** 0 → **осознанно не добираем**, см. ниже
- **Scopus/WoS:** ~12–14 → нужно ≥20 %
- **Фундаментальные (до 2020):** допустимы как основы области

### Решение 24.04 по ВАК-требованию К5

Релевантного по теме ВКР (OWL+SWRL для управления доступом к контенту в СДО) русскоязычного ВАК-корпуса не существует. Целевой поиск в eLibrary.ru по направлениям L1–L8 не даёт источников, пересекающих предметную область на уровне, достаточном для литобзора.

Искусственный добор косвенно-релевантных работ ради формального критерия «≥30 % ВАК» подорвёт качество главы 1 и создаст риск вопроса комиссии «а как эта статья связана с вашей темой?».

**Позиция для защиты:** отсутствие ВАК-корпуса по теме — это само по себе подтверждение gap в литературе. Альтернативные критерии К5 (≥30 не старше 5 лет, ≥20 % Scopus/WoS) соблюдаются, общая релевантность и качество источников — приоритет над формальной процентной квотой. Зафиксировано в §7 PROJECT_BIBLE от 24.04.

---

## A. Источники из задания в ИСУ (Z1–Z10)

| # | Источник | Год | Scopus/WoS | Прочитан | Роль в ВКР | Качество |
|---|---------|-----|-----------|----------|-----------|----------|
| Z1 | Sarwar S. et al. — Ontology based E-learning framework | 2019 | Scopus (Multimedia Tools & Applications) | Абстракт | L2: образовательная онтология без AC. CourseOntology для рекомендаций | Высокое (130+ цитирований) |
| Z2 | Rani M. et al. — Ontology-based adaptive personalized e-learning | 2015 | Scopus | Абстракт | L2: user.owl+course.owl, Felder-Silverman. Нет AC | Среднее |
| Z3 | Iqbal M. et al. — Personalized e-learning for semantic Web | 2025 | ? | Не прочитан | L2/L5: свежий источник, Semantic Web в образовании | Проверить индексацию |
| Z4 | Scherp A. et al. — Semantic web: Past, present, and future | 2024 | Scopus | Не прочитан | Общий фон: обзор Semantic Web | Высокое |
| Z5 | Brewster C. et al. — Ontology-based access control for FAIR data | 2020 | Scopus | Не прочитан | L3: OBAC для FAIR data, не образование | Среднее |
| Z6 | Can Ö. et al. — Personalizable ontology based access control | 2010 | Scopus | Не прочитан | L3: OBAC с Rei policy language | Среднее (фундаментальная) |
| Z7 | Nazyrova A. et al. — Analysis of consistency of prerequisites | 2023 | Scopus (Applied Sciences, MDPI) | Абстракт + ключевые разделы | L4: ближайшая работа. OWL+DL Query для проверки пререквизитов учебного плана. Наша работа расширяет до fine-grained AC | Высокое (ключевой) |
| Z8 | Allemang D., Hendler J. — Semantic web for the working ontologist | 2011 | — (книга) | Не прочитан | Учебник OWL. Фундаментальный источник | Высокое |
| Z9 | Zhang L., Lobov A. — SWRL-based approach for KBE | 2024 | Scopus (Adv. Eng. Informatics) | Абстракт | L3: SWRL в инженерии. Подтверждает: reasoner performance — узкое место | Высокое |
| Z10 | Horrocks I. et al. — SWRL: A semantic web rule language | 2004 | — (W3C Submission) | Спецификация | Фундаментальный: спецификация SWRL | Стандарт |

## B. Источники из текущей ПЗ (P1–P31)

| # | Источник | Год | Scopus/WoS | Прочитан | Роль в ВКР | Качество |
|---|---------|-----|-----------|----------|-----------|----------|
| P1 | Pelánek R. — Adaptive learning is hard | 2025 | Scopus | Не прочитан | L5: фон для главы 1. Ограничения адаптивного обучения | Высокое |
| P2 | Mirata V. et al. — Challenges in adaptive learning in HE | 2020 | Scopus | Не прочитан | L5: фон для главы 1 | Среднее |
| P3 | Kucharski S. et al. — Adaptive Learning Mechanisms: Scoping Review | 2025 | Scopus | Не прочитан | L5: фон для главы 1. Обзор механизмов | Высокое |
| P4 | Bakhouyi A. et al. — Standardization and interoperability on E-learning | 2017 | Scopus | Не прочитан | L7: стандарты e-learning | Среднее |
| P5 | AICC — CMI Guidelines v4.0 | 2004 | — (стандарт) | Не прочитан | L7: исторический стандарт | Стандарт |
| P6 | ADL — SCORM 2004 4th Ed. | 2009 | — (стандарт) | Не прочитан | L7: стандарт, sequencing ≠ AC | Стандарт |
| P7 | ADL — xAPI v2.0 | 2023 | — (стандарт) | Не прочитан | L7: стандарт трекинга, не AC | Стандарт |
| P8 | AICC/ADL — CMI5 Specification | — | — (стандарт) | Не прочитан | L7: стандарт поверх xAPI | Стандарт |
| P9 | = Z1 (дубликат) | 2019 | — | — | Удалить из финального списка | — |
| P10 | = Z2 (дубликат) | 2015 | — | — | Удалить из финального списка | — |
| P11 | Sandhu R.S. — Role-based access control | 1998 | WoS | Не прочитан | Фундаментальный: RBAC. Контекст для позиционирования | Высокое (15000+ цитирований) |
| P12 | Moodle Docs — Roles and permissions | — | — (документация) | Бегло | L1: Moodle access control | Документация |
| P13 | Blackboard — Roles and Privileges | — | — (документация) | Бегло | L1: Blackboard access control | Документация |
| P14 | Hu V.C. et al. — NIST SP 800-162 (ABAC) | 2014 | — (NIST) | Не прочитан | Фундаментальный: ABAC, default-deny | Стандарт |
| P15 | OASIS — XACML v3.0 | 2013 | — (стандарт) | Не прочитан | Фундаментальный: XACML | Стандарт |
| P16 | Jebbaoui H. et al. — Detecting flaws in XACML policies | 2015 | Scopus | Абстракт | L4: SBA-XACML, обнаружение flaws/conflicts/redundancies. 2.4–15× speedup | Высокое |
| P17 | Moodle Dev — Availability conditions | — | — (документация) | Прочитан | L1: Moodle restrict access, JSON availability | Документация (ключевой) |
| P18 | Bhatti R. et al. — Trust-based CAAC | 2005 | Scopus | Не прочитан | Контекст: CAAC | Среднее |
| P19 | Kim Y.G. et al. — Context-aware AC for ubiquitous | 2005 | Scopus | Не прочитан | Контекст: CAAC | Среднее |
| P20 | ⚠️ ДВА ИСТОЧНИКА — РАЗДЕЛИТЬ на Z5 и Z6 | — | — | — | Исправить в финальном списке | — |
| P21 | Aslam S. et al. — OBAC: agent-based | 2020 | Scopus | Не прочитан | L3: OBAC | Среднее |
| P22 | McGuinness D.L. et al. — OWL overview (W3C) | 2004 | — (W3C) | Спецификация | Фундаментальный: спецификация OWL | Стандарт |
| P23 | Horrocks I. — Knowledge Representation on Semantic Web | 2010 | Scopus | Не прочитан | Теория OWL | Высокое |
| P24 | Kayes A.S.M. et al. — CAAC with fuzzy logic and ontology | 2020 | Scopus | Не прочитан | L3: CAAC + онтологии | Среднее |
| P25 | Microsoft Learn — Графы vs. реляционные БД | — | — (документация) | Прочитан | Фон: сравнение подходов к хранению | Документация |
| P26 | Angles R. — Comparison of graph database models | 2012 | Scopus (IEEE) | Не прочитан | Фон: графовые БД | Среднее |
| P27 | = Z4 (дубликат) | 2024 | — | — | Удалить из финального списка | — |
| P28 | Abburu S. — Survey on ontology reasoners | 2012 | ? | Не прочитан | L8: обзор резонеров (устарел) | Низкое |
| P29 | Abicht K. — OWL Reasoners still useable in 2023 | 2023 | arXiv (preprint) | Абстракт | L8: актуальность резонеров. 95+ обзор | Среднее |
| P30 | Lam A.N. et al. — Performance Evaluation of OWL 2 DL Reasoners | 2023 | Scopus (ESWC) | Абстракт + ключевые данные | L8: бенчмарк 6 резонеров. Konclude лидер, Openllet mid-range | Высокое (ключевой) |
| P31 | Steigmiller A. et al. — Benchmarking DL Reasoners | 2023 | Scopus (ISWC) | Абстракт | L8: нейросимволические vs символические. Символические пока лучше | Высокое |

## C. Источники из литобзора фазы 0 (N1–N11)

| # | Источник | Год | Scopus/WoS | Прочитан | Роль в ВКР | Качество |
|---|---------|-----|-----------|----------|-----------|----------|
| N1 | Finin T. — ROWLBAC (SACMAT) | 2008 | Scopus (ACM) | Абстракт + ключевые идеи | L3: фундаментальная работа OBAC. RBAC в OWL через rdfs:subClassOf, owl:disjointWith | Высокое (фундаментальный) |
| N2 | Carminati B. et al. — OWL+SWRL for AC in social networks | 2011 | Scopus (Data & Knowledge Eng.) | Абстракт + ключевые разделы | L3: ключевой. Документация OWA-проблемы. Workaround: cannotDo + SPARQL | Высокое (ключевой) |
| N3 | Beimel D., Peleg M. — SitBAC (healthcare AC) | 2011 | Scopus | Абстракт | L3: OWL+SWRL для AC в здравоохранении | Высокое |
| N4 | Hsu W.-L. — LAPAR (XACML+OWL+SWRL) | 2013 | Scopus | Абстракт | L3: многослойная интеграция | Среднее |
| N5 | Kolovski V. et al. — XACML via Defeasible DL (WWW) | 2007 | Scopus (ACM WWW) | Абстракт + ключевые идеи | L4: фундаментальный. DL для верификации XACML. Policy inclusion = concept subsumption | Высокое (ключевой) |
| N6 | Huang H. et al. — DL-based conflict detecting (ACM) | 2009 | Scopus (ACM) | Абстракт | L4: ABox consistency = conflict detection | Высокое |
| N7 | Laouar M.R. et al. — Ontology-based inconsistency handling in AC | 2025 | Scopus (Springer) | Абстракт | L3: свежий! OWL + inconsistency-tolerant AC | Высокое |
| N8 | Kozlov F.A., Mouromtsev D.I. — ECOLE (ITMO) | 2013–2017 | Scopus (CCIS, WWW Companion) | Абстракт + описание | L6: ИТМО, онтология курсов Open edX. Нет AC | Высокое (контекст) |
| N9 | Heiyanthuduwage S.R. et al. — OWL 2 Learn Profile (PMC) | 2016 | Scopus (PMC) | Абстракт + ключевой вывод | L2: анализ 14 онтологий — ни одна не содержит AC | Высокое (ключевой) |
| N10 | Fisler K. et al. — Margrave (ICSE) | 2005 | Scopus (ACM ICSE) | Абстракт | L4: XACML → MTBDD verification | Высокое (фундаментальный) |
| N11 | Marfia F. et al. — DL reasoning for XACML authorization | 2015 | Scopus | Абстракт | L4: три онтологии (Policy/Domain TBox, ABox) + DL reasoner | Среднее |

## D. Источники, выявленные при фазе 1 — подтверждение gap (N12–N16)

> **Роль:** эти источники подтверждают, что gap, выявленный в фазе 0, сохраняется в 2022–2025 годах.

| # | Источник | Год | Scopus/WoS | Прочитан | Роль в ВКР | Качество |
|---|---------|-----|-----------|----------|-----------|----------|
| N12 | Fakoya J.T. et al. — Ontology-Based Model for E-Learning Management System (O-BMEMS) | 2024 | ? (проверить) | Абстракт | L2: свежая e-learning онтология **без AC** — подтверждает gap | Среднее |
| N13 | Na Nongkhai L. et al. — ADVENTURE: Adaptive learning based on CONTINUOUS ontology | 2025 | Scopus (MDPI Education Sciences) | Абстракт | L2: свежая образовательная онтология + адаптивное обучение **без AC** | Высокое |
| N14 | Mohamed A.K.Y.S. et al. — Systematic literature review for authorization and access control | 2022 | Scopus (Int. J. Web Inf. Syst.) | Абстракт | L3/L4: систематический обзор AC — образование не фигурирует как домен OBAC | Высокое |
| N15 | Farhadighalati N. et al. — A Systematic Review of Access Control Models | 2025 | Scopus (IEEE Access) | Абстракт | L3/L4: систематический обзор ACM — образование не фигурирует | Высокое |
| N16 | Can Ö., Unalir M.-O. — Revisiting OBAC: The Case for OBDA (ICISSP 2022) | 2022 | Scopus | Абстракт | L3: OBAC+OBDA, **не образование** — подтверждает gap | Среднее |

---

## Задачи на фазу 4

1. **Добить свежие источники (2021–2026):** нужно ≥30 не старше 5 лет. Текущий дефицит ~11. Направления: онтологии 2021+, SWRL 2021+, LMS access control 2021+, DL reasoning 2021+, adaptive learning 2021+
2. ~~Добить ВАК/РИНЦ~~ — **снято решением 24.04** (см. выше). Ведение ВАК-колонки в таблицах сохраняется как информация, не как цель
3. **Разделить P20** на два отдельных источника
4. **Удалить дубликаты** P9, P10, P27 из финального списка
5. **Проверить индексацию** Z3 (Iqbal 2025)
6. **Прочитать полностью** ключевые источники: Z7, N2, N5, P30
