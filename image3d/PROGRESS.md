# Image3D - step-by-step progress

Everything done on the photo -> 3D -> STL tool, in order, with what was checked and what was not.
The repo-wide log is [`../PROGRESS.md`](../PROGRESS.md); tasks are TI1-TI7 in [`../TASKS.md`](../TASKS.md).
Times are US Central on 2026-11-11. Steps 1-13 were built on branch `image3d-tool` (merged as PR #7); step 15 is on branch `image3d-real-mesh-fixes`.

## Where it stands

- **Built and tested here:** mesh editing maths, file readers, the phone editor page, the Render service.
- **Slice for P1S, final fix wave (2026-11-12):** PETG HF + Cool Plate refused; G-code checks for bed heat, exact filament and the excluded bed corner; plain overhang and out-of-memory messages; engine run with a memory/time watchdog; leaner STL handling; install step that proves the engine with a test slice; page fixes (stale results, resume, passcode, poll timeout, floating-piece warning, incompatible plates, size in the result line). Verified with the real engine in Claude's workspace and with a fake slicer in a desktop browser. NOT verified: Render, a real phone, any print.
- **Published:** the editor as a private claude.ai artifact named "Image3D editor".
- **Live on Render (2026-11-13, confirmed by Jacob):** the slicer (after a manual Blueprint sync), a real slice and download on the phone, upload to the printer over Wi-Fi with a-Shell + curl (LAN-only and Developer Mode off), file started on the printer. No clean print yet (first attempt: two small parts came loose).
- **Mirror (2026-11-13, branch `mirror`):** Mirror button in the Cut panel; script-checked and desktop-tested; not tried on a phone or a real generated model.
- **Send to printer (2026-11-14, branch `send-helpers`):** copy a one-line a-Shell command, or tap "Send with Shortcut"; desktop-tested and checked with a real curl; not tried on the phone.
- **Waiting on Jacob:** SL9 (try the send box and the Shortcut), SL5 (a clean first print: wash the plate, load filament first), SL7 (try Mirror on the phone).
- **Verified live (2026-11-11):** the Hugging Face generation call, from Claude's workspace.
- **Not verified by anyone yet:** a real phone, the Render deploy, and the zip download inside the real
  Claude app.

## What Jacob asked for

A tool in this repo that imports an image, uses a hosted API to generate a solid model from it, lets him
modify the model and delete parts, and exports an STL. Added during the day: it must work **on a phone**, the
generator should be the **free Hugging Face** route, the images are **photos of objects**, and hosting can be a
second **free Render** service next to the mental fitness app.

## Steps

### Step 1 - Check for a ready-made connector (12:03)
- Searched the Claude connector directory for an image-to-3D tool. None exists.
- Captured the idea as parked. Jacob then said to work on it today.

### Step 2 - Find the repo and read it (13:42)
- The robot repo is `dodsoncode/automate_3D-CAD-print`. Read `CLAUDE.md`, `PLAN.md`, `TASKS.md`, `PROGRESS.md`
  and the existing Walker Designer (`gui/`), whose patterns this tool follows.

### Step 3 - Research the hosting options (13:42-13:47, web-checked only)
- Meshy: free plan has no API access (API starts at the paid Pro plan).
- Tripo: paid per model after trial credits.
- Hugging Face Spaces (Hunyuan3D, TRELLIS): callable for free with a personal token and a small daily GPU quota.
- All of these produce **meshes**, not CAD solids. "Solid" here means a closed, printable mesh.
- Jacob's choices: photos of objects; Hugging Face.

### Step 4 - Design spec (13:48, commits `8fc8c42`, `196f527`)
- `docs/superpowers/specs/2026-11-11-image3d-design.md`.
- Revised once when Jacob said phone-only. Checked the claude.ai artifact rules: an artifact can host the
  editor and offer downloads but **cannot call other sites**. Result: one editor page delivered two ways -
  (1) a claude.ai artifact, (2) the same page served by a small Render app that adds generation.
- Jacob approved the design, then the written spec (TI1, TI2).

### Step 5 - Confirm Render (13:51-13:52, web-checked only)
- A second service on the same Render account is fine. Free services share 750 instance hours a month per
  workspace and use none while asleep. Jacob confirmed the mental fitness app is on the free instance.

### Step 6 - Implementation plan (13:54, commits `865462a`, `2f711ec`)
- `docs/superpowers/plans/2026-11-11-image3d.md`: five tasks. Jacob chose the build method: a separate builder
  for each task and an independent reviewer after each one.

### Step 7 - Task 1: mesh maths and STL (14:43-14:47, commits `10c85e3`, `4d82f23`) - TI3
- `js/mesh.js`: weld, split into pieces, delete piece, keep largest, drop small bits, scale, rotate, lay flat,
  cut with a capped face, closed-mesh check, bounding box, volume. `js/stl.js`: STL writer and reader.
- Review found two problems, both fixed and re-reviewed:
  cutting a very fine cross-section could leave the part open; typed-array input crashed.
- Verification: script-checked (Node tests under pytest).

### Step 8 - Task 2: file readers (14:49, commit `bb6196e`)
- `js/glb.js`, `js/obj.js`, `js/readany.js`; sample files in `tests/samples/` made by `tests/make_samples.py`.
- GLB reader converts Y-up to Z-up and refuses compressed files with a clear message.
- Review: approved; small hardening notes kept for the final review.
- Verification: script-checked on generated samples, not on a real generated model.

### Step 9 - Task 3: phone editor page (14:55-14:59, commits `dc50c76`, `c7f0f0f`) - TI4
- `index.html` (source), `build.py`, `image3d.html` (single-file build).
- Open GLB / OBJ / STL, piece list, tap to select, delete, keep largest, remove tiny bits, size in mm, rotate,
  lay flat, cut with preview, undo, checks (closed, fits 256 mm bed), export.
- Found while checking the artifact rules: artifact downloads do not allow `.stl`. Fix: inside the artifact,
  Export saves `model.zip` containing `model.stl`; anywhere else it saves a plain `model.stl`.
- Also fixed after looking at a screenshot: cut plane shows only while cutting; size box shows the current
  size; the 3D view stays in place while the tools scroll.
- Verification: desktop browser at phone size (Playwright, 390 x 844, touch). NOT on a real phone. The zip
  path was tested with a stand-in for the Claude download service, not the real one.

### Step 10 - Task 4: Render service (15:03-15:08, commits `5cfe766`, `1153d60`, `187ed74`) - TI5
- `server.py` (FastAPI): serves the page; `GET /api/health`; `POST /api/generate` (photo + passcode -> GLB)
  through a Hugging Face Space. `requirements.txt`, `../render.yaml`, `DEPLOY.md` (phone-friendly steps).
- Default Space: `tencent/Hunyuan3D-2`, endpoint `/shape_generation` (shape only, no texture - suits printing
  and uses less GPU time). Changeable with `HF_SPACE`, `HF_API_NAME`, `HF_IMAGE_PARAM`.
- The page shrinks the photo to 1024 px before upload.
- Review rounds fixed: size limit and passcode are now checked before any upload is read; the image is passed
  to the Space the way its interface expects; `/docs` is off; error text is capped; wrong passcodes are
  throttled (5 per address, 30 overall, per 10 minutes).
- Verification: desktop-tested with a FAKE generator. The live Hugging Face call and the Render deploy are
  NOT verified. The throttle assumes Render adds the caller's address last in `X-Forwarded-For`; not checked
  on Render.

### Step 11 - Publish the editor as an artifact (15:20-15:34)
- Published `image3d.html` as the private claude.ai artifact "Image3D editor", built from commit `187ed74`,
  with the download permission declared. Its link is in the Claude chat, not in this repo.
- Not verified: opening it and exporting inside the real Claude app.

### Step 12 - Task 5 docs, full test run, whole-branch review (final fix wave)
- Task 5 docs done and the full test run passed: 101 passed (image3d + gui), 39 passed (firmware).
- Whole-branch review: no critical findings. One important finding, fixed in this wave: a phone that locks its
  screen can drop the generate request, so the page now keeps the screen awake while generating (screen wake
  lock, released afterwards, re-requested if the page becomes visible again) and any network `TypeError` from
  `fetch` shows the friendly "server may be waking up" message.
- Also fixed: `requirements.txt` pinned to the installed major versions; a timed-out Space job is cancelled
  before the 503; the 3D view picks 32-bit indices by vertex count (over 65535) instead of triangle count;
  the Size section shows the whole model's X x Y x Z in mm; undo keeps 20 steps up to 100,000 triangles and 5
  above that; `DEPLOY.md` names the repo as Render shows it (`dodsoncode/automate_3d-cad-print`).
- Verification: desktop browser at phone size with a STUBBED wake lock, fake generator and fake
  `gradio_client`; NOT on a real phone, not against the live Space or Render. The 32-bit index choice is covered
  by reading only (no browser test).

### Step 13 - PR (15:55)
- Full run before pushing: `image3d/tests` + `gui/tests` 106 passed; `firmware` 39 passed.
- The artifact was republished with the final page (wake lock, model size line, undo limit).
- PR #7 opened against `main`: "Image3D: photo -> 3D model -> edit -> STL".

### Step 14 - Merge (16:42)
- Jacob asked for the merge; PR #7 merged to `main` (2bc9d21). The Render Blueprint can now use branch `main`.

### Step 15 - First live generation and two fixes (16:50-18:00)
- Jacob supplied a Hugging Face token. One real run of the generation call against the default Space worked
  (valid model in about 10 seconds). This was run from Claude's workspace, not through Render.
- Problem 1: the model had about 917,000 triangles. Fix: the server now asks the Space for a lighter model
  (`HF_EXTRA_JSON`, default `{"octree_resolution": 128}`, about 115,000 triangles; measured live).
- Problem 2: cutting the real model left it open. Cause: the hand-written cap triangulation failed on the real
  cross-section (an outline with a cavity inside). Fix: caps now use the earcut library (vendored), and the
  failing cross-section is kept as a test fixture.
- A review of that fix then found three more ways a cap could come out open (points on exactly straight runs,
  holes on a grid, cross-sections that pinch to a point). Fixed by nudging the coordinates given to earcut by
  about one part in a billion and by testing loop nesting at a point no other loop shares. A fuzz test
  (`tests/fuzz_cut.js`) now covers these: 9,000 random cuts, 0 failures.
- Checked on real models: 168 cuts along all three axes on two models made from one test picture, all closed.
  The page opened and cut a real model at phone size. Not yet checked: Render, a real phone, other pictures.

### Step 16 - Merge (20:56)
- Jacob asked for the merge; PR #9 merged to `main` (c91f2fa). `main` now has the cut fix and the lighter-model
  setting, so a Render Blueprint from `main` gets both.

### Step 17 - Render deploy and phone confirmed (2026-11-12)
- Jacob deployed the Render service and reported it "works well" on his phone (TI6, TI7). This is the first real-device confirmation for the editor and for generation through Render. Details of what he tried are not recorded.

### Step 18 - Slice for P1S: feasibility spike (2026-11-12)
- The OrcaSlicer engine (npm `orcaslicer-addon`, stock Bambu profiles) sliced a 105k-triangle test model for P1S 0.4 nozzle / PLA Basic / textured PEI into a valid `.gcode.3mf` in about 17 CPU-seconds and about 300 MB. Sending from a cloud server to the printer is not possible; third-party start-print needs LAN-only + Developer Mode, which loses Handy. Write-up: `../docs/2026-11-12-slice-send-feasibility.md`. Script-checked in Claude's workspace only; nothing printed.

### Step 19 - Slice for P1S: design, spec and plan (2026-11-12)
- Jacob chose to build "Slice for P1S" on the free Render instance and keep Handy, with PLA Basic and PLA Silk+ among the filaments. Spec `../docs/superpowers/specs/2026-11-12-p1s-slicing-design.md`, plan `../docs/superpowers/plans/2026-11-12-p1s-slicing.md` (4 tasks). Spike findings: the engine does not centre an STL (the server moves the model to the middle of the bed) and engine options must be strings.

### Step 20 - Slice for P1S Tasks 1-3 (2026-11-12)
- Task 1, slicer core (`slicing.py`, `slicer/`): three review rounds hardened the model check and the fail-closed G-code check; `test_slicing.py` 112 passed, real-engine slices run. Script-checked.
- Task 2, server job API (`/api/slice` routes, passcode guard, one slice at a time, 30-minute keep): tested with a fake slicer, 63 server tests passed. Review found no important issues.
- Task 3, "Slice for P1S" panel on the page: desktop browser at phone size with a fake slicer, 242 `image3d` tests passed. Review found no important issues.
- Minor items left for the final review are listed in the root `../PROGRESS.md`.

### Step 21 - Slice for P1S Task 4: deploy wiring, docs, real run (2026-11-12)
- `render.yaml` build command now also runs `bash slicer/install.sh` (it always exits 0, so a slicer install failure cannot fail the deploy). Docs: `PRINTING.md` (new), `DEPLOY.md` (Updating to get the slicer), this README.
- Real end-to-end run through the real server with the real engine (`tests/e2e_slice.py`, Claude's workspace, 2 CPU cores): `two_cubes.stl` 2.0 s; a 124,500-triangle bumpy sphere 15.6 s, 3.1 MB file; the same model through `slicing.run_slice` alone 14.0 s, peak 368 MB (engine) + 98 MB (Python). Both results passed the G-code check.
- NOT verified: the slicer on Render (the free instance has 0.1 CPU and 512 MB, so expect about 3 minutes by estimate and watch memory), a real phone for the slice section, any print.

### Step 22 - Live on Render, phone upload, first print attempt (2026-11-13, Jacob)
- PR #11 merged. The first redeploy ran the old build command; a manual Blueprint sync fixed it and the slicer installed (Slice panel visible).
- A real slice on the free instance produced a 372 KB `model.gcode.3mf`, downloaded on the phone.
- Upload to the printer from the phone: works with a-Shell + `curl` on port 990 with LAN-only and Developer Mode off; the app "FTP Client - Files location" fails with "no-features".
- First print: dry at first (no filament loaded), then the centre part printed well and two small parts came loose (adhesion).

### Step 23 - Mirror (2026-11-13)
- `mesh.mirror` (kept side + its reflection, joined on the plane, no inner wall) and a Mirror button in the "Cut or mirror" section. 7 maths tests and 3 page tests written first. Details in the root `PROGRESS.md`.

### Step 24 - Send to printer from the phone (2026-11-14)
- Slice result gains "Send to printer from this phone": printer IP, access code and name kept on the phone only; "Copy a-Shell command" (one curl call: fetch from the site, then FTPS upload), "Send with Shortcut" (passes only name:job to the "Send to P1S" Shortcut), "Copy Shortcut setup text". 10 page tests written first, one of them runs the command with a real curl. Details in the root `PROGRESS.md`.

## What Jacob does next

1. **SL9 - try the send box:** after the next merge and redeploy, slice, open "Send to printer from this phone", fill it in, tap Copy a-Shell command, paste into a-Shell. Then set up the Shortcut ([`PRINTING.md`](PRINTING.md)) and try Send with Shortcut.
1. **SL5 - a clean first print:** wash the plate, load filament from the printer's screen first, print one small piece, watch it ([`PRINTING.md`](PRINTING.md)).
2. **SL7 - try Mirror on the phone** with a generated model, after the Mirror PR is merged and Render has redeployed.

## How to run the tests

```
python -m pytest -q image3d/tests      # needs Node; browser tests need Playwright; server tests need fastapi + httpx
python image3d/build.py                # rebuild image3d.html after editing index.html or js/
```
