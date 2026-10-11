# Deploy the static demo to Cloudflare Workers

Cloudflare Workers Static Assets serves the Vite output, JSON catalog, images, and XYZ
satellite tiles. No Worker script, R2 bucket, database, or application secrets are required.
OpenFreeMap still supplies the street basemap over the internet.

## Local verification

Use the Node version in `.nvmrc` and pnpm 12.11.2 (pinned in `package.json`).

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm run build
pnpm run preview:worker
```

`preview:worker` serves the existing `dist/` through the local Workers runtime.
For manual deployment, build first, authenticate with `pnpm exec wrangler login`, then
run `pnpm run deploy`.

## Automatic deployment from main

In Cloudflare Workers & Pages, create a Worker by connecting the GitHub repository
`dekkinlarp/FloodBeacon`. Install/authorize the Cloudflare Workers & Pages GitHub App
for this repository; organization approval may be required by GitHub.

Set:

| Setting | Value |
| --- | --- |
| Worker name | `floodbeacon-demo` (must match `wrangler.jsonc`) |
| Production branch | `main` |
| Root directory | `frontend` |
| Build command | `pnpm install --frozen-lockfile && pnpm run build` |
| Deploy command | `pnpm run deploy` |
| Build variable | `PNPM_VERSION=12.11.2` |
| Build variable | `SKIP_DEPENDENCY_INSTALL=1` |

The explicit install command uses the committed lockfile. Cloudflare reads `.nvmrc`
for Node. Disable non-production branch builds if only main should deploy, and optionally
set build watch paths to `frontend/**` to skip backend-only changes.

Cloudflare Workers Builds generates/manages its deployment API token. No Cloudflare
secret needs to be added to this repository or provided to the frontend. The Worker is
served at `floodbeacon.tech` and `www.floodbeacon.tech` through the `routes` custom domains
in `wrangler.jsonc`; Cloudflare creates the DNS records and certificates on deploy. The zone
must be on the same Cloudflare account, with no existing A/AAAA/CNAME record for either name.

`worker/index.ts` 301-redirects page requests on HTTP, `www`, or `workers.dev` to
`https://floodbeacon.tech`. Built assets (`/assets/*`) and imagery (`/static/*`) skip the
script via `run_worker_first`, so tile loads do not count as Worker invocations.
`preview:worker` passes `CANONICAL_REDIRECTS:off` because local
`wrangler dev` presents requests as `http://floodbeacon.tech`.

Merge the reviewed frontend changes to main before triggering the first build.
Every subsequent main push will build and deploy through the Git integration.

Official references: [Git integration](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/),
[build configuration](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/),
[build image](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/),
and [SPA asset routing](https://developers.cloudflare.com/workers/static-assets/routing/single-page-application/).

## Demo behavior and data

Dispatch and team actions stay in one browser tab and reset on refresh. No SMS is sent,
no live intake is polled, and no backend synchronization occurs. The historical satellite
catalog and files are under `public/static/imagery/`; preserve attribution and license
metadata when updating the snapshot. The Merritt access replay UI is outside this demo.
