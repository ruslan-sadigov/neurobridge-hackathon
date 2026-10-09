# Deploying BidBridge on DigitalOcean App Platform

Two components from the same GitHub repo, each built from its own Dockerfile:

| Component | Source directory | Dockerfile | Port |
|---|---|---|---|
| `backend` (FastAPI) | `backend` | `backend/Dockerfile` | 8080 |
| `frontend` (Next.js) | `frontend` | `frontend/Dockerfile` | 3000 |

Both images were built and run together locally with `docker compose up --build` (health, CORS and page serving
checked). **The DigitalOcean steps themselves have not been run**; button labels in the DigitalOcean console may differ
slightly from the names used here.

## 0. Before you start

- [ ] Everything is committed **and pushed to GitHub** (App Platform builds from the repo, not from your disk).
- [ ] `docker compose up --build` works on your machine (see `README.md`).
- [ ] You have a Gemini API key. Check the model name is still available to your key before the demo.
- [ ] The root `.env` is **not** in the repo (it is gitignored). Never commit it. If a key was ever pasted somewhere
      public, create a new one.

## 1. Deploy the backend first

1. DigitalOcean console > **Create > App Platform** > pick your GitHub repo and branch `main`.
2. Add a component from the repo and set **Source directory** = `backend`. Choose **Dockerfile** as the build method
   (App Platform detects `backend/Dockerfile`).
3. Component type **Web Service**, **HTTP port = 8080**, **instances = 1**.
   Keep it at one instance: analyses run as in-process background jobs, and the database lives on the instance.
4. Under the component's **Environment Variables** add (scope: run time):

   | Variable | Value | Notes |
   |---|---|---|
   | `LLM_PROVIDER` | `gemini` | |
   | `GEMINI_API_KEY` | your key | **Mark as Encrypted/Secret** |
   | `GEMINI_MODEL` | `gemini-3.5-flash-lite` | any model your key can call |
   | `LLM_MIN_INTERVAL_S` | `6` | stays under the free tier's 15 requests/minute |
   | `CORS_ORIGINS` | `http://localhost:3000` for now | **you will change this in step 3** |

   `EMBEDDING_BACKEND`, `DATABASE_URL`, `STORAGE_DIR` and `PORT` already have correct defaults in the Dockerfile.
5. **Health check:** HTTP path `/health`.
6. Choose a small instance size and **Create Resources**. Wait for the deploy to finish.
7. Copy the backend's public URL, e.g. `https://backend-xxxxx.ondigitalocean.app`, and check
   `<backend URL>/health` returns `{"status":"ok"}`.

## 2. Deploy the frontend

1. In the same app, **Add component** from the same repo: **Source directory** = `frontend`, Dockerfile build,
   **Web Service**, **HTTP port = 3000**.
2. Add the variable **`NEXT_PUBLIC_API_URL`** = the backend URL from step 1 (no trailing slash).
   **Scope it to Build time** (or both). Next.js bakes `NEXT_PUBLIC_` values into the browser bundle during the
   build; a run-time-only variable has no effect.
3. Optionally add `NEXT_PUBLIC_USE_MOCK=false` (build time).
4. Deploy and copy the frontend URL, e.g. `https://frontend-xxxxx.ondigitalocean.app`.

## 3. Connect them (CORS)

The backend only accepts browser calls from origins listed in `CORS_ORIGINS`.

1. Open the **backend** component's variables, set `CORS_ORIGINS` = the frontend URL (exact, https, no trailing slash;
   comma-separate several origins, e.g. a custom domain too).
2. Save and let the backend redeploy. If you change `NEXT_PUBLIC_API_URL` later, the **frontend must be rebuilt**.

Order summary: backend (placeholder CORS) -> frontend (with backend URL) -> backend CORS (with frontend URL).

## 4. Smoke test (about 5 minutes, one analysis = about 10 Gemini requests)

```bash
curl https://<backend URL>/health
```

```bash
curl -i -X OPTIONS https://<backend URL>/analyses -H "Origin: https://<frontend URL>" -H "Access-Control-Request-Method: POST"
```

The second should show `access-control-allow-origin: https://<frontend URL>`. Then in the browser:

1. Open the frontend URL.
2. Upload `backend/fixtures/tenders/TR_CFCU_IT_network_equipment_2018.pdf`, click **Load demo profile**, **Run**.
3. Wait about 1-2 minutes (62 s measured for this tender). Expect the dashboard with about 26 requirements, a NO_GO recommendation and critical risks for
   the turnover requirements.
4. Open a requirement, click **View full page**: the tender page text should load with the sentence highlighted.
5. A browser address of the form `...?analysis=<id>` should reopen the same results after a refresh.

## 5. Things to know before the demo

- **Data is not persistent.** To my knowledge App Platform instances have no persistent disk: uploads and the SQLite
  database are lost on every redeploy or restart. Deploy, then run your demo analysis **afterwards**; do not redeploy
  between preparing and presenting. For persistence use a managed Postgres database (`DATABASE_URL=postgresql+psycopg://...`)
  and object storage, which would need small code changes for file storage.
- **No authentication.** Anyone who has the URL can upload files and spend your Gemini quota (free tier: 15 requests
  per minute and 500 per day on the key we used, shared by all users). Share the URL only with judges and teammates,
  and consider adding a simple access check (shared token) before posting it publicly. This is a known MVP gap.
- **Quota.** One analysis is about 10 requests (repeat runs of the same tender and profile are cached). Keep a recorded fallback (screen recording or screenshots of a finished
  analysis) in case the daily quota is used up or the network is slow.
- **Cold starts / slow first request.** Open the app a few minutes before presenting so the first page is warm.
- **Cost.** Two small always-on services are billed per instance. Check the current DigitalOcean pricing page and
  destroy the app after the event if you do not need it.
- **Uploaded tenders are stored on the instance.** Use public or synthetic documents only (as the spec requires).
  `DELETE /analyses/{id}` removes an analysis and its files.

## 6. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Frontend shows "Cannot reach the API" | `CORS_ORIGINS` does not exactly match the frontend URL, or `NEXT_PUBLIC_API_URL` was set after the build. Fix and redeploy the right component |
| Requests go to `localhost:8000` from the deployed site | `NEXT_PUBLIC_API_URL` was missing at **build** time. Add it with build scope and rebuild the frontend |
| Analysis ends **FAILED** with "API key not valid" | Wrong or missing `GEMINI_API_KEY`, or the key cannot use `GEMINI_MODEL` |
| Analysis ends FAILED mentioning quota / 429 | Daily or per-minute limit reached. Wait, or use another key |
| Analysis stays PENDING or RUNNING for more than 6-7 minutes | Check the backend runtime logs; the instance may have restarted (state is lost) |
| Upload returns 415 or 413 | Not a PDF, or file over 50 MB |
| Backend unhealthy on deploy | Wrong HTTP port (must be 8080) or health path (must be `/health`) |
| Results disappeared | The instance restarted or you redeployed; see "Data is not persistent" |

## 7. Alternative: one domain, no CORS (not tested)

App Platform can route paths of one app to different components, for example `/` to the frontend and `/api` to the
backend. Then `NEXT_PUBLIC_API_URL=/api` removes the CORS step and the circular setup. This needs a path-prefix check
(the backend expects routes without `/api`), so try it only if you have time to test it.
