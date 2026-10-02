# Production deployment

The `Build and deploy` workflow runs after a successful `CI` push to `main`. It builds two images, stages `docker-compose.prod.yml` on the VPS, then pulls and starts the services. Images use the commit SHA; the `latest` tag is published but not used for deployment.

Configure these repository secrets before enabling deployment:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS DNS name or IP address |
| `VPS_PORT` | SSH port |
| `VPS_USER` | Deployment account |
| `VPS_SSH_KEY` | Private SSH key for that account |

The workflow retrieves the VPS host key with `ssh-keyscan` using `VPS_HOST` and
`VPS_PORT`. It stores the key in a temporary `known_hosts` file and requires
strict host-key checking for both `ssh` and `scp` throughout that deployment.
Deployment stops if the scan fails or returns no matching key. The temporary
SSH files are removed even if deployment fails; no host-key secret is required.
The initial key is trusted from the network on each workflow run, so it is not
independently verified against a preconfigured fingerprint.

## Script layout

| Script | Runs on | Purpose |
| --- | --- | --- |
| `scripts/ci/lint-shell.sh` | CI runner | Bash syntax and ShellCheck for all scripts under `scripts/` |
| `scripts/ci/validate-compose.sh` | CI runner | Local, production and CS.MONEY test Compose validation with test-only environment values |
| `scripts/deploy/deploy-ssh.sh` | Deploy runner | SSH configuration, file transfer, remote execution and credential cleanup |
| `scripts/deploy/deploy-production.sh` | VPS | Image pull, catalogue seed, service restart and health checks |

The SSH helper copies the production script to `/opt/true-roi` under its existing
filename, `deploy-production.sh`. Run the CI scripts from the repository root.

## Production execution

GitHub Actions serializes workflow runs with the `true-roi-production` concurrency group. On the VPS, `/opt/true-roi/.deploy.lock` is held with `flock` while the staged Compose file is validated and installed, images are pulled, and services are started. The VPS user needs write access to `/opt/true-roi` and `flock` from `util-linux`.

The Compose project is named `true-roi` to keep its existing PostgreSQL volume. Persistent containers have stable names:

| Service | Container |
| --- | --- |
| PostgreSQL | `true-roi-postgres` |
| API and frontend | `true-roi-api` |
| CS.MONEY crawler | `true-roi-csmoney-crawler` |
| CS.MONEY demand worker | `true-roi-csmoney-demand` |

`catalog-seed` is a one-off service, so Compose manages its container name. Docker's `local` log driver rotates each service log at 10 MB and keeps three files. The deploy job prints the image SHA and final `docker compose ps --all` output, waits up to two minutes for a healthy API, and checks both workers are running. On API health failure it prints the last 30 API log lines.

The deployment check is process-level only. A successful run does not prove that
CS.MONEY, CSFloat, or another external provider returned fresh market data. The
current provider-level limitations are documented in
[`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

On the VPS:

```bash
cd /opt/true-roi
docker compose -f docker-compose.prod.yml ps --all
docker compose -f docker-compose.prod.yml logs --tail=100 api
docker compose -f docker-compose.prod.yml logs --tail=100 csmoney-worker csmoney-demand
```

The first deployment with the new Compose file recreates the named containers. The PostgreSQL data remains in the existing `true-roi_true_roi_postgres` volume, provided the current VPS stack was created from `/opt/true-roi` with Compose's default project name.
