# Jobs profession taxonomy: how to add a profession

The profession vocabulary is **code, not data**. `apps/jobs/types.py` (`Profession`,
`PROFESSION_GROUPS`) is the single source of truth. Adding a profession is a reviewed code
change plus a deploy; there is no runtime admin screen for it, by design. The profession decides
who may post or search a role, so a new one goes through review and tests.

## Supported procedure (rehearsed 2026-11-07)

Seven steps (an optional eighth for demo data). To add, for example, `RESPIRATORY_THERAPIST` (clinical) or `LEGAL_ADVISOR` (non-clinical):

| Step | File | Notes |
|---|---|---|
| 1 | `backend/apps/jobs/types.py` | Add the code to `Profession` (≤ 32 characters, upper snake case, English label). Add it to **exactly one** group in `PROFESSION_GROUPS`. The group decides clinical scope: `HEALTHCARE` = clinical (only healthcare employers may post or search it); every other group is open to BUSINESS employers too. |
| 2 | `python manage.py makemigrations jobs` | An `AlterField` of the `profession` choices on `JobPost` and `JobSeekerProfile`. On PostgreSQL it is a **no-op** (`sqlmigrate` prints `(no-op)`): no table change, no data change. |
| 3 | `make openapi` | Regenerates `docs/api/openapi.yaml` (`ProfessionEnum`). |
| 4 | `web/src/api/jobs.types.ts` | Add the code to the `Profession` union and to the same group, in the same position, in `PROFESSION_GROUPS`. |
| 5 | `web/src/i18n/locales/ar.json` and `en.json` | Add `professions.<CODE>` in both languages. |
| 6 | `web/src/design-system/components/JobCard/professionIcon.ts` | Choose an icon. |
| 7 | `mobile/lib/features/jobs/presentation/job_labels.dart`, `mobile/lib/l10n/app_ar.arb` and `app_en.arb`, then `flutter gen-l10n` | Add the code to `professionCodes` (same order) and a label case, and add the `profession<Code>` label in both ARB files. Commit the generated files. |
| 8 | (optional) demo content | `apps/demo/content/*.py` if the demo should show it. |

Nothing else changes. These follow automatically:
- the public `GET /api/v1/jobs/professions`;
- the grouped `<select>`s on the four pages (`ProfessionOptions`);
- job search filters and talent search;
- the BUSINESS-employer scope (`CLINICAL_PROFESSIONS` is derived from the group);
- the job-seeker dashboard's matching jobs.

## What fails when a step is forgotten (verified)

In a throwaway worktree, the procedure was rehearsed with `RESPIRATORY_THERAPIST` (HEALTHCARE) and
`LEGAL_ADVISOR` (BUSINESS). One step at a time was left out:

| Left out | Caught by |
|---|---|
| A group for the new code | import-time assertion in `types.py` ("every profession needs exactly one group") |
| Step 2 (migration) | `makemigrations --check` (CI) |
| Step 3 (OpenAPI) | CI's OpenAPI diff ("docs/api/openapi.yaml is stale") |
| Step 4 (web mirror) | backend `test_the_web_mirror_has_the_same_groups_order_and_members`; web `matches the server vocabulary in docs/api/openapi.yaml` |
| Step 5 (labels) | web `has an Arabic and English label for every profession and group` |
| Step 6 (icon) | web `chooses an icon for every profession` |
| Step 7 (mobile) | mobile `openapi_contract_test.dart`: "job vocabularies the app labels and filters on match the backend choices" (CI, Flutter job) |

With every step done:
- the full jobs suite passed (580 tests);
- `makemigrations --check` reported no changes;
- OpenAPI was in sync with 0 errors;
- all 591 web tests and `tsc` passed;
- the BUSINESS employer could post and submit `LEGAL_ADVISOR` and was refused `RESPIRATORY_THERAPIST`.

The rehearsal was not committed.

## Limitations

1. **The web copy is static.** The web keeps its own copy of the groups so the selects render
   instantly with no loading state. A new profession therefore needs a web deploy too; the tests
   above make forgetting it impossible to merge. The server endpoint `GET /jobs/professions`
   exists for clients that prefer to load the vocabulary.
2. **Codes are permanent.** Job posts, seeker profiles, filters and saved links store the code.
   Never rename or remove one. To retire a profession, leave it in place (an "other" group if
   needed).
3. **Moving a profession between groups changes who may hire for it.** It applies to new posts,
   edits and submissions, which are re-checked at submit. Posts a BUSINESS employer **already
   published** in a profession that becomes clinical are not withdrawn automatically. An admin
   reviews them with the existing job moderation.
4. **Arabic and English only.** Both labels are required; there is no third language.
5. **The mobile app is covered by step 7.** Its contract test fails CI until its list matches the
   server's. Codes it does not know yet still render as the raw code, so an older installed app
   never hides a job.
6. **Specialties are separate.** A profession does not create medical specialties
   (`apps/specialties`). A new clinical profession that needs specialty filters needs those
   added separately.
