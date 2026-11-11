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

## Constraint added by Jacob (13:48)

He will use this **on a phone, not a computer**. So: no local scripts, no local files to double-click,
touch-sized controls, and everything reachable from a link.

## Assumptions (mine - correct me)

- "Solid model" means a closed (watertight) printable mesh. AI generators do not produce CAD solids
  (STEP / parametric); sizes are approximate until scaled in the editor.
- A phone can save the exported STL and open it in Bambu Handy / send it on to Bambu Studio later.

## Hosting - what was checked

- A claude.ai artifact page can be opened on the phone and can offer file downloads, but its security policy
  **blocks network calls to other sites**, so an artifact cannot call Hugging Face itself.
- Meshy's API needs a paid plan. Hugging Face Spaces are callable for free with a personal token and a small
  daily GPU quota.
- Jacob already deploys an app on Render (mental_stength), so a small Render web service is a known path.

## Approach (chosen): one editor page, two ways to reach it

1. **Editor as a claude.ai artifact - works on the phone today, no setup.** Open a model file (GLB / OBJ / STL),
   edit, export STL. To get the model: run the photo through the Hunyuan3D or TRELLIS Space page in the phone
   browser, download the GLB, open it in the editor. Two steps, both on the phone.
2. **Same page served by a small Render app - one link does everything.** `image3d/server.py` (FastAPI) serves
   the page and adds `POST /api/generate`, which forwards the photo to the Hugging Face Space with
   `gradio_client` and returns the GLB. The Hugging Face token is a Render environment variable, never in the
   page or the repo. A passcode (also an environment variable) guards `/api/generate` so strangers cannot spend
   the quota. Render's free tier sleeps when idle, so the first tap can take about a minute.

The page detects which mode it is in: the Generate button appears only when `/api/generate` answers.

Rejected: browser calling Hugging Face directly with a pasted token (blocked inside artifacts; token would sit
in the phone browser), and a local Python server (needs a computer).

## Components

| Unit | Does | Depends on |
|---|---|---|
| `image3d/js/mesh.js` | Pure mesh maths: weld vertices, split into connected pieces, delete piece, scale / rotate / lay flat, plane cut with capped faces, closed-mesh check, bounding box, volume | nothing (runs in Node for tests) |
| `image3d/js/stl.js` | Binary STL writer and reader | nothing |
| `image3d/js/loaders.js` | GLB and OBJ -> plain triangle arrays | vendored three.js GLTFLoader |
| `image3d/server.py` | FastAPI app: serves the built page; `GET /api/health`; `POST /api/generate` (photo + passcode -> GLB). Generators sit behind one function, `generate(image_bytes) -> glb_bytes`; first is Hugging Face Spaces, with Space name and endpoint read from environment variables | `fastapi`, `uvicorn`, `gradio_client`, `python-multipart` |
| `render.yaml` + `image3d/requirements.txt` | Render blueprint for the service | - |
| `image3d/index.html` | The page, laid out for a phone: photo import, Generate (Render mode only), open model file, 3D view, piece list, edit tools, checks, Export STL | the units above, `gui/vendor/three.min.js` |
| `image3d/build.py` | Inlines everything into `image3d/image3d.html` (single file, same idea as `gui/build_artifact.py`); this file is both the artifact and what the Render app serves | - |

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

photo -> `server.py` -> Hugging Face Space -> GLB bytes (or: GLB file opened by hand) -> `loaders.js` -> triangles -> `mesh.js` weld + split into pieces ->
user edits (each edit = pure function on the piece list) -> `stl.js` -> download.

## Errors

- Wrong passcode / quota used up / Space busy or asleep: plain message with what to do next
  ("try again in a few minutes", "open a model file instead").
- Unreadable model file: message, state unchanged.
- Cut that removes everything: refused with a message.

## Testing and honest verification levels

- `image3d/tests/` (Node, run by pytest like `gui/tests`): split, delete, scale, lay flat, cut-and-cap keeps
  a cube and a two-piece sample closed with the right volume; STL round trip.
- Browser test (Playwright, if available here): page loads without errors, opens a sample STL, deletes a
  piece, exports an STL that `mesh.js` reads back closed.
- `server.py`: tested with a fake generator (passcode refused / accepted, GLB returned).
- **Cannot be verified from Claude's workspace:** phone behaviour (only a phone-sized desktop browser test), the Render deploy, and the live Hugging Face call (needs Jacob's token and network
  access). It will be marked NOT verified until Jacob runs one photo through it.

## Jacob's setup steps (after merge)

Today, no setup: open the artifact link on the phone; make a model on the Hugging Face Space page; open the
GLB in the editor.

For one-link generation (about 15 minutes, can be done from the phone):
1. Create a free Hugging Face account and a read token.
2. In Render: New > Blueprint > this repo; set `HF_TOKEN` and `IMAGE3D_PASSCODE`.
3. Open the Render URL on the phone, enter the passcode once, pick a photo, press Generate.
