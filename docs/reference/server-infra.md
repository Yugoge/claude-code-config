# Server Infrastructure — Full Reference Tables

> Extracted from `~/.claude/CLAUDE.md` for low-frequency lookup. The slimmed CLAUDE.md keeps only the hardware line, disk layout, Happy architecture diagram, systemd services table, and key rules.
> Last updated: 2026-04-16

---

## Cloudflare Tunnels

- `life-ai.app` → happy-server (port 3000) + happy-web (8090)
- `dev.life-ai.app` → happy-web-dev (port 8097)

---

## Web Auth Pages (Browser Login)

| Account | URL | Password |
|---------|-----|----------|
| Default | `https://life-ai.app/auth/default` | `1900015516` |
| Jade    | `https://life-ai.app/auth/jade`    | `1900015516` |
| Qijie   | `https://life-ai.app/auth/qijie`   | `15828522037` |
| Dev     | `https://dev.life-ai.app/auth/dev` | `1900015516` |

Files: `/root/deploy/auth-pages/{default,jade,qijie,dev}/index.html`

---

## Docker Services

Compose: `/root/deploy/docker-compose.yml`. All 22 containers managed by a
single compose project with `restart: always`.

<!-- AUTO:docker-services -->
| Service | Container | Port | Notes |
|---------|-----------|------|-------|
| postgres | happy-postgres | internal | postgres:15-alpine |
| redis | happy-redis | internal | redis:7-alpine |
| minio | happy-minio | 9000→9000, 9001→9001 | minio/minio:latest |
| happy-server | happy-server | 3000→3005 | happy-server-happy-server; depends on postgres, redis, minio |
| cloudflared-lifeai | cloudflared-lifeai | host network | cloudflare/cloudflared:latest; depends on happy-server, happy-web, budget-web, applio-web |
| happy-web | happy-web | 8090→80 | happy-app:message-fixes; depends on happy-server |
| postgres-dev | happy-postgres-dev | internal | postgres:15-alpine |
| redis-dev | happy-redis-dev | internal | redis:7-alpine |
| happy-server-dev | happy-server-dev | 3005→3005 | happy-server-dev:latest; depends on postgres-dev, redis-dev, minio |
| happy-web-dev | happy-web-dev | 8097→80 | happy-app:dev; depends on happy-server-dev |
| knowledge-web | knowledge-web | 8092→80 | nginx:alpine |
| budget-web | budget-web | 8093→80 | nginx:alpine |
| leadership-web | leadership-web | 8091→80 | nginx:alpine |
| travel-web | travel-web | 8094→80 | nginx:alpine |
| apply-web | apply-web | 8095→80 | nginx:alpine |
| applio-postgres | applio-postgres | internal | postgres:16-alpine |
| applio-redis | applio-redis | internal | redis:7-alpine |
| applio-api | applio-api | internal | applio-api:latest; depends on applio-postgres, applio-redis |
| applio-worker | applio-worker | internal | applio-api:latest; depends on applio-api |
| applio-beat | applio-beat | internal | applio-api:latest; depends on applio-api |
| applio-web | applio-web | 8096→3000 | applio-web:latest; depends on applio-api |
| ib-gateway | ib-gateway | 127.0.0.1→4001→4003, 127.0.0.1→4002→4004, 127.0.0.1→5900→5900 | ghcr.io/gnzsnz/ib-gateway@sha256:92ec011323ad1a36ff8a346d430ae26ff94ee300765f4b1a67a04fe05d25f96a |
<!-- /AUTO:docker-services -->
