# Printing from the Slice for P1S file

The page makes `model.gcode.3mf` for the Bambu P1S with a 0.4 mm nozzle. This is how to choose the settings and get the file onto the printer from your phone.

## The settings
The first choice in each list is the default.
- **Filament:** PLA Basic (default), PLA Silk+, PLA Matte, PETG HF. Pick the one that is really on the printer.
- **Quality:** 0.20 mm Standard (default), 0.16 mm Optimal (finer, slower), 0.28 mm Extra Draft (faster, rougher).
- **Plate:** Textured PEI (default), Cool Plate, Smooth PEI (High Temp). Pick the plate that is physically on the printer.
- **Supports:** Off (default) or Tree (auto), which adds tree supports where the model needs them.

## Steps
1. In the editor, get the model the way you want it, then open Slice for P1S and choose the four settings.
2. Type the passcode in the Generate box at the top of the page first (the Slice section has no passcode field; with the box empty the page says "Enter the passcode in the Generate section first"). Then tap Slice and keep the screen open. When it is done, tap Download print file. You get `model.gcode.3mf`.
3. Get the file onto the printer with route A or B below.
4. On the printer's screen open the file (Files / SD card) and start it.

## Getting the file to the printer
The printer stays in normal cloud mode. Nothing here needs LAN-only mode or Developer Mode, so Bambu Handy keeps working for watching the print.

**A. MicroSD card (the sure way)**
1. Put the printer's microSD card in a card reader that fits your phone.
2. Copy `model.gcode.3mf` onto the card.
3. Put the card back in the printer and start the file from the printer's screen.

**B. FTPS app over home Wi-Fi (not verified on your printer)**
1. Phone on the same Wi-Fi as the printer.
2. In an FTPS-capable file-transfer app, make a connection with type "FTP with implicit TLS/SSL" (not SFTP).
3. Host: the printer's IP address (on the printer's network settings screen). Port: 990. User: `bblp`. Password: the access code shown on the same network settings screen.
4. Upload `model.gcode.3mf` to the root folder.
5. Start the file from the printer's screen (Files / SD card).

Other users report that route B works on the P1 series without LAN-only mode, but it is NOT verified on your printer or firmware. Large uploads were reported unreliable on some firmware. If it fails, use the card.

## First-print checklist
1. Make the first print a small model.
2. The plate on the printer is the plate you chose on the page.
3. The filament loaded is the filament you chose. The file is single-filament; with an AMS, pick the slot on the printer when you start the print (how the printer treats the AMS slot for this file has not been verified on the printer).
4. Watch the first layers.
5. Stop the print if anything looks wrong.

## If slicing fails
- **"Still working... (connection hiccup)" for a while, then "The slice expired or was lost. Slice again.":** the server may have run out of memory (the free Render instance has 512 MB, and a big, tall model with fine quality and supports can need most of it; not measured on Render). Try a smaller or shorter model, 0.28 mm Extra Draft quality, or supports off if the model does not need them. If it keeps happening, the slicer needs a bigger Render instance.
- **"This model has overhanging parts that would print in mid-air. Turn on Tree supports, cut a flat base, or delete loose pieces, then slice again.":** supports were off and the engine found parts with nothing under them (it calls them "floating regions"). Do what the message says. The page also warns "N piece(s) float above the bed" while supports are off.
- **"The slicer could not support this model's overhanging parts. Cut a flat base or delete loose pieces, then slice again.":** the same problem with Tree supports already on. Cut a flat base in the editor or delete loose pieces.
- **"This model is too large to slice on this server (out of memory). Try a smaller or shorter model, 0.28 mm Extra Draft, or supports off.":** the server stopped the slicer before it ran out of memory. Do what the message says; if it keeps happening, the slicer needs a bigger Render instance.
- **"Bambu PETG HF cannot be printed on the Cool Plate - choose another plate":** PETG HF cannot be used with the Cool Plate (Bambu's profile has no bed temperature for that plate). The page disables that plate when PETG HF is chosen; pick Textured PEI or Smooth PEI.
- **The model is wider than about 240 mm:** the file may be refused after slicing, because the brim the slicer adds would leave the 256 mm bed (or enter the corner of the bed the P1S does not print in). Make the footprint smaller.

## What is checked, and what is not
Before the file is offered, the server checks it automatically:
- the printer model is the P1S and the nozzle is 0.4;
- the filament, quality, plate and supports in the file match your choices;
- every extruding move stays inside the 256 mm bed and out of the front-left corner the P1S does not print in (the printer's own start-up purge line is the one exception);
- the bed temperature for the chosen plate is above zero in the settings stored in the file, and a bed-heat command comes before printing starts.

If a check fails, no file is offered and the page says why.

NOT verified:
- No print has been made from this tool's output.
- The slicer has not yet run on Render.
- The actual temperature values (bed and nozzle) and the Z height are whatever Bambu's stock profiles set; they are not checked. Only "the bed temperature is above zero and the bed is told to heat" is checked.
- How the printer handles the AMS slot for this file.
