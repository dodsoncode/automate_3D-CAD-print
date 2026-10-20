// Runs the MakeCode TypeScript (gait.ts + walker.ts) in Node with a tiny fake micro:bit, for the parity tests.
// usage: node harness.js '<json scenario>'   (needs the `typescript` npm package on NODE_PATH)
const ts = require('typescript'), fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..');
function js(f) {
  return ts.transpileModule(fs.readFileSync(path.join(dir, f), 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.None } }).outputText;
}
const log = [], state = { missing: [], shown: [], bg: null, t: 0 };
const mocks = {
  pins: {
    createBuffer: n => ({ data: new Array(n).fill(0), setNumber(fmt, i, v) { this.data[i] = v; } }),
    i2cWriteBuffer: (a, b) => { log.push([a, b.data.slice()]); return state.missing.indexOf(a) >= 0 ? 1 : 0; }
  },
  NumberFormat: { UInt8LE: 1 }, IconNames: { Sad: 'sad' },
  basic: { pause() {}, showIcon(i) { state.shown.push(i); } },
  control: { millis: () => state.t, waitMicros() {}, inBackground(f) { state.bg = f; } }
};
const names = Object.keys(mocks);
const body = js('gait.ts') + '\n' + js('walker.ts') + '\nreturn walker;';
const walker = new Function(...names, body)(...names.map(n => mocks[n]));
const sc = JSON.parse(process.argv[2]);
let out;
if (sc.mode === 'gait') {
  walker._reset();
  walker._configure(...sc.cfg);
  out = [];
  sc.steps.forEach(st => {
    walker._command(st.fwd, st.turn);
    for (let i = 0; i < st.n; i++) {
      walker._update(st.dt);
      out.push([0, 1, 2, 3].map(l => walker._hip(l)).concat([0, 1, 2, 3].map(l => walker._knee(l))));
    }
  });
} else {
  state.missing = sc.missing || [];
  walker.start();
  const ticks = {};
  log.forEach(([a, b]) => { if (b.length === 5) ticks[(b[0] - 6) / 4] = [b[3] | (b[4] << 8), a]; });
  out = { ticks, shown: state.shown, addrs: log.map(l => l[0]).filter((v, i, a) => a.indexOf(v) === i) };
  if (sc.setLeg) {
    log.length = 0; walker.setLeg(...sc.setLeg);
    const b = log[log.length - 1][1]; out.after = [(b[0] - 6) / 4, b[3] | (b[4] << 8)];
  }
}
console.log(JSON.stringify(out));
