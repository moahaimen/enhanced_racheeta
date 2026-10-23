# Homepage photographs

Derived from the owner-supplied reference pack `racheeta_ui_reference_pack` (AI-generated concept
art; approved direction `04_final_merged_direction.png`). See `docs/PROVENANCE.md`.

| File | What it is | Size |
| --- | --- | --- |
| `hero-doctor.webp` | Practitioner cut-out for the hero (560 px wide, transparent background) | ≈ 24 kB |
| `hero-doctor-sm.webp` | Same, 360 px wide, served under 768 px | ≈ 14 kB |
| `svc-doctors|facilities|products|jobs|estate|hire.webp` | Service-card pictures, 520 × 156 px | 5–13 kB each |

Derivation: crop of the approved reference at its native resolution → for the hero, OpenCV GrabCut
foreground extraction with a hand-tuned rectangle/mask → Lanczos upscale (Pillow) → WebP export
(lossy, alpha channel for the cut-out). No text is baked into any file; they are decorative
(`alt=""`) and the headline, buttons, search, labels and navigation are real HTML.

Rules: no external hotlinks, no stock or paid source, below-the-fold pictures are
`loading="lazy"`, the hero picture is the only high-priority image. Replacing a picture means
replacing the file with the same name and aspect ratio.
