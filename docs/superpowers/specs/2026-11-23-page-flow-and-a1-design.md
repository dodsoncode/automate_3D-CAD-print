# Image3D: top-to-bottom page flow, then Bambu A1 support - design

Date: 2026-11-23. Status: design approved in chat by Jacob 2026-11-23 (short design for a small change).

## Intent and why
Jacob's first real run worked end to end (generate, STL, slice, send by a-Shell). The page does not show the order of
the work: he scrolls to the bottom to load a picture, back up to edit, and down again to slice and export. He also
wants the app to serve his Bambu A1 printers, not only the P1S.

## Goals
- PR 1 (first, about 3-4 h): one clear top-to-bottom flow with numbered steps.
- PR 2 (after Jacob has seen PR 1 on his phone, about 5-7 h): a Printer dropdown (P1S, A1, A1 mini).

## Non-goals / anti-goals
- No framework, no wizard that hides later steps (it adds taps and hides the order).
- No removed feature: every existing button and element ID stays, so current behaviour and tests keep working.
- No change to slicing or send behaviour in PR 1.

## Approaches
- Reshape the existing page in place (chosen): smallest change, keeps every working feature.
- Wizard with one step per screen: rejected, more taps and the order is hidden.
- For PR 2: one per-printer config table in `slicing.py` (profile names, bed size, excluded corner, result checks)
  (chosen), versus copy-pasting the P1S code path per printer (rejected).

## PR 1 design (decided with Jacob)
- One passcode box at the very top (`#gen-pass` id kept). Messages say "Enter the passcode at the top".
- Step 1 Get a model: photo picker + Generate; below it an **Upload GLB file** button that opens the file picker
  (still accepts GLB, OBJ, STL).
- Step 2 Edit: Pieces, Size, Orient, Cut or mirror, Checks.
- Step 3 Slice: slice settings, plus a small Export STL button.
- Step 4 Send: download, a-Shell command, Shortcut; visible from the start, greyed until a slice exists.
- No model loaded: steps 2-4 greyed with "Load a model first."
- Artifact copy (no server): no Generate, no Slice; shows Upload GLB file and the edit tools.
- Claude's calls (not Jacob's): drop the Hugging Face how-to links (he only uses Generate); passcode leaves the
  Generate panel.

## PR 2 design (to confirm after PR 1)
Bambu's pinned profiles already hold A1 and A1 mini 0.4 mm machine, `... @BBL A1` / `@BBL A1M` filament and process
profiles. The A1 bed is 256 mm with no excluded corner; the A1 mini bed is smaller. The page and send box name the
chosen printer. Uploads use the same FTPS port 990. Not verified on a real A1 until Jacob prints one.

## Left to the builder
Exact wording, spacing and greyed styling; test layout.
