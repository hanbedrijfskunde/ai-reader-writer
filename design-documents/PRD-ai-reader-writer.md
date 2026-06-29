# PRD — AI Reader & Writer

**Datum:** 2026-06-29
**Status:** Concept (ter review)
**Eigenaar:** docent / ontwikkelaar (single-user)
**Type:** Productietool voor docenten (lokaal)

---

## 1. Samenvatting

AI Reader & Writer is een **lokale, single-docent webtool** die docenten van een HBO-onderwijsmodule helpt om:

1. een set brondocumenten (PDF's) samen te voegen tot één **pagina-getrouwe online reader** met de oorspronkelijke tekst, afbeeldingen en opmaak op hun originele positie (verbatim);
2. per document **verdiepende vragen** te genereren op een door de docent gekozen **Bloom-niveau**;
3. ná het op *Definitief* zetten van de reader een **toetsset** (meerkeuze + open) te genereren, verdeeld per **leeruitkomst** volgens opgegeven **wegingen**, met kwaliteitsborging conform het bestaande [handboek toetssamenstelling](workflow-toets-samenstelling.html).

De tool is een **productietool**: docenten genereren en exporteren materiaal. Studenten werken **niet** in de app; er zijn geen accounts, geen studentvoortgang en geen cijferadministratie.

---

## 2. Doelgroep & gebruikscontext

- **Primaire gebruiker:** één docent die een module samenstelt, draait de app lokaal.
- **Indirecte ontvangers:** studenten (lezen de geëxporteerde reader elders, bv. in een LMS) — buiten de app.
- **Omgeving:** lokale machine, lokale brondocumenten, eigen Claude API-key in `.env.local`.

---

## 3. Doelen & succescriteria

| # | Doel | Succescriterium |
|---|---|---|
| D1 | Brondocumenten samenvoegen tot één reader | Twee of meer PDF's worden samengevoegd tot één doorbladerbare reader met behoud van originele opmaak |
| D2 | Verbatim weergave | Tekst, afbeeldingen en lay-out blijven exact gelijk aan de bron (geen AI-herschrijving van leertekst) |
| D3 | Verdiepende vragen per document | Per document genereert de AI verdiepende vragen op het gekozen Bloom-niveau; docent kan reviewen/redigeren |
| D4 | Reader-levenscyclus | Reader kan van *Concept* naar *Definitief*; finalisatie ontgrendelt de toetsfase |
| D5 | Toetsset per leeruitkomst | Toetsset wordt verdeeld over leeruitkomsten volgens wegingen (`aantal = totaal × weging`) |
| D6 | Kwaliteitsborging toets | MC-vragen worden gegenereerd én auto-beoordeeld (validiteit/betrouwbaarheid/techniek, 1-5) conform handboek; ondermaatse vragen worden geregenereerd |
| D7 | Export | Reader → HTML + PDF; toetsset → CSV/Word/PDF |

---

## 4. Scope

### In scope (MVP)
- Upload van bron-PDF's, rubric en leeruitkomsten via een **webfrontend**.
- Automatisch samenvoegen van documenten; **verwijderen/herordenen op documentniveau**.
- Eén **Bloom-doelniveau** per reader.
- **Verdiepende vragen per document** (Bloom-gestuurd).
- Reader-status *Concept* → *Definitief*.
- **Toetsset** (gemengd MC + open), verdeeld **per leeruitkomst** op basis van wegingen.
- **Auto-beoordeling** van vragen met regeneratie-lus.
- Export: reader (HTML + PDF), toetsset (CSV + Word + PDF).

### Buiten scope (bewust — YAGNI)
- Accounts, authenticatie, multi-user/samenwerking.
- Studentinteractie, voortgangsopslag, beoordeling/cijfers.
- AI-herschrijving of -samenvatting van de leertekst.
- OCR voor gescande PDF's → **fase 2**.
- QTI/LMS-import-export → **fase 2**.
- Sectie-granulariteit fijner dan documentniveau → mogelijk **fase 2**.

---

## 5. Architectuurprincipe

**Scheiding van weergave en verwerking.** Eén databron (de PDF) voedt twee onafhankelijke kanalen:

- **Weergavekanaal** — toont de originele pagina's getrouw; verandert niets aan de inhoud (verbatim + visuals op originele positie).
- **Verwerkingskanaal** — extraheert de tekstlaag en stuurt die naar Claude voor vraaggeneratie. De student ziet deze tekstlaag nooit; hij voedt alleen de AI.

Hierdoor verdwijnt het fidelity-risico volledig uit het weergavekanaal, terwijl het AI-kanaal vrij met tekst kan werken.

---

## 6. Techniekkeuze

| Laag | Keuze | Toelichting |
|---|---|---|
| Backend | **Python 3.10+ / FastAPI** | Sluit aan op bestaand mc-toetsgenerator-werk en het handboek |
| Frontend | **Browser-UI** (server-rendered HTML + lichte JS, bv. HTMX) | Upload van bronnen/rubric/leeruitkomsten; geen zware build-tooling voor een lokale app |
| PDF-verwerking | **PyMuPDF (fitz)** | Laden, samenvoegen, tekstlaag-extractie, render, PDF-export |
| Reader-weergave | **PDF.js** of voor-gerenderde pagina-afbeeldingen | Pagina-getrouwe weergave met ingevoegde HTML-vraagblokken |
| AI | **Claude API** (`anthropic`) | Key in `.env.local` (in `.gitignore`) |
| Opslag | **SQLite / JSON** + lokale projectmap | Projectstaat, secties, vragen, statussen |

---

## 7. Workflow / levenscyclus

```
1. Project aanmaken
2. Bron-PDF's uploaden (source-docs/)
        │
        ▼
3. Auto-merge → Reader-CONCEPT
   (docent kan documenten verwijderen / herordenen)
        │
        ▼
4. Bloom-doelniveau kiezen (1 niveau voor hele reader)
        │
        ▼
5. Verdiepende vragen genereren (Claude, per document, op tekstlaag)
        │
        ▼
6. Docent reviewt/redigeert → status DEFINITIEF
        │  (ontgrendelt toetsfase)
        ▼
7. Upload leeruitkomsten + rubric (wegingen per LU),
   totaal aantal vragen, MC/open-verhouding
        │
        ▼
8. Toetsset genereren (stratificatie per LU) + auto-beoordelen + regenereren
        │
        ▼
9. Export: reader → HTML + PDF ; toetsset → CSV/Word/PDF
```

---

## 8. Componenten

Elk component heeft één duidelijk doel, een afgebakende interface en is los testbaar.

| Component | Doet | Input | Output | Hangt af van |
|---|---|---|---|---|
| **Ingest & Merge** | PDF's laden en samenvoegen; documenten = secties | bron-PDF's | gemergede reader + sectie-index | PyMuPDF |
| **Reader Store** | Projectstaat beheren | acties | persistente staat (secties, volgorde, status, Bloom-niveau, vragen) | SQLite/JSON |
| **Text Extractor** | Tekstlaag per document leveren aan AI | document | platte tekst (intern) | PyMuPDF |
| **Vraaggenerator (verdiepend)** | Verdiepende vragen per document op Bloom-niveau | tekst + Bloom-niveau | schema-gevalideerde vragen | Claude API |
| **Reader Renderer/Export** | Pagina-getrouwe HTML + vraagblokken; PDF-hercompositie | reader-model | HTML + PDF | PDF.js, PyMuPDF |
| **Toets Generator** | LU+rubric parsen, wegingen→stratificatie, MC+open genereren, auto-beoordelen, exporteren | reader-tekst + LU's + rubric + parameters | toetsset (CSV/Word/PDF) | Claude API, handboek |

---

## 9. Datamodel (indicatief)

- **Project**: id, naam, status (`concept` | `definitief`), bloom_doelniveau, aangemaakt_op.
- **Document (sectie)**: id, project_id, bestandsnaam, volgorde, ingesloten (bool), pagina-aantal.
- **VerdiependeVraag**: id, document_id, bloom_niveau, vraagtekst, (optioneel) modelantwoord, status (concept/akkoord).
- **Leeruitkomst**: id, project_id, code, omschrijving, weging (%).
- **RubricCriterium**: id, project_id, omschrijving, (koppeling naar leeruitkomst), niveaubeschrijvingen.
- **Toetsvraag**: id, project_id, leeruitkomst_id, type (`mc` | `open`), bloom_niveau, stam, opties[], sleutel/modelantwoord, beoordelingsscores (validiteit/betrouwbaarheid/techniek 1-5), toelichtingen.

**Rol van de rubric:** de wegingen sturen de verdeling **per leeruitkomst**. De rubric levert daarnaast het **kwaliteits-/beoordelingskader** voor met name de **open vragen** (modelantwoord en beoordelingswijzer) en kan het Bloom-niveau per leeruitkomst informeren.

---

## 10. Vraagverdeling (stratificatie per leeruitkomst)

Conform het handboek:

```
aantal_vragen(LU) = round( totaal_toetsvragen × weging(LU) )
```

- Wegingen die **niet optellen tot 100%** worden genormaliseerd (met waarschuwing).
- Afronding via **largest-remainder** zodat het totaal exact klopt en geen LU onbedoeld op 0 vragen valt.
- De MC/open-verhouding wordt binnen elke LU toegepast (bv. lagere Bloom-niveaus → meer MC, hogere → meer open), instelbaar per toetsset.

---

## 11. Kwaliteitsborging toetsvragen

De toetsmodule hanteert het [handboek toetssamenstelling](workflow-toets-samenstelling.html) als **canonieke standaard** (niet dupliceren, verwijzen):

- **Genereren** met de handboekregels (o.a. ⚑-aanscherpingen uit docentfeedback) als instructie.
- **Auto-beoordelen** per vraag op drie dimensies (elk 1-5):
  - *Validiteit* — meet de vraag wat beoogd is (juist cognitief/Bloom-niveau)?
  - *Betrouwbaarheid* — discriminerend vermogen, geen ambiguïteit, gokkansreductie.
  - *Technische kwaliteit* — stam, correct antwoord, afleiders.
- **Deterministische checks** als vangnet (lengte-bias, absolute termen, ontkenning).
- **Regeneratie-lus:** vragen onder een drempel (bv. dimensie < 4) worden opnieuw gegenereerd.

---

## 12. Foutafhandeling

| Situatie | Gedrag |
|---|---|
| Gescande PDF zonder tekstlaag | Detecteren, docent waarschuwen; OCR is fase 2 |
| AI-output wijkt af van schema | Schema-validatie + automatische retry |
| Wegingen ≠ 100% | Normaliseren + waarschuwen |
| Afronding vragenaantallen | Largest-remainder; geen LU valt onbedoeld weg |
| Claude API-fout / rate limit | Retry met backoff; tussenresultaten bewaren |
| Reader nog niet *Definitief* | Toetsfase geblokkeerd met duidelijke melding |

---

## 13. Export

| Artefact | Formaten | Fase |
|---|---|---|
| Reader | HTML (pagina-getrouw + vraagblokken), PDF | MVP |
| Toetsset | CSV (vraag, type, sleutel/modelantwoord, LU, Bloom, scores), Word, PDF | MVP |
| Toetsset | QTI/LMS-import | Fase 2 |

---

## 14. Testaanpak

- **Unit:** sectie-/document-detectie, weging→vragenaantal (largest-remainder), schema-validatie AI-output, deterministische MC-checks uit het handboek.
- **Integratie:** end-to-end met de twee bestaande bronnen ([Over leiderschap](../source-docs/Over%20leiderschap_DIG.pdf), [Pathologie voor verpleegkundigen](../source-docs/Pathologie%20voor%20verpleegkundigen_DIG.pdf)).
- **Kwaliteit:** steekproef van gegenereerde MC-vragen handmatig vergelijken met handboek-voorbeelden (§3 goede/slechte vragen).

---

## 15. Fasering

- **Fase 1 (MVP):** alle in-scope-items hierboven.
- **Fase 2:** OCR voor gescande PDF's; QTI-export; eventueel fijnere sectie-granulariteit (hoofdstuk/pagina); meerdere projecten/readers naast elkaar.

---

## 16. Open punten / aannames ter bevestiging

1. **Frontend-stack:** voorstel is server-rendered HTML + HTMX (licht, geen build-stap). Akkoord, of liever een SPA (React)?
2. **Bloom-taxonomie:** Nederlandstalige revised Bloom (Onthouden, Begrijpen, Toepassen, Analyseren, Evalueren, Creëren). Doelniveau = "t/m X".
3. **Drempel auto-beoordeling:** voorstel = regenereren bij een dimensiescore < 4 (max N pogingen). Drempel/aantal nader te bepalen.
4. **Leeruitkomst↔rubric-koppeling:** wegingen per LU zijn leidend; rubric voedt vooral open-vraagbeoordeling. Bevestigen of dat volstaat.
```
