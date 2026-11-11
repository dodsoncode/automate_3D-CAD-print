# Image to 3D editor (`image3d/`) - design

Date: 2026-11-11. Status: design approved in chat by Jacob; this spec awaits his review.

## Purpose

Turn a **photo of an object** into a printable STL for the Bambu P1S, with light editing in between:
import photo -> generate a 3D model -> delete unwanted pieces, resize, orient, cut -> export STL.
Typical use: decorative shells and add-ons for the walking robot, not servo-fit parts.

## What Jacob said

- Lives in this repo (`automate_3D-CAD-print`).
- Input is mostly photos of objects.
- Generator: free Hugging Face route (open-source Hunyuan3D / TRELLIS Spaces).
- Python is fine, but the tool must **run in a browser** so he can open and edit from his devices.

## Assumptions (mine - correct me)

- "Run in a browser" means the whole tool works as one web page with no server to keep running, so it opens
  on a phone, tablet or computer. Python is kept only as an optional command-line fallback.
- The Hugging Face token is pasted once into the page and stored in that browser only (localStorage).
  It is never written to the repo.
- "Solid model" means a closed (watertight) printable mesh. AI generators do not produce CAD solids
  (STEP / parametric); sizes are approximate until scaled in the editor.

## Approaches considered

1. **Browser-only page calling Hugging Face directly (chosen).** One HTML file; works on any device; no
   install. Risk: a Space can be busy, change its API, or refuse browser calls.
2. Local Python server + page. Token stays in a file, but only works on the computer running it.
3. Hosted backend (Render etc.). Reachable anywhere but adds a service to run and secure. Not needed yet.

To contain the risk in (1), the editor never depends on generation: it also **opens any GLB / OBJ / STL
file**, so a model made on the Hugging Face, Tripo or Meshy web apps (or by the Python fallback) can be
edited and exported the same way.

## Components

| Unit | Does | Depends on |
|---|---|---|
| `image3d/js/mesh.js` | Pure mesh maths: weld vertices, split into connected pieces, delete piece, scale / rotate / lay flat, plane cut with capped faces, closed-mesh check, bounding box, volume | nothing (runs in Node for tests) |
| `image3d/js/stl.js` | Binary STL writer and reader | nothing |
| `image3d/js/loaders.js` | GLB and OBJ -> plain triangle arrays | vendored three.js GLTFLoader |
| `image3d/js/generators.js` | `generate(imageFile, settings) -> GLB bytes`. One entry per generator; first one is Hugging Face Spaces through the Gradio JS client. Space name and endpoint are settings, not hard-coded logic | `@gradio/client` (loaded only when Generate is pressed) |
| `image3d/index.html` | The page: photo import, Generate, 3D view, piece list, edit tools, checks, Export STL | the units above, `gui/vendor/three.min.js` |
| `image3d/generate.py` | Optional fallback: `python image3d/generate.py photo.jpg out.glb` using `gradio_client`; token from `HF_TOKEN` env var | `pip install gradio_client` |
| `image3d/build.py` | Inlines everything into `image3d/image3d.html` (single file, same idea as `gui/build_artifact.py`) | - |

## Editing features (version 1)

- Tap a piece in the view or the list to select it; **Delete piece**; "Keep only the biggest piece".
- **Size:** set the longest side in mm (uniform scale); shows X/Y/Z size.
- **Orient:** rotate 90 degrees about X/Y/Z; **Lay flat** (drop to the bed, Z = 0).
- **Cut:** axis-aligned plane with a slider; keep the side above or below; the cut is capped so the part stays closed.
- **Undo** (one stack, last 20 steps).
- **Checks (traffic lights, like Walker Designer):** closed mesh, fits the 256 x 256 x 256 mm bed, piece count.
- **Export STL** (binary, mm). Warns but still exports if the mesh is not closed (Bambu Studio can repair).

Not in version 1: sculpting, holes / booleans, merging parts, colors or multi-material 3MF, sending to the printer.

## Data flow

photo -> `generators.js` -> GLB bytes -> `loaders.js` -> triangles -> `mesh.js` weld + split into pieces ->
user edits (each edit = pure function on the piece list) -> `stl.js` -> download.

## Errors

- No token / bad token / quota used up / Space busy: plain message with what to do next
  ("try again in a few minutes", "open a model file instead").
- Unreadable model file: message, state unchanged.
- Cut that removes everything: refused with a message.

## Testing and honest verification levels

- `image3d/tests/` (Node, run by pytest like `gui/tests`): split, delete, scale, lay flat, cut-and-cap keeps
  a cube and a two-piece sample closed with the right volume; STL round trip.
- Browser test (Playwright, if available here): page loads without errors, opens a sample STL, deletes a
  piece, exports an STL that `mesh.js` reads back closed.
- **Cannot be verified from Claude's workspace:** the live Hugging Face call (needs Jacob's token and network
  access). It will be marked NOT verified until Jacob runs one photo through it.

## Jacob's setup steps (after merge)

1. Create a free Hugging Face account and a read token.
2. Open `image3d/image3d.html`, paste the token in Settings, pick a photo, press Generate.
