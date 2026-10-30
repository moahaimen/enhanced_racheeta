# Provenance — clean-room implementation

Racheeta 2.0 is an **independent implementation**. Nothing in this repository
is copied from the legacy Racheeta / `virach` code base (Flutter app, its
backend, its widgets, styles or API implementation).

## What the legacy project may be used for

- Understanding **historical business requirements** (which user types exist,
  which flows the product needs, which fields a domain object had).
- Reviewing **product ideas** at the level of "there was a map view of
  providers", never at the level of code, layout or assets.

## What is never reused

| Category | Rule |
| --- | --- |
| Source code (Dart, Python, JS, SQL) | Never copied, adapted or transliterated. |
| UI implementation (widgets, screens, CSS, themes) | Never copied. Racheeta 2.0 has its own design system (`docs/DESIGN_SYSTEM.md`). |
| Assets (logos, icons, images, fonts bundled with the old app) | Not used unless the owner explicitly approves a specific asset in writing. |
| API contracts and database schemas | Redesigned from the master plan; `docs/api/openapi.yaml` is the only contract. |
| Credentials, keys, service accounts | Never (see `SECURITY.md`). |

## Relationship to AKAD

The owner's other platform, AKAD, established a premium, block-oriented
design philosophy. Racheeta shares that **philosophy** (clear blocks, strong
hierarchy, generous spacing, restrained motion) but has its **own** tokens,
palette, typography, components and identity. No AKAD component, stylesheet
or token file is copied into this repository.

## Third-party material

- Open-source dependencies are pinned in `backend/requirements/*.txt` and
  `web/package-lock.json` under their own licences.
- Icons in `web/src/design-system/icons/` are drawn for Racheeta on a 24px
  grid; they are not an imported icon library.
- The interface font is **Cairo** (SIL Open Font License), self-hosted through the
  `@fontsource-variable/cairo` npm package; no third-party font request is made.
- The homepage backdrop (`web/src/pages/home/art.tsx`: orb, towers, palms) and the practitioner
  placeholder avatar (`PersonPlaceholder`) are original inline SVG drawn for Racheeta.
- The **homepage photographs** in `web/src/assets/home/` (the hero practitioner cut-out;
  the six service-card pictures were removed with the approved homepage, ADR-065) are **derived from the owner-supplied, AI-generated reference pack**
  (`racheeta_ui_reference_pack`, approved direction `04_final_merged_direction.png`). They are
  cropped / cut out / upscaled and exported as WebP; no text, logo or UI is baked in, and the full
  concept screenshots are **not** shipped. See `web/src/assets/home/README.md` for the exact
  derivation. The pack carries no licence metadata: the owner approved using these as project
  imagery; **the owner should confirm the rights position before the production launch**, or swap
  in commissioned photography (the files are referenced from two small components only).

## Enforcement

- Code review rejects contributions that reference or resemble legacy files.
- New engineers or AI assistants read this file (linked from `HANDOFF.md`)
  before touching UI or API code.

## Phase 3 statement

The billing, moderation, audit and jobs modules and every Phase 3 web page
were written from the Phase 3 brief and this repository's own conventions. No
code, schema, copy or asset was copied from the legacy Racheeta project or
from AKAD. The contact-leak patterns were authored for this repository.
