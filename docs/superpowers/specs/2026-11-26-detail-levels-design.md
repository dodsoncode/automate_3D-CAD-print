# Image3D: Detail levels (Low / Medium / High / Large) - design

Date: 2026-11-26. Status: approved in chat by Jacob 2026-11-26 (approach B, then this design).

## Intent and why
Generated models must be sliceable on the site (OrcaSlicer limit 150,000 triangles), and Jacob also wants a
full-detail "Large" model to slice himself in Bambu Studio. Today the server asks Hugging Face for a lighter mesh
(`octree_resolution` 128, about 115,000 triangles on the one model measured), so "as generated" is never large, and
High is not guaranteed to stay under the limit.

## Goals
- Generate once at the Space's default (full) detail (no `octree_resolution` override; one photo measured at about
  917,000 triangles, about 10 s on 2026-11-11).
- Step 2 (Edit) gets a Detail row: Low 25,000, Medium 60,000, High = 95% of the slicer limit (about 142,500; 150,000
  default without a server), Large = exactly as generated (for Bambu Studio). Shows the current triangle count.
- Switch freely: every level is computed from the model as loaded, so no detail is lost by switching.
- High is always sliceable.

## Non-goals / anti-goals
- No new libraries (the page is a single self-contained file); no change to slicing or sending.
- A reduction must not open a closed model (that would break slicing) or wreck the outline.
- No regenerate-to-change-detail (it costs Hugging Face GPU quota).

## Approaches
- A. Choose detail before Generate (octree resolution per level): cheap (2-3 h) but needs regenerating to change,
  costs quota, and High is not guaranteed under the limit. Rejected by Jacob.
- B. Always generate Large; reduce in the page (chosen by Jacob): one generation, switch freely, High guaranteed.
  Costs a mesh-reduction step in `js/mesh.js` and phone memory/speed with ~900k triangles (unverified).

## Decided
- Server: default extra settings become `{}` (Space default detail); `render.yaml` `HF_EXTRA_JSON` becomes `{}`.
  Jacob must run Manual sync on the Render Blueprint after merge.
- If the model was edited (cut, mirror, delete...) since loading, choosing a level warns that it starts again from the
  model as generated; Undo brings the edits back.
- Model already under a level's target: left as is, and the page says so.
- Slice hint for too many triangles: "Tap Detail: High".

## Claude's calls
- Reduction: quadric-error edge collapse (Garland-Heckbert) with checks that keep the mesh manifold and closed and
  avoid flipped triangles; each piece gets a share of the budget by its triangle count.
- Undo keeps 2 steps above 500,000 triangles (5 above 100,000, 20 below).
- Large STL export of ~900k triangles is about 45 MB.

## Not verified until Jacob tries it
Speed and memory on his iPhone; how long a full-detail generation takes through Render.
