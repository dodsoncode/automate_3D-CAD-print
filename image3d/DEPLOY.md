# Deploy Image3D on Render (from a phone)

Status: the Hugging Face call was run for real on 2026-11-11 from Claude's workspace (default Space, a test picture, about 10 seconds, model opened and cut cleanly in the editor). The Render deploy itself and a real phone are NOT verified yet; that is TI7.

## A. Hugging Face account and token
1. Open huggingface.co in your phone browser and tap Sign Up. Create a free account and confirm your email.
2. Open huggingface.co/settings/tokens and tap Create new token.
3. Choose the type Read, name it `image3d`, and create it.
4. Copy the token (it starts with `hf_`). Keep it somewhere private; you will paste it into Render once. Never put it in the repo or the page.

## B. Render
1. Open dashboard.render.com and sign in (the same account as mental_stength is fine).
2. Tap New, then Blueprint.
3. Connect GitHub if asked, then pick the repo `dodsoncode/automate_3d-cad-print`.
4. Choose the branch `main` (the Blueprint file `render.yaml` is at the repo root). Tap Continue.
5. Render asks for two secret values. Set `HF_TOKEN` to the token from part A, and `IMAGE3D_PASSCODE` to a long passcode you invent, for example four random words. It is the only lock on your Hugging Face quota, so do not use a short or guessable one (you will type it on the page).
6. Tap Apply / Deploy and wait for the deploy to say Live.

## C. Use it
1. Open the service URL shown at the top of the Render page (`https://image3d-....onrender.com`).
2. The Generate from a photo box shows up when the server is awake. Choose a photo, type the passcode (the page remembers it on this phone), tap Generate.
3. Wait a minute or two. The model opens in the editor; then delete pieces, resize, cut and export the STL as usual.

## Updating to get the slicer
The "Slice for P1S" section comes with a new build step (`bash slicer/install.sh`, added to the build command in `render.yaml`). To get it after the PR is merged:
1. The build command lives in `render.yaml`, and Render only applies it when the **Blueprint syncs**. On 2026-11-13 the service redeployed with the OLD build command (the build log said `Running build command 'pip install -r requirements.txt'`, with no `SLICER INSTALL` line) until the Blueprint was synced by hand. If that happens: in the Render dashboard open **Blueprints**, open `image3d`, tap **Manual sync**. The sync lists "Update web service image3d build command to `pip install -r requirements.txt && bash slicer/install.sh`" and starts a deploy. If no deploy starts, open the service and tap Manual Deploy, then Deploy latest commit.
2. When the deploy is Live, open the Logs tab and look in the build log for the line `SLICER INSTALL: ok`.
3. In the phone browser open `<service URL>/api/slice/options`. It should show `"available": true`. Then reload the page: the Slice for P1S section appears below Export.
   The install step ends by slicing a built-in 10 mm cube; only if that works does it write `slicer/.install_ok`, and the page offers slicing only when that file is present for the pinned OrcaSlicer commit. The engine library needs glibc 2.35 or newer, libstdc++ with GLIBCXX_3.4.30, libcrypto.so.3, libfontconfig.so.1, libexpat and libz. If Render's build image lacks one of these, the build log shows `SLICER INSTALL: failed at smoke` (with the last lines of the engine output above it), the page says "Slicer unavailable on this server", and everything else keeps working.
4. If it shows `"available": false` (or the build log says `SLICER INSTALL: failed at ...`), the rest of the app still works: the install step cannot fail the deploy. Send Claude the build-log lines around `SLICER INSTALL`.
5. Expect a slice to take about 3 minutes on the free instance (an estimate from CPU-seconds measured elsewhere, not measured on Render). Models are limited to 150,000 triangles, but that limit does not by itself keep the slicer inside the free instance's memory.
6. Memory: the free instance has 512 MB for the web server and the slicer together. The slicer's memory follows the size of the print (height, layers, supports) more than the triangle count. Measured with the real engine in Claude's workspace on 2026-11-12 (NOT measured on Render): about 180 MB on a tiny model; 254-263 MB on a 35 mm-tall dome at 56,000-150,000 triangles with standard quality and no supports; 286 MB with fine quality and tree supports; 400 MB on a 70 mm full sphere with 150,000 triangles, fine quality and tree supports. A big, tall model with fine quality and supports may run out of memory on the free instance. If it does, the page shows "Still working... (connection hiccup)" for a while, then "The slice expired or was lost. Slice again." Try a smaller or shorter model, 0.28 mm Extra Draft quality, or supports off if the model does not need them. If it keeps happening, the slicer needs a bigger Render instance. Steps for getting the file onto the printer are in [PRINTING.md](PRINTING.md).

## Troubleshooting
- First load takes about a minute: the free Render instance sleeps when idle and has to wake up. Reload after a minute.
- Message mentions quota: the daily free GPU time on Hugging Face is used up. Try again later (it resets daily).
- Message says server not configured: HF_EXTRA_JSON: that value in Render is not a valid JSON object; the default is `{"octree_resolution": 128}`.
- Message says wrong passcode: the passcode must match `IMAGE3D_PASSCODE` in Render exactly. Message says server not configured: `HF_TOKEN` or `IMAGE3D_PASSCODE` is missing in Render (Environment tab).
- Message says too many attempts: wait 10 minutes and try again. After 5 wrong passcodes the server refuses that phone for 10 minutes, and if many wrong passcodes arrive from anywhere it refuses everyone for a while.
- Space asleep, busy or errors: wait and retry, or switch Space. The default is `tencent/Hunyuan3D-2` with the endpoint `/shape_generation`, which makes the shape only (no texture). That suits printing. To switch, open the service in Render, Environment, and set these four values together, then save (Render redeploys):
  - `HF_SPACE`: the Space name, for example `owner/space-name`.
  - `HF_API_NAME`: the endpoint name from the Space page ("Use via API"), for example `/shape_generation`. Setting it to an empty value makes the server guess an endpoint, which is a fallback and is not reliable.
  - `HF_IMAGE_PARAM`: the name of the endpoint's photo input (default `image`).
  - `HF_EXTRA_JSON`: extra settings for the call, as a JSON object. For another Space set it to `{}` unless you know its settings.
  - `SLICE_MEM_MARGIN_MB` (default 40): the slicer is stopped with "out of memory" when the container's memory use gets within this many MB of its limit (read from the cgroup files `memory.current` and `memory.max`).
  - `SLICE_MEM_LIMIT_MB` (default 470): used only when those cgroup files are not available: the slicer is stopped when its memory plus the web server's exceeds this many MB.
  A different Space may need code changes if its inputs or outputs differ. Only the default Space has been run for real.
- Model too heavy or too coarse: detail is set by `HF_EXTRA_JSON` in Render (Environment). The default `{"octree_resolution": 128}` gives about 115,000 triangles. `96` gives about 55,000 (faster on the phone, less detail); `256` gives about 900,000 (too heavy for a phone).
