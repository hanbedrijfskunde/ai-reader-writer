# PRD — AI Reader & Writer

**Datum:** 2026-06-29
**Status:** Concept (ter review)
**Eigenaar:** docent / ontwikkelaar (single-user)
**Type:** Productietool voor docenten (lokaal)

---

## 1. Samenvatting

AI Reader & Writer is een **lokale, single-docent webtool** die docenten van een HBO-onderwijsmodule helpt om:

1. een set **bronnen** — PDF-documenten **en YouTube-video's** — samen te voegen tot één **pagina-getrouwe online reader**; PDF's behouden de oorspronkelijke tekst, afbeeldingen en opmaak op hun originele positie (verbatim), video's verschijnen als thumbnail + link met een AI-synopsis;
2. per bron **verdiepende vragen** te genereren op een door de docent gekozen **Bloom-niveau**;
3. ná het op *Definitief* zetten van de reader een **toetsset** (meerkeuze + open) te genereren, verdeeld per **leeruitkomst** volgens opgegeven **wegingen**, met kwaliteitsborging conform het bestaande [handboek toetssamenstelling](workflow-toets-samenstelling.html).

Bronnen zijn van twee types: **PDF-documenten** en **YouTube-video's**. Beide voeden dezelfde pijplijn (verdiepende vragen, toetsset); alleen de weergave in de reader verschilt.

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
| D1 | Bronnen samenvoegen tot één reader | Twee of meer bronnen (PDF's en/of video's) worden samengevoegd tot één doorbladerbare reader met behoud van originele opmaak |
| D2 | Verbatim weergave (PDF) | Tekst, afbeeldingen en lay-out van PDF's blijven exact gelijk aan de bron (geen AI-herschrijving van leertekst) |
| D2b | Video-integratie | Docent plakt een YouTube-URL; AI haalt transcript + metadata op, maakt een korte synopsis, en plaatst thumbnail + link in de reader |
| D3 | Verdiepende vragen per bron | Per bron (document of video) genereert de AI verdiepende vragen op het gekozen Bloom-niveau; docent kan reviewen/redigeren |
| D4 | Reader-levenscyclus | Reader kan van *Concept* naar *Definitief*; finalisatie ontgrendelt de toetsfase |
| D5 | Toetsset per leeruitkomst | Toetsset wordt verdeeld over leeruitkomsten volgens wegingen (`aantal = totaal × weging`) |
| D6 | Kwaliteitsborging toets | MC-vragen worden gegenereerd én auto-beoordeeld (validiteit/betrouwbaarheid/techniek, 1-5) conform handboek; ondermaatse vragen worden geregenereerd |
| D7 | Export | Reader → HTML + PDF; toetsset → CSV/Word/PDF |

---

## 4. Scope

### In scope (MVP)
- Upload van bron-PDF's, **YouTube-URL's**, rubric en leeruitkomsten via een **webfrontend**.
- **YouTube-video toevoegen via URL:** AI haalt transcript + metadata op (via de [youtube-transcript-skill](#62-hergebruikte-skill-youtube-transcript)), genereert een **synopsis**, en plaatst **thumbnail + link** in de reader.
- Automatisch samenvoegen van bronnen; **verwijderen/herordenen op bronniveau** (documenten én video's).
- Eén **Bloom-doelniveau** per reader.
- **Verdiepende vragen per bron** (Bloom-gestuurd), voor zowel documenten als video's.
- **Video-transcript telt mee voor de toetsset** (koppelbaar aan leeruitkomst, meegenomen in wegingen).
- Reader-status *Concept* → *Definitief*.
- **Toetsset** (gemengd MC + open), verdeeld **per leeruitkomst** op basis van wegingen.
- **Auto-beoordeling** van vragen met regeneratie-lus.
- Export: reader (HTML + PDF), toetsset (CSV + Word + PDF).

### Buiten scope (bewust — YAGNI)
- Accounts, authenticatie, multi-user/samenwerking.
- Studentinteractie, voortgangsopslag, beoordeling/cijfers.
- AI-herschrijving of -samenvatting van de PDF-**leertekst** (blijft verbatim). *Uitzondering:* voor video's maakt de AI wél een korte **synopsis** van het transcript — dat is helpertekst, geen vervanging van verbatim bronmateriaal.
- OCR voor gescande PDF's → **fase 2**.
- QTI/LMS-import-export → **fase 2**.
- Sectie-granulariteit fijner dan bronniveau (bv. per hoofdstuk/pagina binnen een document) → mogelijk **fase 2**.

---

## 5. Architectuurprincipe

**Scheiding van weergave en verwerking.** Elke bron voedt twee onafhankelijke kanalen:

- **Weergavekanaal** — toont de bron op zijn natuurlijke manier: PDF's pagina-getrouw (verbatim + visuals op originele positie), video's als thumbnail + link met synopsis. Verandert niets aan de inhoud.
- **Verwerkingskanaal** — levert **platte tekst** aan Claude voor vraaggeneratie: bij PDF's de tekstlaag, bij video's het transcript. De student ziet deze tekst nooit; hij voedt alleen de AI.

Een YouTube-video is daarmee simpelweg een **derde bron-type** dat hetzelfde verwerkingskanaal voedt — het transcript speelt exact dezelfde rol als de PDF-tekstlaag. Hierdoor verdwijnt het fidelity-risico uit het weergavekanaal, terwijl het AI-kanaal vrij met tekst kan werken.

---

## 6. Techniekkeuze

| Laag | Keuze | Toelichting |
|---|---|---|
| Backend | **Python 3.10+ / FastAPI** | Sluit aan op bestaand mc-toetsgenerator-werk en het handboek |
| Frontend | **Browser-UI** (server-rendered HTML + lichte JS, bv. HTMX) | Upload van bronnen/rubric/leeruitkomsten; geen zware build-tooling voor een lokale app |
| PDF-verwerking | **PyMuPDF (fitz)** | Laden, samenvoegen, tekstlaag-extractie, render, PDF-export |
| Video-verwerking | **Playwright + Chromium** (via youtube-transcript-skill) | Transcript + metadata + thumbnail ophalen; `PyYAML` als dependency |
| Reader-weergave | **PDF.js** of voor-gerenderde pagina-afbeeldingen; thumbnail+link voor video | Pagina-getrouwe weergave met ingevoegde HTML-vraagblokken |
| AI | **Claude API** (`anthropic`) | Key in `.env.local` (in `.gitignore`) |
| Opslag | **SQLite / JSON** + lokale projectmap | Projectstaat, bronnen, vragen, statussen |

### 6.2 Hergebruikte skill: youtube-transcript

Voor het ophalen van YouTube-data hergebruiken we de bestaande **youtube-transcript-skill** (`fetch_transcript.py`, oorspronkelijk uit het ai-wiki-project). Deze drijft een echte Chromium via Playwright en is daarmee robuust tegen YouTube's Proof-of-Origin-tokengating (simpelere libraries zoals `youtube-transcript-api`/`yt-dlp` falen daar intermitterend op).

- **Interface:** `python fetch_transcript.py "<URL>" --json` → JSON met metadata (titel, kanaal, duur, **thumbnail-URL's**, hoofdstukken, beschrijving) + transcriptsegmenten met timestamps.
- **Integratie:** het script wordt **gevendord** in de repo (bv. `app/integrations/youtube_transcript/`) zodat de tool zelfstandig draait, met bronvermelding naar het origineel.
- **Eenmalige setup:** `pip install playwright PyYAML` + `python -m playwright install chromium`.
- De **Video Ingest**-component (§8) roept dit script aan in `--json`-modus, laat Claude het ASR-transcript opschonen en er een synopsis van maken, en slaat het resultaat op in de Reader Store.

---

## 7. Workflow / levenscyclus

```
1. Project aanmaken
2. Bronnen toevoegen:
   - PDF's uploaden (source-docs/)
   - YouTube-URL's plakken → transcript+metadata ophalen → synopsis
        │
        ▼
3. Auto-merge → Reader-CONCEPT
   (docent kan bronnen — documenten én video's — verwijderen / herordenen)
        │
        ▼
4. Bloom-doelniveau kiezen (1 niveau voor hele reader)
        │
        ▼
5. Verdiepende vragen genereren (Claude, per bron, op tekstlaag/transcript)
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
| **Ingest & Merge** | PDF's laden en samenvoegen; elke bron = sectie | bron-PDF's | gemergede reader + bron-index | PyMuPDF |
| **Video Ingest** | YouTube-URL → transcript+metadata ophalen, ASR opschonen, **synopsis** genereren | YouTube-URL | video-bron (titel, thumbnail, link, transcript, synopsis) | youtube-transcript-skill (Playwright), Claude API |
| **Reader Store** | Projectstaat beheren | acties | persistente staat (bronnen, volgorde, status, Bloom-niveau, vragen) | SQLite/JSON |
| **Text Extractor** | Platte tekst per bron leveren aan AI (PDF-tekstlaag of video-transcript) | bron | platte tekst (intern) | PyMuPDF |
| **Vraaggenerator (verdiepend)** | Verdiepende vragen per bron op Bloom-niveau | tekst + Bloom-niveau | schema-gevalideerde vragen | Claude API |
| **Reader Renderer/Export** | Pagina-getrouwe HTML + vraagblokken; video als thumbnail+link+synopsis; PDF-hercompositie | reader-model | HTML + PDF | PDF.js, PyMuPDF |
| **Toets Generator** | LU+rubric parsen, wegingen→stratificatie, MC+open genereren, auto-beoordelen, exporteren | reader-tekst (PDF + transcripts) + LU's + rubric + parameters | toetsset (CSV/Word/PDF) | Claude API, handboek |

---

## 9. Datamodel (indicatief)

- **Project**: id, naam, status (`concept` | `definitief`), bloom_doelniveau, aangemaakt_op.
- **Bron (sectie)**: id, project_id, **type** (`document` | `video`), titel, volgorde, ingesloten (bool).
  - *type `document`*: bestandsnaam, pagina-aantal.
  - *type `video`*: youtube_url, video_id, kanaal, duur, thumbnail_url, transcript (intern), synopsis.
- **VerdiependeVraag**: id, bron_id, bloom_niveau, vraagtekst, (optioneel) modelantwoord, status (concept/akkoord).
- **Leeruitkomst**: id, project_id, code, omschrijving, weging (%).
- **RubricCriterium**: id, project_id, omschrijving, (koppeling naar leeruitkomst), niveaubeschrijvingen.
- **Toetsvraag**: id, project_id, leeruitkomst_id, **bron_id** (herkomst: document of video), type (`mc` | `open`), bloom_niveau, stam, opties[], sleutel/modelantwoord, beoordelingsscores (validiteit/betrouwbaarheid/techniek 1-5), toelichtingen.

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
| Video zonder transcript (`no transcript section`) | Metadata + thumbnail + link tóch tonen; geen synopsis/vragen, docent waarschuwen |
| Transcript-panel rendert niet / region-lock / age-gate | Retry met hogere timeout; daarna metadata-only met melding (zie skill-failure-modes) |
| Ongeldige / niet-YouTube-URL | Valideren vóór ophalen; duidelijke foutmelding |
| AI-output wijkt af van schema | Schema-validatie + automatische retry |
| Wegingen ≠ 100% | Normaliseren + waarschuwen |
| Afronding vragenaantallen | Largest-remainder; geen LU valt onbedoeld weg |
| Claude API-fout / rate limit | Retry met backoff; tussenresultaten bewaren |
| Reader nog niet *Definitief* | Toetsfase geblokkeerd met duidelijke melding |

---

## 13. Export

| Artefact | Formaten | Fase |
|---|---|---|
| Reader | HTML (pagina-getrouw + vraagblokken; video = thumbnail+link+synopsis), PDF | MVP |
| Toetsset | CSV (vraag, type, sleutel/modelantwoord, LU, Bloom, scores), Word, PDF | MVP |
| Toetsset | QTI/LMS-import | Fase 2 |

---

## 14. Testaanpak

- **Unit:** bron-detectie, weging→vragenaantal (largest-remainder), schema-validatie AI-output, deterministische MC-checks uit het handboek, YouTube-URL-validatie + parsen van skill-JSON.
- **Integratie:** end-to-end met de twee bestaande PDF-bronnen ([Over leiderschap](../source-docs/Over%20leiderschap_DIG.pdf), [Pathologie voor verpleegkundigen](../source-docs/Pathologie%20voor%20verpleegkundigen_DIG.pdf)) **plus minimaal één YouTube-video** (mét en zónder transcript, om beide paden te dekken).
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
5. **Vendoren youtube-transcript-skill:** voorstel is het script in de repo kopiëren (`app/integrations/youtube_transcript/`) met bronvermelding, zodat de tool zelfstandig draait. Akkoord, of liever als externe dependency/submodule houden?
6. **Synopsis-lengte:** voorstel = korte synopsis (±100-150 woorden). Nader te bepalen.
```
