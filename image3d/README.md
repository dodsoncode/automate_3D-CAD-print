# Image3D editor

A phone-friendly page to open a 3D mesh (GLB, OBJ or STL), delete pieces, resize, orient, cut, and export a printable STL. The goal is photo -> 3D model -> clean it up -> STL for the printer, all from a phone.

## Two ways to use it

1. **claude.ai artifact ("Image3D editor").** Published 2026-11-11 from commit 187ed74, private to Jacob (the link is not kept in this repo). Artifact pages cannot reach other sites, so it cannot call Hugging Face, and artifact downloads do not allow `.stl`, so Export saves `model.zip` containing `model.stl`. Workflow: make a model on a Hugging Face Space page in the phone browser (Hunyuan3D-2.1 or TRELLIS), download the GLB, open it in the editor, edit, Export.
2. **Render service** (`../render.yaml` + `DEPLOY.md`). One link: photo -> model -> edit -> plain `model.stl`. The server keeps the Hugging Face token and adds `POST /api/generate`. Deployed on Render and confirmed working on Jacob's phone on 2026-11-12. Optionally also "Slice for P1S" (see below): `POST /api/slice` and friends make a `.gcode.3mf` for a Bambu P1S.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The editor page (needs `js/`, `vendor/` and `../gui/vendor/`) |
| `image3d.html` | Single-file build of the page (committed); works from any directory and as an artifact |
| `build.py` | `python image3d/build.py` bundles `index.html` into `image3d.html` |
| `js/mesh.js`, `js/stl.js` | Mesh maths (weld, split, scale, rotate, lay flat, cut, closed check) and STL read/write |
| `vendor/earcut.min.js` | Polygon triangulation for cut caps (earcut 2.2.4, ISC; see `vendor/LICENSES.txt`) |
| `js/glb.js`, `js/obj.js`, `js/readany.js` | File readers (GLB, OBJ; `readany.js` picks by extension, STL goes through `stl.js`) |
| `server.py` | FastAPI app for Render: serves the page, `GET /api/health`, `POST /api/generate` via a Hugging Face Space, and the slice job routes (`GET /api/slice/options`, `POST /api/slice`, `GET /api/slice/{id}`, `GET /api/slice/{id}/file`) |
| `slicing.py`, `slicer/` | Slice for P1S: OrcaSlicer engine wrapper with option tables, model centring and the G-code safety checks; `slicer/install.sh` installs Node, the engine and Bambu's profiles at build time (always exits 0) |
| `PRINTING.md` | Phone steps: slicer settings, getting `model.gcode.3mf` to the P1S while keeping Bambu Handy, first-print checklist, what is not verified |
| `requirements.txt` | Python dependencies for the server |
| `../render.yaml` | Render Blueprint (free web service, `rootDir: image3d`) |
| `DEPLOY.md` | Phone steps for the Hugging Face token and the Render deploy, plus troubleshooting |
| `tests/` | `test_mesh.py`, `test_readers.py`, `test_page.py`, `test_server.py`, `test_slicing.py`, `make_samples.py`, `samples/`; `e2e_slice.py` is a script (not run by pytest) for a real slice through the real server |

## Tests

- `python -m pytest -q image3d/tests` (the browser tests at 390 px wide need Playwright + Chromium).
- Everything incl. existing tests: `python -m pytest -q image3d/tests gui/tests && (cd firmware && python -m pytest -q)`.

## Slice for P1S (Render version only)
A section below Export turns the current model into `model.gcode.3mf` for a Bambu P1S (0.4 mm nozzle): choose filament, quality, plate and supports, tap Slice, download. The page shows "Slicer unavailable" if the server has no working slicer; everything else is unaffected. Model limit 150,000 triangles. Before a file is offered it is checked (printer model, nozzle, your four choices, every extruding move inside the bed). Phone steps for the settings, getting the file to the printer and the first print: [PRINTING.md](PRINTING.md). Deploy step and how to check it installed: [DEPLOY.md](DEPLOY.md). Real-engine run: `python image3d/tests/e2e_slice.py` (add `--direct` for the memory measurement).

## Verification status

- Mesh maths and file readers: script-checked (Node under pytest, on generated samples). Not tried on a real Hunyuan3D/TRELLIS GLB.
- Editor page: tested in a desktop browser at phone size (Playwright), NOT on a real phone.
- Server: tested with a FAKE generator and a fake `gradio_client`; the real Hugging Face call was run once from Claude's workspace on 2026-11-11 (default Space) and the resulting model opened and cut cleanly.
- Render deploy and generation on a phone: Jacob reported on 2026-11-12 that they work well (TI6, TI7). Details of what he tried are not recorded.
- Slice for P1S: the slicer core (`slicing.py`) is script-checked with the real OrcaSlicer engine in Claude's workspace. The server is tested with a fake slicer, plus real end-to-end runs through the real server (`tests/e2e_slice.py`; 124,500-triangle model in 15.6 s with 2 CPU cores here, 368 MB peak for the engine process). The page is tested in a desktop browser at phone size with a fake slicer.
- NOT verified: the slicer on Render, a real phone for the slice section, any print, and the artifact's `model.zip` download inside the real Claude app.
- Open for Jacob: TS4 (redeploy and check the slicer is available), TS5 (first small test print, watched) and TS3 (FTPS upload test). See `../TASKS.md`.
