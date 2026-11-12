// Slices one STL with the OrcaSlicer engine.  Usage: node slice_job.js <input.stl> <output.gcode.3mf> <settings.json>
// settings.json: {"printer","filament","process","options":{...string values...}} (from slicing.settings_for).
// The engine prints many DEBUG lines; the caller only reads the last line: RESULT {"ok":true,...} or RESULT {"ok":false,"error":"..."}.
// Exit code 0 on success, 1 on failure.
const fs = require("fs");
const path = require("path");

function finish(result) {
  process.stdout.write("\nRESULT " + JSON.stringify(result) + "\n", () => process.exit(result.ok ? 0 : 1));
}

async function main() {
  const [input, output, settingsPath] = process.argv.slice(2);
  if (!input || !output || !settingsPath) throw new Error("usage: node slice_job.js <input.stl> <output.gcode.3mf> <settings.json>");
  const s = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
  const engine = require("orcaslicer-addon");
  engine.initialize({
    resourcesPath: path.join(__dirname, "resources"),
    printerProfiles: [s.printer],
    filamentProfiles: [s.filament],
    processProfiles: [s.process],
  });
  await engine.slice({
    input: input,
    output: output,
    printerProfile: s.printer,
    filamentProfile: s.filament,
    processProfile: s.process,
    options: s.options || {},
  });
  finish({ ok: true, output: output });
}

main().catch((e) => finish({ ok: false, error: String((e && e.message) || e).slice(0, 500) }));
