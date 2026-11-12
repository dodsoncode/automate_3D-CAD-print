# Feasibility: slice for the P1S and send to the printer from a phone

Date: 2026-11-12. A spike: the output is this answer. The test scripts lived in a scratch folder and are not in the repo.

## Question

Can the Image3D tool (phone, Render) slice an edited model for the Bambu P1S with correct nozzle / filament
settings, and get the job to the printer?

## Part 1 - Slicing: feasible (measured)

Tried here: the OrcaSlicer engine through the `orcaslicer-addon` npm package (prebuilt Linux binary, no GUI),
with the stock Bambu profiles from the OrcaSlicer repository (`resources/profiles/BBL`).

- Input: a 104,888-triangle, 74 x 74 x 70 mm test model exported by the editor's own STL writer.
- Profiles: printer `Bambu Lab P1S 0.4 nozzle`, filament `Bambu PLA Basic @BBL P1S 0.4 nozzle`,
  process `0.20mm Standard @BBL X1C`, plate `Textured PEI Plate`.
- Result: a valid `.gcode.3mf` (plate G-code, thumbnails, settings) - 348 layers, 1 h 3 min estimate,
  39 cm3 of filament, bed 55 C, first-layer nozzle 220 C, `printer_model = Bambu Lab P1S`.
- Cost: about 17 CPU-seconds and about 300 MB peak memory (single core, only the needed profiles loaded).
  Engine binary 68 MB, Bambu profiles 12 MB.

What that means on Render:
- Free instance (512 MB RAM, 0.1 CPU): memory fits but is tight next to the web server; a slice would take
  roughly 3 minutes (17 CPU-seconds at a tenth of a core - an estimate, not measured on Render).
- Starter instance ($7/month, 0.5 CPU): roughly 35 seconds.
- The service needs Node as well as Python, so it would move to a Docker-based Render service.

Not verified / risks:
- The G-code has **not been printed**. It comes from stock P1S profiles, but nothing here proves a good print.
- The default plate in the profiles is `Cool Plate`; the P1S ships with a textured PEI plate, so the plate
  must be set explicitly (done in the test) and shown to the user.
- `orcaslicer-addon` is version 0.1.0, a small community project (AGPL-3.0) around OrcaSlicer 2.3.1-beta.
  If it proves unreliable, the fallback is the official OrcaSlicer or Bambu Studio command line in Docker
  (documented `--slice`, `--load-settings`, `--export-3mf`), which is heavier and was not tried here.
- AMS / multi-colour, supports and auto-orientation were not tried.

## Part 2 - Sending to the printer: possible, but not from the cloud alone

Facts (web-checked 2026-11-12, not tested on Jacob's printer):
- Bambu Handy is not a slicer and (per forum answers) cannot open a local STL / 3MF; one recent source says
  whether it can send a sliced `.gcode.3mf` from phone storage depends on the app version.
- Since the January 2025 authorization firmware, third-party software can start a print only with the printer
  in LAN-only + Developer Mode. Developer Mode cannot connect to Bambu Cloud, so Handy and remote access stop.
- The printer has an FTPS server (port 990, user `bblp`, password = access code) for its SD card; forum
  reports say it works on the P1 series without LAN-only mode, with mixed reports on large uploads.
- Starting a print uses MQTT on the local network. A Render server cannot reach a printer at home, and a
  phone browser cannot speak FTPS or MQTT.

Options:

| | Route | Extra hardware | Keeps Handy / cloud | Effort | Status |
|---|---|---|---|---|---|
| A | Slice on Render, download `.gcode.3mf` to the phone, copy to the printer's microSD (card reader), start on the printer | card reader | yes | none beyond slicing | always works |
| B | As A, but upload to the SD card over Wi-Fi with an FTPS app on the phone, start on the printer | none | yes (if FTPS works in cloud mode on his firmware) | none beyond slicing | needs a 10-minute test at home |
| C | Small always-on computer at home (Pi or any PC) polls the Render app, uploads by FTPS and starts the print by MQTT (`printer/bambu_send.py`) | yes | **no** - needs LAN-only + Developer Mode | about 4-6 h + setup | `bambu_send.py` has never run on the real printer |
| D | Upload the model privately to MakerWorld, print from Handy with Bambu's cloud slicing | none | yes | none | manual, outside this tool |

## Recommendation

1. Build slicing into the Render app first ("Slice for P1S" -> `.gcode.3mf` download). It is the measured,
   valuable part and every sending route needs it.
2. Before building any sender, Jacob tries route B once (FTPS app + start on the printer). If it works, a relay
   may not be worth giving up Handy for.
3. Build the home relay (C) only if he wants one-tap printing and accepts losing Handy / cloud.

## Sources

- Bambu Studio command line: https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- OrcaSlicer CLI mode: https://www.orcaslicer.com/wiki/cli/cli_mode
- Handy and local files: https://forum.bambulab.com/t/open-stl-or-3mf-files-directly-in-the-app/92605
- Developer Mode / authorization: https://3dprinteray.com/bambu-lan-only-mode , https://bambuhub.net/articles/bambu-connect-explained
- FTPS details: https://contentnation.net/en/grumpydevelop/bl-knowledge , https://forum.bambulab.com/t/we-can-now-connect-to-ftp-on-the-p1-and-a1-series/6464
- Render instance types: https://render.com/docs/compute-plans.md
