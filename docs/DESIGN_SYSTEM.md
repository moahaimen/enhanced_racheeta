# Racheeta design system

> Home: `web/src/design-system/` — `tokens/` (values), `styles/` (CSS custom
> properties, base, utilities), `icons/`, `components/`, `layouts/`, `index.ts`.
> Pages import from `'../design-system'` only.

## 1. Brand philosophy

Racheeta is a premium, trustworthy medical platform for Iraq, Arabic-first.
The interface is **block-based**: a page is a sequence of clearly bounded
surfaces (hero, search, results, information cards), each with one job, strong
alignment and generous whitespace. Motion is subtle, shadows are soft, borders
do most of the separating. Nothing on a page is invented: every number, name
and status comes from the API or is a clearly labelled empty state.

Relationship to AKAD: Racheeta shares the owner's block-oriented design
philosophy but has its own tokens, palette, typography and components. It is
not a copy of AKAD (see `PROVENANCE.md`).

## 2. Colour

Source of truth: `tokens/colors.ts`; CSS variables in `styles/tokens.css`
(a test keeps both equal).

### Brand teal

| Step | Hex | Use |
| --- | --- | --- |
| 50 | `#eef8f7` | brand surfaces (`--surface-brand`) |
| 100 | `#d5efec` | soft accents, hero gradients |
| 200 | `#abdfd9` | |
| 300 | `#7ccac2` | brand borders (`--border-brand`) |
| 400 | `#4db1a8` | focus ring |
| 500 | `#2a9a90` | brand mid-tone, illustrations |
| 600 | `#1f7f77` | **primary actions** (`--surface-brand-strong`) |
| 700 | `#196660` | brand text (`--text-brand`), hover |
| 800 | `#154f4b` | |
| 900 | `#103c39` | |

The main brand colour is 600: saturated enough to be recognisable, dark
enough for white text (contrast ≥ 4.5:1).

### Neutrals

White `#ffffff`, off-white `#f7f9f9` (page background), greys 100–400 for
surfaces and borders, 500 muted text, 600 secondary text, **800 charcoal
headings** (`--text-primary`). Pure black is not used for text.

### Semantic

success `#1e8e5a`, warning `#b7791f`, error `#c4383b`, info `#2f6fb7`, each
with a `-soft` background. Only `Alert`, `Badge`, `ErrorState` and form errors
use them; feature CSS never references raw colours.

### Role tokens

`--surface-primary/secondary/tertiary/brand`, `--text-primary/secondary/muted/brand/on-brand`,
`--border-subtle/strong/brand`, `--focus-ring`. Components reference roles,
not scale steps, so a future theme changes roles only.

## 3. Typography

Font: **IBM Plex Sans Arabic** (Arabic and Latin in one family), fallbacks
Noto Sans Arabic → system UI. Loaded with `display=swap` (`web/index.html`).

| Role | Size (mobile → desktop) | Weight | Line-height |
| --- | --- | --- | --- |
| display | 2 → 2.5 rem | 700 | 1.15 |
| h1 | 1.75 → 2 rem | 700 | 1.2 |
| h2 | 1.5 rem | 700 | 1.25 |
| h3 | 1.25 rem | 600 | 1.3 |
| section | 1.125 rem | 600 | 1.35 |
| body | 1 rem | 400 | 1.6 |
| body-sm | 0.9375 rem | 400 | 1.55 |
| label | 0.875 rem | 600 | 1.4 |
| caption | 0.8125 rem | 400 | 1.4 |
| button | 0.9375 rem | 600 | 1.2 |

Arabic gets the same scale; line-height 1.6 for body keeps Arabic ascenders
and dots readable. Form controls are 44px tall (2.75rem) for comfortable
Arabic input and touch targets.

## 4. Spacing, widths, rhythm

4px base: `--space-1` (4) … `--space-20` (80). Section rhythm
`--space-section` = 40px mobile / 64px desktop; gutter 16 / 32px. Content
widths: sm 640, md 880, lg 1120 (default), xl 1280 (shell, home, discovery).
`Container`, `PageStack` (24px between blocks) and the `grid-2` / `grid-auto`
utilities are the layout primitives.

## 5. Radius

sm 8 (small chips, focus outline), **md 12 = controls and buttons**,
**lg 16 = cards**, **xl 24 = hero blocks**, full = badges only. Elements are
never uniformly pill-shaped.

## 6. Shadows and borders

`--shadow-xs/sm/md/lg`; cards use `--shadow-card` (sm) and lift to
`--shadow-card-hover` (md). Every card also has a 1px `--border-subtle`
border. Heavy shadows and glassmorphism are not used; the header uses a
light blur only.

## 7. Motion

`--duration-fast` 120ms, `base` 180ms, `slow` 260ms with a standard easing.
Used for: hover colour changes, card lift, button press, skeleton shimmer.
`prefers-reduced-motion` sets durations to 0 and stops shimmer.

## 8. Icons

`icons/` — one owned line-icon set (24px grid, 1.75px stroke,
`currentColor`). `<Icon name="…" />` is decorative unless `label` is given.
Directional icons pass `flipInRtl`. No emoji, no mixed libraries.

## 9. Components (implemented)

| Group | Components |
| --- | --- |
| Actions | `Button` (primary/secondary/ghost/subtle/danger; sm/md/lg; `loading`), `LinkButton`, `IconButton`, `ApiActionButton` |
| Surfaces | `Card`, `SectionCard`, `DashboardBlock` (alias), `FeatureCard` (with `upcoming`), `StatCard` |
| Feedback | `Alert`, `Badge`, `Spinner`, `LoadingState`, `LoadingOverlay`, `Skeleton`, `EmptyState`, `ErrorState`, `AsyncPage` |
| Forms | `FormField`, `TextField`, `PasswordField`, `SearchField`, `Select`, `Textarea`, `Checkbox`, `CheckboxGroup`, `FormSection`, `FormActions`, `useFormErrors` |
| Navigation | `Tabs` (+ `tabPanelProps`), `Pagination`, `SiteHeader` (with mobile panel), `SiteFooter` |
| Layout | `Container`, `PageStack`, `PageHeader`, `SectionHeader` |
| Domain | `ProviderCard`, `ProviderCardSkeleton`, `Avatar`, `JobCard`(+`Skeleton`, `formatSalary`), `TalentCard`, `UsageMeter`, `JobStatusBadge`/`ApplicationStatusBadge`/`InvitationStatusBadge` |

`LinkButton` accepts router `state` (used to return to `/employer` after login).

`ApiActionButton` reports every completed action through `onSuccess`, including
actions that resolve with nothing (a DELETE / 204); only a click ignored while
another call is pending is skipped (`DUPLICATE_CALL` from `useAsyncAction`).

Not built yet (no page needs them): `Modal/Dialog`, `Drawer`, `Dropdown`,
`Tooltip`, `Toast`, `Breadcrumb`, `Radio`, `QuickActionCard`, `ActivityCard`.
Add them in `components/` with a CSS module and a behaviour test when a page
requires them; do not build page-local variants.

## 10. Loading rules (owner requirement)

- Every backend-connected page or block renders inside `AsyncPage` (spinner
  state or `skeleton`), then an `ErrorState` with retry, then content.
- Every backend-connected button is an `ApiActionButton`: disabled while
  pending, `aria-busy`, circular `Spinner`, **stable dimensions** (the label
  stays in the layout, hidden, while the spinner overlays it), duplicate
  clicks ignored, state restored on success/error.
- Navigation uses `LinkButton`, never `ApiActionButton`.

## 11. RTL behaviour

- `<html dir>` follows the language (`i18n/index.ts`).
- All CSS uses logical properties (`inline-start/end`, `block-start/end`,
  `margin-inline`, `padding-inline`, `inset-inline`). No `left/right`
  except the select chevron, which is mirrored under `[dir='rtl']`.
- Directional icons use `flipInRtl`; `Tabs` mirrors arrow keys.
- Latin-only values (email, phone, URL, ids, coordinates) are wrapped with
  the `.ltr` utility or `dir="ltr"` so they read correctly inside RTL text.

## 12. Responsive rules

Breakpoints 480 / 768 / 1024 / 1280 (min-width). Grids collapse to one column
below 768; the header switches to the mobile panel below 1024; hero stacks
below 1024. No horizontal overflow at 360–430px: cards use `min-inline-size:
0`, long values use `overflow-wrap: anywhere`, tab lists scroll.

## 13. Accessibility rules

- Real `<button>` / `<a>` elements; `IconButton` requires a label.
- Every field has a `<label>`; hints and errors are linked with
  `aria-describedby`; errors use `role="alert"`; invalid fields set
  `aria-invalid`.
- Visible focus ring (`--focus-ring`, 2px offset) on every focusable element.
- Contrast: text tokens against surfaces meet WCAG AA; brand-on-white uses
  700, white-on-brand uses 600.
- Disabled buttons are truly `disabled`; loading buttons are `aria-busy`.
- ARIA only where semantics are missing (tablist, status regions).

## 14. Correct vs incorrect

| Do | Don't |
| --- | --- |
| `<ApiActionButton action={save}>Save</ApiActionButton>` | `<button onClick={() => api.save()}>` |
| `<AsyncPage load={…}>{data => …}</AsyncPage>` | `useEffect` + `useState` loading flags in a page |
| `<Card>`, `<SectionCard title>` for blocks | `<div className="card">` with local CSS |
| `color: var(--text-secondary)` | `color: #666` |
| `padding-inline-start: var(--space-4)` | `padding-left: 16px` |
| `<EmptyState title="No providers yet">` | a fake list, "—" placeholders, or invented stats |
| `<Icon name="search" />` | emoji or a second icon library |
| `<Badge tone="outline">Coming soon</Badge>` on an unimplemented module | a working-looking button that goes nowhere |

## 15. CSS architecture

Global: `styles/tokens.css` (custom properties), `styles/base.css` (reset,
typography, focus, reduced motion), `styles/utilities.css` (a dozen
utilities). Everything else is a **CSS Module** next to its component or
page (`*.module.css`). The former single global stylesheet was removed. No UI
framework is used; the system is owned by the repository.
