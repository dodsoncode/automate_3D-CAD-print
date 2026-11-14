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

**B. Upload over home Wi-Fi from the phone (worked on Jacob's P1S on 2026-11-13, LAN-only and Developer Mode off)**
The printer accepts file uploads by FTPS (FTP with implicit TLS) on port 990, user `bblp`, password = the access code on the printer's WLAN screen. What worked on the iPhone is the free app **a-Shell** and one `curl` command:
1. Phone on the same Wi-Fi as the printer. A microSD card must be in the printer.
2. On the page, tap Download print file and save `model.gcode.3mf` (for example to Downloads).
3. Open a-Shell. Type `pickFolder`, choose the folder that holds the file, tap Open. `ls` should list `model.gcode.3mf`.
4. Type on one line, with the printer's IP address and access code filled in:
   `curl --insecure --ftp-pasv -T model.gcode.3mf ftps://PRINTER-IP:990/ --user bblp:ACCESS-CODE`
   A progress line that reaches 100 % and no `curl:` error means it is on the printer. (372 KB took about 7 seconds.)
5. Start the file from the printer's screen (folder icon).

To test the connection without uploading: `curl -v --insecure --ftp-pasv ftps://PRINTER-IP:990/ --user bblp:ACCESS-CODE` lists the card's folders.

Notes:
- The app "FTP Client - Files location" did NOT work with the printer (error "no-features" on Test Server and Browse, with LAN-only on and off). Other FTP apps are untried.
- Keep the access code private; do not put it in screenshots. It can be regenerated on the printer's WLAN screen.
- Large uploads were reported unreliable on some firmware by other users; not seen here (one small file tried). If an upload fails, use the card.

## Before you start the file: filament
The file's start sequence loads filament from **AMS slot 1** only when the printer runs it with the AMS in use. On 2026-11-13 the first try printed dry (nothing loaded). The reliable way: load the filament from the printer's screen first (until plastic comes out of the nozzle), then start the file. How the start screen's AMS option behaves for this file is still not pinned down.

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
- No print from this tool's output has finished cleanly yet. First attempt (2026-11-13): the centre part printed well on its brim; two small parts came loose (bed adhesion: wash the plate, print one piece at a time, give small parts a bigger footprint).
- The actual temperature values (bed and nozzle) and the Z height are whatever Bambu's stock profiles set; they are not checked. Only "the bed temperature is above zero and the bed is told to heat" is checked.
- How the printer handles the AMS slot for this file.
