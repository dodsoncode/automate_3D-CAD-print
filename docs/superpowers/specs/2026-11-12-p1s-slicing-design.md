# "Slice for P1S" in the Image3D Render app - design

Date: 2026-11-12. Status: design approved in chat by Jacob (with PLA Silk+ added); this spec awaits his review.
Background and measurements: `docs/2026-11-12-slice-send-feasibility.md`.

## Purpose

From the phone, turn the model in the Image3D editor into a file the Bambu P1S can print (`.gcode.3mf`),
with correct nozzle, filament and plate settings, without a computer. Sending stays manual for now so that
Bambu Handy keeps working (Jacob's choice): the file goes to the printer's microSD by card reader or by an
FTPS app, and the print is started on the printer.

## What Jacob said

- Build the slicing step; stay on the free Render instance.
- Keep Handy (so no Developer Mode, no home relay for now).
- Filament options must include Bambu PLA Basic and Bambu PLA Silk+.

## What the user sees (Render version of the page only)

A "Slice for P1S" section below Export:

| Setting | Choices (default first) |
|---|---|
| Printer / nozzle | Bambu P1S, 0.4 mm (fixed, shown as text) |
| Filament | Bambu PLA Basic, Bambu PLA Silk+, Bambu PLA Matte, Bambu PETG HF |
| Quality | 0.20 mm Standard, 0.16 mm Optimal (finer), 0.28 mm Extra Draft (faster) |
| Plate | Textured PEI Plate, Cool Plate, Smooth PEI Plate / High Temp Plate |
| Supports | Off, Tree (auto) |

Tap **Slice**: progress text ("Slicing... about 3 minutes on the free server; keep this screen open"), then a
result line (print time, filament in grams, layers) and **Download print file** (`model.gcode.3mf`).
If the server has no working slicer the section says "Slicer unavailable on this server" and nothing else
changes. The Claude artifact version never shows the section.

## How it works

- Engine: OrcaSlicer's slicing engine through the npm package `orcaslicer-addon` 0.1.0 (prebuilt Linux
  binary; needs Node >= 18 and, on the host, glibc >= 2.35, libstdc++ with GLIBCXX_3.4.30, libcrypto.so.3,
  libfontconfig.so.1, libexpat and libz; `slicer/install.sh` proves this by slicing a 10 mm cube), with Bambu's stock profiles from the OrcaSlicer repository
  pinned to commit `47a17ad9a33af7871bdbf21935bc2c1a6a5e488f`.
- Profiles used: printer `Bambu Lab P1S 0.4 nozzle`; process `<quality> @BBL X1C` (the P1S uses these);
  filament `<name> @BBL P1S 0.4 nozzle`.
- The page sends the current model as binary STL. The server:
  1. checks passcode, size and triangle count (limit 150,000);
  2. checks the model fits the 256 x 256 x 256 mm bed, then moves it so its footprint is centred at
     (128, 128) with its lowest point at z = 0 - **found in testing: the engine does not centre an STL, and an
     uncentred model produced moves at negative X, off the bed**;
  3. runs the engine as a separate process (one slice at a time, 15-minute limit);
  4. **checks the result before offering it**: printer model is Bambu Lab P1S, nozzle 0.4, the filament,
     quality and plate are the ones asked for, supports match, and every extruding move lies inside the bed.
     A file that fails any check is discarded and the page shows why.
- Slicing is a background job: `POST /api/slice` returns a job id at once; the page polls
  `GET /api/slice/{id}` and downloads from `GET /api/slice/{id}/file`. A dropped connection does not lose the
  result. Finished jobs are kept 30 minutes; only the latest result is kept.
- All three slice routes need the passcode header, with the same wrong-passcode throttle as Generate.

## Protecting what already works

- The slicer is optional. `image3d/slicer/install.sh` runs in Render's build step, installs Node if the
  build image has none, the engine and the profiles, and **always exits successfully**; if anything is
  missing, `GET /api/slice/options` reports `available: false` and Generate / the editor are unaffected.
- No Docker and no change of Render runtime; `render.yaml` only gains the extra build step.

## Limits (stated on the page or in the docs)

- Free instance: 512 MB RAM, 0.1 CPU. Measured engine cost for a 105k-triangle model: about 17 CPU-seconds and
  300-345 MB. Expect about 3 minutes per slice; the 150,000-triangle limit keeps memory in range. Not measured
  on Render.
- Single filament only (no AMS colour mapping), no auto-orientation, no per-object settings.
- The engine package is a small community project. If it fails on Render or proves unreliable, the fallback is
  the official OrcaSlicer / Bambu Studio command line in a Docker service (not built here).

## Verification levels (honest)

- Here: real slices through the real engine, with the output checks above, plus a browser test at phone size
  with a stand-in slicer.
- NOT verified until Jacob does it: the engine installing and running on Render; any print. The first print
  should be something small, watched for the first layers.

## Getting the file to the printer while keeping Handy (documented in `image3d/PRINTING.md`)

- A: card reader -> microSD -> start on the printer.
- B: FTPS app on the phone over home Wi-Fi (implicit TLS, port 990, user `bblp`, password = access code) ->
  start on the printer. Reported to work on the P1 series without LAN-only mode; unverified on Jacob's
  firmware - a 10-minute test (SL3).

## Not in scope

Sending or starting prints from the tool, a home relay, Developer Mode, AMS multi-colour, other printers or
nozzles, editing slicer settings beyond the five above.
