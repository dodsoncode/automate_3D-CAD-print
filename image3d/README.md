# Image3D editor

A phone-friendly page to open a 3D mesh (GLB, OBJ or STL), delete pieces, resize, orient, cut, and export a printable STL. The goal is photo -> 3D model -> clean it up -> STL for the printer, all from a phone.

## Two ways to use it

1. **claude.ai artifact ("Image3D editor").** Published 2026-11-11 from commit 187ed74, private to Jacob (the link is not kept in this repo). Artifact pages cannot reach other sites, so it cannot call Hugging Face, and artifact downloads do not allow `.stl`, so Export saves `model.zip` containing `model.stl`. Workflow: make a model on a Hugging Face Space page in the phone browser (Hunyuan3D-2.1 or TRELLIS), download the GLB, open it in the editor, edit, Export.
2. **Render service** (`../render.yaml` + `DEPLOY.md`). One link: photo -> model -> edit -> plain `model.stl`. The server keeps the Hugging Face token and adds `POST /api/generate`. Not deployed yet.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The editor page (needs `js/`, `vendor/` and `../gui/vendor/`) |
| `image3d.html` | Single-file build of the page (committed); works from any directory and as an artifact |
| `build.py` | `python image3d/build.py` bundles `index.html` into `image3d.html` |
| `js/mesh.js`, `js/stl.js` | Mesh maths (weld, split, scale, rotate, lay flat, cut, closed check) and STL read/write |
| `vendor/earcut.min.js` | Polygon triangulation for cut caps (earcut 2.2.4, ISC; see `vendor/LICENSES.txt`) |
| `js/glb.js`, `js/obj.js`, `js/readany.js` | File readers (GLB, OBJ; `readany.js` picks by extension, STL goes through `stl.js`) |
| `server.py` | FastAPI app for Render: serves the page, `GET /api/health`, `POST /api/generate` via a Hugging Face Space |
| `requirements.txt` | Python dependencies for the server |
| `../render.yaml` | Render Blueprint (free web service, `rootDir: image3d`) |
| `DEPLOY.md` | Phone steps for the Hugging Face token and the Render deploy, plus troubleshooting |
| `tests/` | `test_mesh.py`, `test_readers.py`, `test_page.py`, `test_server.py`, `make_samples.py`, `samples/` |

## Tests

- `python -m pytest -q image3d/tests` (the browser tests at 390 px wide need Playwright + Chromium).
- Everything incl. existing tests: `python -m pytest -q image3d/tests gui/tests && (cd firmware && python -m pytest -q)`.

## Verification status

- Mesh maths and file readers: script-checked (Node under pytest, on generated samples). Not tried on a real Hunyuan3D/TRELLIS GLB.
- Editor page: tested in a desktop browser at phone size (Playwright), NOT on a real phone.
- Server: tested with a FAKE generator and a fake `gradio_client`; the real Hugging Face call was run once from Claude's workspace on 2026-11-11 (default Space) and the resulting model opened and cut cleanly.
- NOT verified: the Render deploy, a real phone, and the artifact's `model.zip` download inside the real Claude app.
- Open for Jacob: TI6 (try the artifact editor on the phone) and TI7 (Hugging Face token + Render deploy, first real generation). See `../TASKS.md`.
