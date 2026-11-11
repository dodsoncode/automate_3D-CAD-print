# Deploy Image3D on Render (from a phone)

Status: the server code is tested only with a FAKE generator. The live Hugging Face call and the Render deploy are NOT verified yet; the first real run is TI7.

## A. Hugging Face account and token
1. Open huggingface.co in your phone browser and tap Sign Up. Create a free account and confirm your email.
2. Open huggingface.co/settings/tokens and tap Create new token.
3. Choose the type Read, name it `image3d`, and create it.
4. Copy the token (it starts with `hf_`). Keep it somewhere private; you will paste it into Render once. Never put it in the repo or the page.

## B. Render
1. Open dashboard.render.com and sign in (the same account as mental_stength is fine).
2. Tap New, then Blueprint.
3. Connect GitHub if asked, then pick the repo `dodsoncode/automate_3D-CAD-print`.
4. Choose the branch `main` (the Blueprint file `render.yaml` is at the repo root). Tap Continue.
5. Render asks for two secret values. Set `HF_TOKEN` to the token from part A, and `IMAGE3D_PASSCODE` to a passcode you invent (anything private, you will type it on the page).
6. Tap Apply / Deploy and wait for the deploy to say Live.

## C. Use it
1. Open the service URL shown at the top of the Render page (`https://image3d-....onrender.com`).
2. The Generate from a photo box shows up when the server is awake. Choose a photo, type the passcode (the page remembers it on this phone), tap Generate.
3. Wait a minute or two. The model opens in the editor; then delete pieces, resize, cut and export the STL as usual.

## Troubleshooting
- First load takes about a minute: the free Render instance sleeps when idle and has to wake up. Reload after a minute.
- Message mentions quota: the daily free GPU time on Hugging Face is used up. Try again later (it resets daily).
- Message says wrong passcode: the passcode must match `IMAGE3D_PASSCODE` in Render exactly. Message says server not configured: `HF_TOKEN` or `IMAGE3D_PASSCODE` is missing in Render (Environment tab).
- Space asleep, busy or errors: wait and retry, or switch Space. In Render open the service, Environment, and set `HF_SPACE` to another Space (for example `trellis-community/TRELLIS`). If the server cannot find the right endpoint, set `HF_API_NAME` to the Space's endpoint name (the Space page, "Use via API", shows names like `/generation_all`). Leave `HF_API_NAME` empty to auto-pick. Save; Render redeploys.
