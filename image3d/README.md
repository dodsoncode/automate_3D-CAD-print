# Image3D editor

A phone-friendly page to open a 3D mesh (GLB, OBJ or STL), delete pieces, resize, orient, cut, and export a printable STL.

- `index.html` - the page (needs `js/` and `../gui/vendor/`); `python image3d/build.py` bundles it into one file, `image3d.html`, which works from any directory and as a claude.ai artifact.
- `js/` - mesh maths and file readers (`mesh.js`, `stl.js`, `glb.js`, `obj.js`, `readany.js`).
- No model yet? Generate one from a photo on a Hugging Face Space (Hunyuan3D-2.1 or TRELLIS), download the GLB, then open it here.
- Tests: `python -m pytest -q image3d/tests` (browser tests at 390 px wide need Playwright + Chromium).
