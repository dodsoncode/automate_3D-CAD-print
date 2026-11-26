# Detail levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate at full detail and add a Detail row (Low / Medium / High / Large) in step 2 that reduces the model in the page.

**Architecture:** Server drops the `octree_resolution` override. A new dependency-free `image3d/js/simplify.js` does quadric-error edge collapse per shell. `index.html` keeps the model as loaded (`state.original`) and derives each level from it.

**Tech Stack:** Python/FastAPI server, plain browser JS (UMD like `mesh.js`), pytest + Node snippets + Playwright.

**Spec:** `docs/superpowers/specs/2026-11-26-detail-levels-design.md`

## Global Constraints
- No new libraries; page stays one self-contained file after `python image3d/build.py`.
- Levels: Low 25,000; Medium 60,000; High = floor(0.95 x slicer limit) (142,500 with the 150,000 limit; 150,000 is the default without a server); Large = model as loaded.
- A closed shell must stay closed after reduction; no flipped triangles.
- Undo keeps 2 steps above 500,000 triangles, 5 above 100,000, 20 otherwise.
- Every existing element id and test keeps working.

## Review Focus
1. Model with many tiny pieces: each shell keeps at least 4 triangles (a shell never vanishes or turns open).
2. Open (not closed) input: reduction does not throw; boundary edges are kept, so the outline does not shrink.
3. Flat faces (cube sides, cut caps): collapses do not fold triangles over (volume sign and closedness kept).
4. Model already under the target: returned unchanged (same counts), page says so.
5. Choosing a level after an edit: warning shown, Undo restores the edited model.

---

### Task 1: Server generates at full detail
**Files:** Modify `image3d/server.py` (`DEFAULT_EXTRA`, docstring line 8), `render.yaml` (`HF_EXTRA_JSON` value `'{}'`), `image3d/tests/test_server.py:163`, `image3d/DEPLOY.md`.
- [ ] Test: change the expected call at test_server.py:163 to `"kwargs": {"image": "FILE:photo.png"}`; add `test_default_extra_is_empty`: `assert server.DEFAULT_EXTRA == {}`. Run, see FAIL.
- [ ] `DEFAULT_EXTRA = {}`; docstring/comment say Space default detail; `render.yaml` value `'{}'`; DEPLOY.md: after this change run Blueprint Manual sync.
- [ ] `python -m pytest -q image3d/tests/test_server.py` PASS. Commit.

### Task 2: `simplify.js` - quadric edge collapse
**Files:** Create `image3d/js/simplify.js`; add its `<script src="js/simplify.js">` next to `mesh.js` in `index.html` (build.py inlines script tags); test `image3d/tests/test_simplify.py` (Node snippets, same pattern as `test_mesh.py`).
**Interfaces:** Produces `simplifyModel(model, target) -> model` (model = array of `{v: number[], t: number[]}`), `simplifyShell(shell, target) -> shell`, global `I3DSimplify` in the browser / `module.exports` in Node.
- [ ] Tests (helpers: a UV sphere of ~20,000 triangles, cube, tube from test_mesh, `mesh.isClosed`, `mesh.volume`, `mesh.bbox`):
  - `test_sphere_reduces_to_target`: 20k sphere -> target 2,000: result tris <= 2,000 and >= 1,800; closed; volume within 3%; bbox each axis within 2%.
  - `test_under_target_is_unchanged`: cube with target 100 returns identical `v` and `t`.
  - `test_budget_split_by_size_and_floor_of_4`: model [sphere 20k, cube, 300 tiny tetrahedra]; target 3,000: total <= 3,000 + 4 x shells; every shell >= 4 tris and closed; shell count unchanged.
  - `test_flat_faces_do_not_fold`: subdivided box (each face 40x40 grid, 19,200 tris) -> 500: closed, volume within 1%, every triangle normal points outward (dot with centroid offset > 0).
  - `test_open_mesh_keeps_its_border`: a 100x100 grid plane (open) -> 1,000: no throw; boundary vertex set's bbox equals the input's.
  - `test_speed`: 900,000-triangle sphere -> 142,500 in under 30 s under Node (prints the time).
- [ ] Run, see FAIL (module missing).
- [ ] Implement: weld-indexed shells (input already welded); per-vertex quadrics from face planes; boundary edges get a heavy perpendicular-plane penalty; edge heap by cost with lazy invalidation; collapse target = optimal point if the 3x3 solve is well conditioned, else best of endpoints/midpoint; reject a collapse that would flip any neighbour triangle normal (dot < 0.2) or break the link condition (shared neighbours of the two vertices > 2 for an interior edge); per-shell budget = max(4, round(target x shellTris / totalTris)); compact at the end.
- [ ] Tests PASS. Commit.

### Task 3: Page Detail row
**Files:** Modify `image3d/index.html`; test `image3d/tests/test_page.py`.
**Interfaces:** Consumes `I3DSimplify.simplifyModel`. Produces ids `#detail-low`, `#detail-medium`, `#detail-high`, `#detail-large`, `#detail-info`; `App.detailTargets()` -> `{low, medium, high}`.
- [ ] Tests:
  - `test_detail_row_is_first_in_edit`: the first `h3` in `#step-2` is "Detail"; four buttons in order Low, Medium, High, Large.
  - `test_detail_levels_and_info`: open a 30,000-triangle sample; tap Low -> `#detail-info` text starts "25,000 triangles"; tap Large -> triangle count equals loaded count and info says "Large (as generated)".
  - `test_high_is_95_percent_of_the_slice_limit`: with server options limit 150,000 `App.detailTargets().high == 142500`; with no server also 142500.
  - `test_switching_does_not_lose_detail`: Low then High on a 200k sample: count > 60,000 (computed from the original, not from Low).
  - `test_under_target_says_so`: two_cubes.stl, tap Medium -> message "Already under 60,000 triangles; nothing changed." and counts unchanged.
  - `test_level_after_edit_warns_and_undo_restores`: cut, then Low -> message contains "starts again from the model as generated"; Undo -> count equals the cut model's.
  - `test_slice_hint_points_to_high`: model over the limit -> `#slice-hint` contains "Tap Detail: High".
  - `test_undo_limit_tiers`: `I3DApp.undoLimit()` is 2 for 600k, 5 for 200k, 20 for 50k triangles.
  - Big samples are made in the page with a JS sphere helper (no fixture files over 1 MB).
- [ ] Run, see FAIL.
- [ ] Implement: `state.original` set when a model is opened/generated (not by edits); `state.edited` true after any `apply` other than a detail change; buttons run `apply()` with "Reducing..." status first (setTimeout 0 so it paints); info line `N triangles - <Level>`; undo tiers; slice hint text; `python image3d/build.py`.
- [ ] Page tests PASS. Commit.

### Task 4: Docs, full run, PR
- [ ] `PRINTING.md`/`README.md`: Detail row and Large for Bambu Studio; `image3d/PROGRESS.md` Step 28; root `PROGRESS.md` entry; TASKS SL14 checked.
- [ ] `python -m pytest -q image3d/tests gui/tests` all pass. Screenshot step 2 at 390 px.
- [ ] Commit, push, PR (REST API).
