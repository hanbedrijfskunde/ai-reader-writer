# PRD — AI Reader & Writer (online dienst)

**Datum:** 2026-06-30
**Status:** Concept (ter review)
**Eigenaar:** ontwikkelaar / aanbieder (single founder)
**Type:** Online SaaS-productietool voor docenten HBO
**Voorganger:** [PRD-ai-reader-writer.md](PRD-ai-reader-writer.md) (lokale single-user PoC)

---

## 1. Samenvatting

AI Reader & Writer wordt een **online, self-serve dienst** waarmee individuele HBO-docenten:

1. een set **bronnen** — PDF-documenten **en YouTube-video's** — samenvoegen tot één **pagina-getrouwe reader** (PDF's verbatim met behoud van tekst, afbeeldingen en opmaak; video's als thumbnail + link met AI-synopsis);
2. per bron **verdiepende vragen** genereren op een gekozen **Bloom-niveau**;
3. ná het op *Definitief* zetten van de reader optioneel een **toetsset** (meerkeuze + open) genereren, verdeeld per **leeruitkomst** volgens wegingen, met kwaliteitsborging conform het [handboek toetssamenstelling](workflow-toets-samenstelling.html).

De dienst is een **productietool**: docenten genereren en **exporteren** materiaal (HTML/PDF/CSV/Word). **Studenten werken niet in de app** en de dienst host geen reader-inhoud publiek — de docent verspreidt de export zelf via het eigen LMS. Er zijn geen studentaccounts, geen studentvoortgang en geen cijferadministratie.

### Wat verandert t.o.v. de PoC

| Aspect | PoC (lokaal) | Online dienst |
|---|---|---|
| Gebruikers | één docent, lokaal | vele docenten, **multi-tenant** met accounts |
| Toegang | lokale machine | publiek, **self-serve registratie** |
| AI | Claude API (eigen key) | **Vertex AI / Gemini** (centraal geleverd) |
| Kosten | docent betaalt eigen API | **pay-per-use**: basis per reader + per document; toets per batch |
| Opslag | SQLite + lokale mappen | **Cloud SQL (Postgres)** + **Cloud Storage** |
| Verwerking | inline (blokkeert) | **async** via Cloud Tasks + worker |
| Hosting | n.v.t. | **Google Cloud**, regio **europe-west4 (NL)** |

---

## 2. Doelgroep, verdienmodel & gebruikscontext

- **Klant & gebruiker:** individuele HBO-docent (self-serve), meldt zich zelf aan, betaalt per verwerking.
- **Distributiemodel:** volledige **publieke self-serve lancering** — iedereen kan registreren, betalen en direct gebruiken.
- **Indirecte ontvangers:** studenten (lezen de geëxporteerde reader elders, bv. in een LMS) — **buiten de app**.
- **Tenant-model:** **één docent = één account**; geen gedeelde projecten tussen docenten (B2B/instelling is fase 2).

---

## 3. Doelen & succescriteria

| # | Doel | Succescriterium |
|---|---|---|
| D1 | Self-serve onboarding | Docent kan zonder tussenkomst registreren, e-mail verifiëren, opwaarderen en de eerste reader maken |
| D2 | Bronnen samenvoegen tot één reader | Twee of meer bronnen (PDF's en/of video's) worden samengevoegd tot één doorbladerbare reader met behoud van originele opmaak |
| D3 | Verbatim weergave (PDF) | Tekst, afbeeldingen en lay-out van PDF's blijven exact gelijk aan de bron (geen AI-herschrijving van leertekst) |
| D4 | Video-integratie | Docent plakt een YouTube-URL; AI haalt transcript + metadata op, maakt een synopsis, en plaatst thumbnail + link in de reader |
| D5 | Verdiepende vragen per bron | Per bron genereert Gemini verdiepende vragen op het gekozen Bloom-niveau; docent kan reviewen/redigeren |
| D6 | Reader-levenscyclus | Reader kan van *Concept* naar *Definitief*; finalisatie ontgrendelt de toetsfase |
| D7 | Toetsset per leeruitkomst | Toetsset wordt verdeeld over leeruitkomsten volgens wegingen (`aantal = totaal × weging`) |
| D8 | Kwaliteitsborging toets | MC-vragen worden gegenereerd én auto-beoordeeld (validiteit/betrouwbaarheid/techniek, 1-5); ondermaatse vragen worden geregenereerd |
| D9 | Export | Reader → HTML + PDF; toetsset → CSV/Word/PDF |
| D10 | Betaalbaar gebruik | Saldo-check vóór verwerking; correcte afschrijving ná succesvolle job; mislukte job = geen kosten |
| D11 | Tenant-isolatie | Een docent kan nooit projecten/bronnen van een andere docent zien of wijzigen (afgedwongen op app- én databaselaag) |
| D12 | AVG-conformiteit | Privacyverklaring, verwijderrecht, data in EU (NL), Vertex AI traint niet op klantdata |

---

## 4. Scope

### In scope (MVP — eerste publieke release)
1. Registratie/login + e-mailverificatie (Firebase Auth); account + wallet + **gratis starttegoed**.
2. Project aanmaken; bronnen toevoegen (PDF-upload naar Cloud Storage + YouTube-URL).
3. **Async verwerking** (Cloud Tasks + worker): tekst-/transcript-extractie, synopsis, verdiepende vragen via **Vertex AI/Gemini**.
4. Bronnen verwijderen/herordenen; één **Bloom-doelniveau** per reader.
5. Reader-status *Concept* → *Definitief*; **export HTML + PDF**.
6. Optionele **toetsset** (gemengd MC + open) per **batch van 10 vragen**, verdeeld per leeruitkomst, met auto-beoordeling + regeneratielus; export CSV/Word/PDF.
7. **Prepaid betaling via Stripe** (wallet opwaarderen, webhook, BTW); prijslijst basis/document/toetsbatch; saldo-check vóór verwerking.
8. Multi-tenancy met Postgres RLS; AVG-basis (privacyverklaring, verwijderen); Cloud Logging/Monitoring.

### Buiten scope (bewust — YAGNI / fase 2)
- **Studentinteractie, voortgangsopslag, beoordeling/cijfers** (blijft buiten de app).
- **Publiek hosten van reader-inhoud** (aansprakelijkheidsgrens — alleen export).
- AI-herschrijving/-samenvatting van PDF-**leertekst** (blijft verbatim). *Uitzondering:* korte **synopsis** van video-transcript.
- Instelling/opleiding-accounts (B2B), SSO, verwerkersovereenkomsten → fase 2.
- Teamdeling / gedeelde projecten → fase 2.
- OCR voor gescande PDF's → fase 2.
- QTI/LMS-import-export → fase 2.
- Sectie-granulariteit fijner dan bronniveau → fase 2.
- Abonnementsvariant naast pay-per-use → fase 2.

---

## 5. Architectuurprincipes

1. **Scheiding van weergave en verwerking** (ongewijzigd t.o.v. PoC). Elke bron voedt twee kanalen: een **weergavekanaal** (PDF pagina-getrouw; video als thumbnail+link+synopsis) en een **verwerkingskanaal** (platte tekst/transcript naar Gemini). De student ziet de verwerkingstekst nooit.
2. **Koop wat gevaarlijk is om te bouwen.** Auth (Firebase) en betaling (Stripe) zijn beveiligings­kritisch en opgeloste problemen — gebruik managed providers, besteed eigen energie aan de unieke kern (reader + toetsgeneratie).
3. **Tenant-isolatie is een typefout om te vergeten, niet iets om te onthouden.** Elke datatoegang vereist een `user_id`; geen functie of query bestaat zonder.
4. **Zwaar werk is altijd asynchroon.** Geen blokkerende request mag wachten op PDF-render, YouTube-fetch of AI-generatie.
5. **AI achter één interface.** Alle modelcalls lopen via een `LLMProvider`-abstractie (implementatie: Vertex AI/Gemini), zodat modelversies te swappen en in tests te mocken zijn.
6. **Prepaid, nooit onbetaald.** Saldo-check vóór verwerking; werkelijke afschrijving ná succes; mislukte job kost niets.

---

## 6. Techniekkeuze (GCP-native)

| Laag | Keuze | Toelichting |
|---|---|---|
| Compute (web) | **Cloud Run** (FastAPI-container) | Autoscaling, schaalt naar 0; sluit aan op bestaande FastAPI-code |
| Compute (worker) | **Cloud Run** (aparte worker met Chromium/Playwright + PyMuPDF) | Zware/async taken gescheiden van de web-tier |
| Taakqueue | **Cloud Tasks** | Async dispatch, retries met backoff |
| Database | **Cloud SQL for PostgreSQL** | Multi-tenant met `user_id` + **Row-Level Security** |
| Bestandsopslag | **Cloud Storage** | Bron-PDF's, gerenderde reader, exports; per-tenant prefix |
| Auth | **Firebase Authentication / Identity Platform** | E-mail+wachtwoord + Google-login + e-mailverificatie |
| AI | **Vertex AI — Gemini** | Synopsis, verdiepende vragen, toetsgeneratie + auto-beoordeling; achter `LLMProvider`-interface |
| Video-verwerking | **Playwright + Chromium** (in worker) | Transcript + metadata + thumbnail (youtube-transcript-skill) |
| PDF-verwerking | **PyMuPDF (fitz)** | Laden, samenvoegen, tekstextractie, render, PDF-export |
| Secrets | **Secret Manager** | API-keys, Stripe-secret, DB-credentials |
| Betaling | **Stripe** | Checkout, webhook, EU-BTW (Stripe Tax), facturen |
| Observability | **Cloud Logging + Monitoring** | Logs, metrics, alerting, foutopvang |
| Frontend | **Server-rendered HTML + lichte JS (HTMX)** | Lichte UI; jobstatus via polling/SSE |
| Regio | **europe-west4 (Nederland)** | Data-residency NL; AVG-verhaal; fallback EU-regio voor Vertex indien een Gemini-model niet in NL beschikbaar is |

### 6.1 Hergebruikte skill: youtube-transcript
Het bestaande `fetch_transcript.py` (Playwright/Chromium) wordt **gevendord** in de worker-container (`app/integrations/youtube_transcript/`). Interface: `python fetch_transcript.py "<URL>" --json` → JSON met metadata (titel, kanaal, duur, thumbnail-URL's, hoofdstukken, beschrijving) + transcriptsegmenten. De **Video Ingest**-job roept dit aan, laat Gemini het transcript opschonen en er een synopsis van maken, en slaat het resultaat op.

### 6.2 Modelmigratie Claude → Gemini
De PoC stemde prompts en kwaliteitsdrempels af op Claude. **Alle prompts en de auto-beoordelingsdrempels van het toetshandboek moeten opnieuw worden gevalideerd op Gemini** vóór publieke lancering (zie §13, risico R1). De `LLMProvider`-interface isoleert deze laag.

---

## 7. Workflow / levenscyclus

```
1. Registreren → e-mail verifiëren → account + wallet + gratis starttegoed
        │
        ▼
2. Project aanmaken
        │
        ▼
3. Bronnen toevoegen:
   - PDF's uploaden (Cloud Storage)
   - YouTube-URL's plakken
        │  (saldo-check vóór verwerking; kostenraming getoond)
        ▼
4. Async verwerking (Cloud Tasks → worker):
   transcript/tekst-extractie → synopsis → auto-merge → Reader-CONCEPT
        │
        ▼
5. Bloom-doelniveau kiezen + verdiepende vragen genereren (Gemini, per bron)
        │
        ▼
6. Docent reviewt/redigeert → status DEFINITIEF (ontgrendelt toetsfase)
        │
        ▼
7. (optioneel) Leeruitkomsten + wegingen invoeren; aantal toetsbatches (×10) kiezen
        │
        ▼
8. Toetsset genereren (stratificatie per LU) + auto-beoordelen + regenereren
        │
        ▼
9. Export: reader → HTML + PDF ; toetsset → CSV/Word/PDF
```

---

## 8. Componenten

| Component | Doet | Input | Output | Hangt af van |
|---|---|---|---|---|
| **Auth & Account** | Registratie, login, e-mailverificatie, accountbeheer | credentials | geverifieerde `user_id` + sessie | Firebase Auth |
| **Wallet & Billing** | Saldo bijhouden, opwaarderen, afschrijven, facturen | Stripe-events, jobresultaten | saldo, transacties, facturen | Stripe, Postgres |
| **Pricing** | Kostenraming per actie (reader/document/toetsbatch) | actie + parameters | bedrag in euro's | prijslijst |
| **Ingest & Merge** | PDF's laden en samenvoegen; elke bron = sectie | bron-PDF's | gemergede reader + bron-index | PyMuPDF, Cloud Storage |
| **Video Ingest** | YouTube-URL → transcript+metadata, opschonen, synopsis | YouTube-URL | video-bron | youtube-transcript-skill, Vertex AI |
| **Job Orchestrator** | Async taken inplannen, status bewaken, idempotent afronden | actieverzoek | `Job` + resultaat | Cloud Tasks, worker |
| **Reader Store** | Projectstaat beheren (tenant-gescoped) | acties + `user_id` | persistente staat | Postgres (RLS) |
| **Text Extractor** | Platte tekst per bron leveren aan AI | bron | platte tekst (intern) | PyMuPDF |
| **Vraaggenerator (verdiepend)** | Verdiepende vragen per bron op Bloom-niveau | tekst + Bloom-niveau | schema-gevalideerde vragen | Vertex AI |
| **Reader Renderer/Export** | Pagina-getrouwe HTML + vraagblokken; PDF-hercompositie | reader-model | HTML + PDF | PyMuPDF |
| **Toets Generator** | LU+wegingen→stratificatie, MC+open genereren, auto-beoordelen, exporteren | reader-tekst + LU's + parameters | toetsset (CSV/Word/PDF) | Vertex AI, handboek |

---

## 9. Datamodel (indicatief)

### Bestaande entiteiten (krijgen tenantgrens)
- **Project**: id, **user_id**, naam, status (`concept`|`definitief`), bloom_doelniveau, reader_title, module_code, academic_year, aangemaakt_op.
- **Bron (Source)**: id, project_id, type (`document`|`video`), titel, volgorde, ingesloten, tekst (intern), `processing`; voor document: bestandsnaam (Storage-pad), pagina-aantal; voor video: youtube_url, video_id, kanaal, duur, thumbnail_url, synopsis, quote.
- **VerdiependeVraag (Question)**: id, source_id, volgorde, vraagtekst.
- **Leeruitkomst**: id, project_id, code, titel, weging, bloom_niveau, volgorde.
- **Toetsvraag**: id, project_id, leeruitkomst_id, source_id, type (`mc`|`open`), bloom_niveau, stam, opties[], sleutel/modelantwoord, scores (validiteit/betrouwbaarheid/techniek 1-5), toelichtingen, volgorde.

> Onderliggende entiteiten erven de tenant via hun `project_id`; **elke query loopt via een tenant-gescopte projectlookup**.

### Nieuwe entiteiten (SaaS)
- **User**: id, email, naam, firebase_uid, status, aangemaakt_op.
- **Wallet**: user_id, saldo (euro), bijgewerkt_op.
- **Transaction**: id, user_id, type (`topup`|`usage`|`grant`|`refund`), bedrag (±), bron (Stripe-event-id of job-id, **uniek/idempotent**), tijdstip.
- **UsageEvent**: id, user_id, project_id, operatie (`synopsis`|`vragen`|`toets`), document_type, gemini_tokens_in/out, omgerekend_bedrag, tijdstip. *(Interne margemeting; nooit getoond aan docent.)*
- **Job**: id, user_id, project_id, type, status (`queued`|`running`|`done`|`failed`), foutmelding, tijdstip, geschat_bedrag, werkelijk_bedrag.
- **StripeCustomer**: user_id, stripe_customer_id.

---

## 10. Multi-tenancy & tenant-isolatie

Gelaagde verdediging — een lek hier betekent dat docent A het materiaal van docent B ziet:

1. **Applicatielaag:** elke `store.py`-functie krijgt `user_id` als **verplichte** parameter. Eén gedeelde helper `get_owned_project(user_id, project_id)` (404 als niet eigenaar); alle project-routes lopen hierdoor. `get_project(id)` zonder `user_id` bestaat niet meer.
2. **Auth-laag:** FastAPI-dependency haalt `user_id` uit het geverifieerde Firebase-ID-token; routes vertrouwen **nooit** een `user_id` uit de request-body.
3. **Databaselaag (vangnet):** **Postgres Row-Level Security**-policies op `user_id`, zodat een vergeten `WHERE`-clausule niet meteen lekt. De applicatie zet per request de tenant-context (bv. `SET app.current_user_id`).

---

## 11. Prijsmodel & facturatie (pay-per-use, prepaid)

### Prijsstructuur
- **Vaste basisprijs per verwerkte reader** — samenstellen, renderen, exporteren.
- **Variabele prijs per verwerkt document** (PDF of video) — extractie/transcript + synopsis + verdiepende vragen voor die bron.
- **Optionele toetsset** — vaste prijs **per batch van 10 vragen**; docent kiest het aantal batches.
- Totale readerprijs = `basis + (aantal_documenten × documentprijs)`, **vooraf getoond** vóór verwerking.

### Betaalmechaniek
- **Prepaid wallet** in euro's; docent waardeert op via **Stripe Checkout**.
- **Gratis starttegoed** bij registratie (genoeg voor één kleine reader).
- **Saldo-check vóór verwerking** (blokkeer bij onvoldoende saldo + "opwaarderen"-knop).
- **Afschrijving ná succesvolle job**, idempotent op `job_id`; **mislukte job = geen kosten**.
- **Stripe-webhook** boekt opwaarderingen bij, **idempotent** op Stripe-event-id (`Transaction.bron`).
- **Stripe Tax** voor EU-BTW; facturen via Stripe.
- Marge bewaakt via `UsageEvent` (werkelijke Gemini-tokenkost per document/toets).

---

## 12. Vraagverdeling (stratificatie per leeruitkomst)

Conform het handboek (ongewijzigd t.o.v. PoC):

```
aantal_vragen(LU) = round( totaal_toetsvragen × weging(LU) )
```
- Totaal = `aantal_batches × 10`.
- Wegingen die niet optellen tot 100% worden genormaliseerd (met waarschuwing).
- Afronding via **largest-remainder** zodat het totaal exact klopt en geen LU onbedoeld op 0 valt.
- MC/open-verhouding per LU (lagere Bloom → meer MC, hogere → meer open), instelbaar per toetsset.

---

## 13. Kwaliteitsborging toetsvragen

Het [handboek toetssamenstelling](workflow-toets-samenstelling.html) blijft de **canonieke standaard** (verwijzen, niet dupliceren):
- **Genereren** met de handboekregels (incl. ⚑-aanscherpingen) als instructie.
- **Auto-beoordelen** per vraag op drie dimensies (elk 1-5): validiteit, betrouwbaarheid, technische kwaliteit.
- **Deterministische checks** als vangnet (lengte-bias, absolute termen, ontkenning).
- **Regeneratie-lus:** vragen onder de drempel (bv. dimensie < 4) worden opnieuw gegenereerd (max N pogingen).
- **Let op (R1):** drempels en prompts zijn op Claude afgesteld en moeten op **Gemini** opnieuw gevalideerd worden.

---

## 14. Foutafhandeling

| Situatie | Gedrag |
|---|---|
| Onvoldoende saldo | Blokkeer verwerking vóór de job; toon kostenraming + opwaarderen |
| Job mislukt (worker) | Status `failed`, **geen** afschrijving, tussenresultaten bewaard, docent geïnformeerd |
| Gescande PDF zonder tekstlaag | Detecteren, docent waarschuwen; OCR is fase 2 |
| Video zonder transcript | Metadata + thumbnail + link tóch tonen; geen synopsis/vragen, waarschuwen; geen documentkosten voor het AI-deel |
| Transcript-panel/region-lock/age-gate | Retry met hogere timeout; daarna metadata-only met melding |
| Ongeldige / niet-YouTube-URL | Valideren vóór ophalen; duidelijke foutmelding |
| AI-output wijkt af van schema | Schema-validatie + automatische retry |
| Stripe-webhook dubbel geleverd | Idempotent op event-id; geen dubbele bijschrijving |
| Worker-retry na gedeeltelijk succes | Idempotent op `job_id`; geen dubbele afschrijving |
| Wegingen ≠ 100% | Normaliseren + waarschuwen |
| Vertex AI-fout / rate limit | Retry met backoff; job blijft `running`/`failed`, saldo intact |
| Reader nog niet *Definitief* | Toetsfase geblokkeerd met duidelijke melding |
| Toegang tot andermans project | 404 (tenant-isolatie), gelogd |

---

## 15. AVG / juridisch / compliance

- **Export-only = aansprakelijkheidsgrens:** de dienst host nooit publiek verbatim uitgeverstekst; de docent verspreidt zelf via het LMS.
- **Data-residency:** alle opslag/compute in **europe-west4 (NL)**; Vertex AI in EU. **Vertex AI traint niet op klantdata** (prompts/uploads) — verkoopargument richting docenten.
- **Persoonsgegevens:** beperkt tot het docent-account; **geen studentgegevens** in de app.
- **Privacyverklaring + verwerkingsregister;** subprocessors (Google Cloud, Stripe) vermeld.
- **Verwijderrecht:** docent kan project + bronnen verwijderen; verwijdering wist ook Cloud Storage-objecten en gerelateerde records.
- **Auteursrecht:** uploadrechten liggen bij de docent (voorwaarden); de dienst bewaart bronnen alleen t.b.v. verwerking/export door diezelfde docent.

---

## 16. Export

| Artefact | Formaten | Fase |
|---|---|---|
| Reader | HTML (pagina-getrouw + vraagblokken; video = thumbnail+link+synopsis), PDF | MVP |
| Toetsset | CSV (vraag, type, sleutel/modelantwoord, LU, Bloom, scores), Word, PDF | MVP |
| Toetsset | QTI/LMS-import | Fase 2 |

---

## 17. Testaanpak

- **Unit:** bron-detectie; weging→vragenaantal (largest-remainder); schema-validatie AI-output; deterministische MC-checks; YouTube-URL-validatie + parsen van skill-JSON; **prijsraming** (reader/document/toetsbatch); **idempotente afschrijving**; **tenant-isolatie helpers** (`get_owned_project`).
- **Integratie:** end-to-end met bestaande PDF-bronnen **plus** minimaal één YouTube-video (mét en zónder transcript); **Stripe-webhook** (test-events, dubbele levering); **job-levenscyclus** (succes, fout-geen-afschrijving, retry-idempotentie).
- **Beveiliging:** RLS-policies (docent A kan project van docent B niet lezen via directe DB-query); auth-dependency weigert ongeldige/ontbrekende tokens.
- **Kwaliteit:** steekproef gegenereerde MC-vragen op **Gemini** vergelijken met handboek-voorbeelden (R1-validatie).

---

## 18. Fasering

- **Fase 1 (MVP — publieke lancering):** alle in-scope-items uit §4.
- **Fase 2:** OCR; QTI-export; fijnere sectie-granulariteit; **instelling/opleiding-accounts (B2B) + SSO + verwerkersovereenkomsten**; teamdeling; meerdere readers op schaal; eventueel abonnementsvariant naast pay-per-use.

---

## 19. Risico's & open punten

| # | Risico / punt | Aanpak |
|---|---|---|
| R1 | **Modelmigratie Claude → Gemini** verandert toetskwaliteit | Prompts + drempels opnieuw valideren vóór lancering; `LLMProvider`-interface; kwaliteitssteekproef |
| R2 | **Marge-erosie** bij dure documenten/toetsbatches | `UsageEvent` meet werkelijke tokenkost; prijslijst bijstelbaar; saldo-check vooraf |
| R3 | **Misbruik/scraping** (gratis starttegoed, kostbare AI) | E-mailverificatie verplicht vóór verwerking; rate limits; beperkt starttegoed |
| R4 | **Koude-start latency** Cloud Run + zwaar Playwright-image | Min-instances overwegen voor worker; image slank houden; async UX met jobstatus |
| R5 | **Gemini-modelbeschikbaarheid** in europe-west4 | Vóór bouw verifiëren; fallback Vertex EU-regio met data-residency EU |
| R6 | **Tenant-lek** | Gelaagde isolatie (app + RLS); beveiligingstests; 404 i.p.v. 403 |
| R7 | **Stripe/AVG-administratie** (BTW, facturen, subprocessors) | Stripe Tax; privacyverklaring + verwerkingsregister bij lancering |

---

## 20. Aannames (bevestigd in brainstorm)

1. Self-serve, individuele docent betaalt (B2B = fase 2).
2. **Export-only**; geen publieke hosting van reader-inhoud (auteursrecht).
3. **Centrale AI** via Vertex AI/Gemini; docent levert geen eigen key.
4. **Pay-per-use, prepaid**: basis per reader + per document; toets per batch van 10.
5. Volledige **publieke self-serve lancering** als eerste release.
6. **GCP-native**, regio **europe-west4 (NL)**; **Stripe** als betaalcomponent.
7. **Eén docent = één account**; multi-tenancy met **Postgres RLS**.
