# Ontology-Based Access Control in LMS: A Research Gap Analysis

**No existing work combines OWL ontologies, SWRL rules, and DL-reasoner verification for access control in Learning Management Systems — making this a clearly defined and publishable research gap.** Three mature but entirely disconnected research streams — e-learning ontologies, semantic web access control, and formal policy verification — have never converged on the LMS access control problem. Meanwhile, every major LMS platform lacks formal verification of its access rules, with Open edX even documenting that circular prerequisite chains can permanently lock learners out of content. This gap sits at a theoretically rich intersection with practical significance for millions of LMS users worldwide.

---

## How five LMS platforms handle access control — and where they all fail

All major platforms implement some form of conditional access, but with remarkably different architectures and granularity. **Moodle** offers the most expressive system: JSON-encoded availability conditions stored in `course_modules.availability` support nested Boolean logic (AND/OR/NOT) across grade thresholds, activity completion, dates, group membership, user profile fields, and competency frameworks. Its plugin architecture (`/availability/condition/`) has produced 30+ community extensions including role-based, IP-based, and GPS-based restrictions.

**Canvas LMS** operates at module level only, with prerequisites limited to sequential module completion. Its Mastery Paths feature adds performance-based branching with up to three scoring ranges, but individual activities cannot carry independent access conditions. **Blackboard** (now Anthology) provides "Adaptive Release" with a disjunctive normal form structure — multiple rules combined with OR, each containing AND-joined criteria — but cannot apply rules to discussion forums and loses all rules when courses are copied. **Stepik** offers only module-level point thresholds in its paid tiers, with no activity-level conditions, Boolean logic, or group-based gating. **Open edX** restricts prerequisites to the subsection level, supporting minimum score and completion percentage, but permits only a single prerequisite per subsection with no compound conditions.

The critical finding across all five platforms is a shared set of **architectural blind spots**:

- **No platform implements formal verification** of access rule consistency
- **No platform detects circular dependencies** — Open edX explicitly warns that "prerequisite configuration controls do not prevent you from creating a circular chain of prerequisites that will permanently hide them from learners"
- **No platform supports cross-course dependencies** in standard access control
- Rules are evaluated at runtime with no pre-validation of satisfiability

| Feature | Moodle | Canvas | Blackboard | Stepik | Open edX |
|---|---|---|---|---|---|
| Granularity | Activity + section | Module | Content item | Module | Subsection |
| Boolean logic | Full nesting | None | OR-of-ANDs | None | None |
| Grade threshold | ✅ | ✅ | ✅ | ✅ (points) | ✅ (min %) |
| Completion tracking | ✅ | ✅ | ✅ (review status) | ❌ | ✅ |
| Date restrictions | ✅ | ✅ | ✅ | ❌ | ✅ (release dates) |
| Group/membership | ✅ | ✅ (Differentiation) | ✅ | ❌ | ✅ (cohorts) |
| Cycle detection | ❌ | Structural mitigation | ❌ | Sequential by design | ❌ (documented risk) |
| Formal verification | ❌ | ❌ | ❌ | ❌ | ❌ |

These limitations are not minor. **Blackboard** performs a basic check flagging rules "that can't be satisfied" in Advanced Adaptive Release, but this is a shallow heuristic rather than formal verification. Canvas structurally prevents backward prerequisite references by only allowing preceding modules, which mitigates but does not eliminate logical issues. Storage formats range from Moodle's JSON trees to Open edX's CourseContentMilestone database records to Canvas's PostgreSQL relational model — none designed with formal reasoning in mind.

---

## E-learning ontologies and access control ontologies exist separately but have never intersected

An extensive search across Scopus, IEEE Xplore, ACM DL, and SpringerLink reveals **two well-developed but completely disconnected research streams** that define the thesis's novelty.

**The e-learning ontology stream** includes over 15 named OWL ontologies developed between 2006–2023. Sarwar et al. (2019) built CourseOntology for personalized content recommendation using machine learning, modeling Course, Learner, and LearningContent classes — validated with the OOPS! tool but containing no access control concepts. Rani et al. (2015) created `user.owl` and `course.owl` implementing the Felder-Silverman Learning Style Model with JADE software agents for adaptive content delivery. Gascueña et al. (2006) modeled learning materials with learning style and device characteristics. Jovanović et al.'s LOCO ontology (2006) bridges IMS Learning Design with learning objects through context intermediaries. The EDUC8 ontology (Iatrellis et al., 2019) models multi-facet learning pathways, while the IEEE LOM OWL ontology (Gluz & Vicari, 2012) represents learning object metadata with relationship types like "requires" and "isRequiredBy" — but these are metadata annotations, not enforceable access rules.

Of particular relevance to the ITMO context, **Kozlov F.A.** and Mouromtsev D.I. at ITMO's Laboratory of Information Science and Semantic Technologies developed the **ECOLE** (Enhanced Course Ontology for Linked Education) system for Open edX, published across multiple venues (KESW 2013, CCIS 394; KESW 2014, CCIS 468; WWW 2016 Companion). ECOLE interlinks terms across courses, calculates educational knowledge rates using NLP-based ontology population, and converts to SCORM — but contains **no access control modeling whatsoever**. The VICE pedagogic ontology comes closest to modeling prerequisites through "strong prerequisite" as an "admissibility role" for automated course planning, but treats this as sequencing logic rather than access policy.

Heiyanthuduwage et al. (2016) analyzed a corpus of **14 learning ontologies** and found that while one (Macquarie University) includes a `hasPrerequisite` property, none of the 14 contains any access control constructors. Their proposed "OWL 2 Learn" profile shows that learning ontologies use a much smaller subset of OWL 2 than available — a finding relevant to ontology design decisions.

**The ontology-based access control (OBAC) stream** is equally mature but entirely non-educational. Finin et al.'s **ROWLBAC** (SACMAT 2008) is the foundational work representing NIST Standard RBAC in OWL — modeling role hierarchies via `rdfs:subClassOf`, static separation of duty via `owl:disjointWith`, and using N3Logic/SWRL for dynamic constraints. Javanmardi et al.'s SBAC (2006) uses Subject/Object/Action ontologies with SWRL for semantic access control. Can & Unalir (2010) developed personalizable OBAC with the Rei policy language. Laouar et al. (2025) represent OrBAC in OWL with inconsistency-tolerant semantics for conflict resolution. **None of these has been applied to education.**

The intersection — an OWL ontology combining educational domain concepts with formal access control policy specification — **is an empty set in the literature**. This is the thesis's primary scientific novelty.

---

## SWRL has been applied to access control in many domains — except education

SWRL-based access control is a well-explored paradigm in healthcare, social networks, cloud computing, and enterprise systems — providing both a methodological foundation and a clear gap for the LMS domain.

**Carminati et al. (2011)** developed SWRL-based access control for online social networks, using a Social Network Ontology and Access Control Ontology with Pellet as the reasoner. They encountered the fundamental OWA limitation directly: "OWL and SWRL do not support negation-as-failure due to open-world assumption... This prevents us from reasoning collectively on positive and negative authorizations." Their workaround — separate `ac:cannotDo` predicates plus SPARQL enforcement — has become a standard pattern. **Beimel & Peleg (2011)** created SitBAC for healthcare, representing data-access scenarios as OWL Situation classes with SWRL property chains for knowledge inference. **Hsu (2013)** built LAPAR, integrating XACML with OWL and SWRL in a multi-layer framework, converting XACML policies to SWRL rules via XSLT, then to Jess inference engine statements. Rahmouni et al. (2014) mapped SWRL privacy rules to XACML policies for cloud healthcare, explicitly noting that "enforcement of semantic web rules on complex and heterogeneous architectures is expensive."

In education specifically, SWRL has been used for content sequencing (Chi, 2009), teaching strategy specification (Clemente et al., 2005), and learning process analysis (IEEE 2023, using Pellet for C++ course inference), but **never for access control**.

Zhang & Lobov (2024) in "SWRL-based approach for knowledge-based engineering" (Advanced Engineering Informatics, Vol. 61) demonstrated automated shaft design using OWL+SWRL for mathematical calculations and geometric model generation. While not about access control, their work confirms practical SWRL integration methodology and identifies key needs: a faster reasoner, user-friendly tools for mathematical expression conversion to SWRL, and better digital transformation of standards. Their finding that **reasoner performance remains a bottleneck** is directly relevant.

The **technical limitations of SWRL** for access control are well-documented and must be addressed in any thesis design:

- **No negation-as-failure**: Cannot express "if NOT completed, then deny" — only positive body atoms permitted. Workarounds include `owl:complementOf` class descriptions or separate negative predicates
- **No aggregation**: Cannot count completed activities (e.g., "completed 3 of 5 modules")
- **Monotonicity**: New facts can only be added, never retracted — once a permission is inferred, SWRL alone cannot revoke it
- **Open World Assumption**: Access control requires Closed World Assumption (default deny); SWRL assumes absence of information is not negation
- **DL-safe restriction**: Variables bind only to named individuals, ensuring decidability but limiting reasoning over inferred entities
- **No disjunction in rule heads**: Cannot express OR-branching in consequents
- **Performance**: Carminati et al. reported Pellet out-of-memory errors; rule execution is combinatorial in individuals × rules

Every SWRL-based access control system in the literature requires **architectural workarounds** — typically SPARQL for CWA enforcement, XACML for practical policy deployment, or separate negative predicates for denial.

---

## Formal verification of access policies is mature but has never reached LMS

The formal verification literature offers a rich toolkit of methods that have never been applied to educational access control.

**XACML analysis** has produced several tools. Fisler et al.'s **Margrave** (ICSE 2005) translates XACML policies to Multi-Terminal Binary Decision Diagrams (MTBDDs) for query-based verification and change-impact analysis, completing in under one second on real policies but supporting only a subset of XACML conditions. **Jebbaoui et al. (2015)** introduced a semantics-based approach using set-based intermediate representations with inference rules to detect three problem types: flaws (unreachable rules), conflicts (contradictory permit/deny decisions on overlapping targets), and redundancies (subsumed rules). Their SBA-XACML evaluation engine achieved **2.4–15× speedup** over the Sun PDP. NIST's ACPT integrates NuSMV model checking with combinatorial testing for RBAC/ABAC/MLS policies, though the project was archived in 2025. Hughes & Bultan (2008) encoded XACML policies as Boolean formulas for SAT-solver verification.

**Description Logic (DL) reasoning** has been applied to access control verification in several important works. Kolovski et al. (WWW 2007) formalized XACML using Defeasible Description Logics (DDL⁻), mapping policy inclusion to concept subsumption and change-impact analysis to concept satisfiability, implemented on the Pellet reasoner. Marfia et al. (2015) built an XACML-compliant framework using three ontologies (Policy TBox, Domain TBox, Domain ABox) where authorization decisions are made by sending positive and negative permission theorems to a DL reasoner. Huang et al. (2009) directly mapped XACML policies to a DL knowledge base, transforming conflict detection into **ABox consistency checking**. These works demonstrate that standard OWL 2 DL reasoning services map directly to verification tasks:

- **Consistency checking → conflict detection** (contradictory rules make the ontology inconsistent)
- **Class unsatisfiability → impossible conditions** (vacuous rules have no possible instances)
- **Subsumption checking → redundancy/shadowing** (subsumed policy rules are redundant)
- **Classification/realization → policy analysis** (organizing rules into hierarchy, determining applicable rules)

**Nazyrova et al. (2023)** in "Analysis of the Consistency of Prerequisites and Learning Outcomes of Educational Programme Courses by Using the Ontological Approach" (Applied Sciences, 13(4), 2661) is the **closest existing work to the thesis topic**. They built an OWL ontology in Protégé 5.5.0 modeling disciplines, skills, semesters, and academic years with object property chains for temporal ordering, then used DL Query and SPARQL to verify whether prerequisite skills are formed by prior courses in the curriculum timeline. Tested on a Software Engineering programme at a Kazakh university, their approach detects inconsistencies where prerequisites are unsatisfied. However, their work addresses **curriculum-level consistency** (are courses in the right semester order?), not **access control policy verification** (are conditional access rules conflict-free, complete, and satisfiable?).

**The gap is sharp**: DL-based policy verification exists for enterprise XACML systems, and ontological prerequisite checking exists for curriculum planning, but **no one has applied DL-reasoning to verify LMS access control rules** — the rules that determine whether a specific student can access a specific learning activity based on grades, completions, dates, and roles.

---

## Only one maintained reasoner supports both DL reasoning and SWRL

The choice of DL reasoner is constrained by a critical requirement: **native SWRL support with built-in functions**. Based on the systematic review by Abicht (2023, arXiv:2309.06888) covering 95+ reasoners, the Lam et al. (2023) benchmark at ESWC comparing 6 reasoners across ORE 2015's 1920 ontologies, and the original ORE 2015 competition report (Parsia et al., J. Automated Reasoning, 2017), the landscape is surprisingly narrow.

**Konclude** dominates performance benchmarks — first in consistency checking (1911/1920), classification (1862/1920), and realization (591/624) in Lam et al. 2023. But it **has no SWRL support** (neither syntax nor built-ins). **HermiT** ranks consistently second with robust hypertableau calculus, but while it handles DL-safe rules since v1.1, it supports **no SWRL built-ins** — meaning no comparisons, no math operations, no string functions — making it unsuitable for access control rules that inevitably require grade comparisons and date calculations. **ELK** handles only OWL 2 EL (no SWRL, insufficient expressivity). **FaCT++** is unmaintained since 2016 with no SWRL. Original **Pellet** last released in 2015 (OWLAPI 4 only) and ranks last in every benchmark category.

**Openllet** — the maintained fork of Pellet — emerges as the **only viable option** for native OWL 2 DL + SWRL integration. It supports OWLAPI 5, inherits Pellet's comprehensive SWRL implementation with most built-ins, and performed mid-range in benchmarks (1918/1920 loaded, 1595/1920 classified). Caveats include its last release in September 2019, known StackOverflowError bugs with certain SWRL-datatype combinations, incomplete built-in coverage, and AGPL licensing. It is available via Maven (`com.github.galigator.openllet:openllet-owlapi:2.6.5`).

A **hybrid architecture** offers a robust alternative: use HermiT or Konclude for DL reasoning (consistency checking, classification) and the **SWRLAPI Drools engine** (maintained by the Protégé project) for SWRL rule execution. The pipeline would be: load ontology → execute SWRL rules via Drools → assert materialized facts → run DL reasoner for verification. The tradeoff is architectural complexity and loss of inference provenance (Drools assertions become indistinguishable from stated axioms).

| Reasoner | SWRL Rules | SWRL Built-ins | DL Reasoning | Status | Best Use |
|---|---|---|---|---|---|
| **Openllet** | ✅ DL-safe | ⚠️ Subset | ✅ OWL 2 DL | Minimal maintenance | Primary choice for OWL+SWRL |
| **HermiT** | ✅ DL-safe | ❌ None | ✅ OWL 2 DL | Barely maintained | DL verification in hybrid arch |
| **Konclude** | ⚠️ Nominal schemas | ❌ None | ✅ OWL 2 DL | Maintained (slow) | Performance-critical DL tasks |
| **Drools/SWRLAPI** | ✅ | ✅ Full | ❌ OWL 2 RL only | Maintained | SWRL execution in hybrid arch |
| **Pellet** | ✅ | ✅ Most | ✅ OWL 2 DL | Unmaintained | Legacy reference |

For scalability, DL-safe SWRL rules bind only to named individuals, making execution **linear in the number of individuals but combinatorial across rules × bindings**. For a typical LMS deployment with thousands of users and hundreds of resources, incremental materialization rather than full re-reasoning is advisable.

---

## The confirmed novelty and what the thesis should contribute

The literature review reveals a **three-way gap** at the intersection of research streams that have never been combined:

**Stream 1** — E-learning ontologies (Sarwar 2019, Rani 2015, Kozlov/ECOLE 2013–2017, LOCO 2006, IEEE LOM OWL) model content, learners, and learning styles but never formalize access control policies.

**Stream 2** — Ontology-based access control (ROWLBAC 2008, SBAC 2006, Carminati 2011, Beimel & Peleg 2011) uses OWL+SWRL for policy specification in healthcare, social networks, and enterprise systems but has never targeted education or LMS.

**Stream 3** — Formal policy verification via DL-reasoning (Kolovski 2007, Marfia 2015, Huang 2009) and educational ontological consistency checking (Nazyrova 2023) exist independently — no work applies DL-based verification to LMS access rules.

The thesis can claim novelty on three fronts. First, **a new OWL ontology** that bridges educational domain concepts (Course, LearningActivity, Learner, Grade, CompletionState, Prerequisite) with access control concepts (AccessPolicy, Permission, Prohibition, Condition, Role) — modeling what no existing ontology does. Second, **SWRL rules for declarative access control** in the LMS domain, encoding conditions like grade thresholds, activity completion requirements, and temporal restrictions as semantic rules — applying a technique proven in healthcare and social networks to an untouched domain. Third, **DL-reasoner-based verification** of these rules — using consistency checking for conflict detection, unsatisfiability for impossible conditions, and subsumption for redundancy — something no LMS platform currently provides despite documented risks like Open edX's circular prerequisite problem.

The thesis committee's criticism about lacking formal verification is directly addressable: the verification component (mapping policy analysis to standard DL reasoning services) provides both theoretical grounding and practical value that current LMS platforms entirely lack. The work extends Nazyrova et al.'s curriculum-level consistency checking to fine-grained activity-level access control, extends ROWLBAC's general RBAC formalization to the educational domain, and extends Kolovski's DL-based XACML analysis to an ontology-native representation. These extensions are well-defined, the technical feasibility is demonstrated by adjacent work, and the Openllet reasoner (or a HermiT+Drools hybrid) provides the tooling needed for implementation and evaluation.