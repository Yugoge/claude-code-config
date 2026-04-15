# Plan: Auto-login page at /auth/qijie

## Context
qijie 需要从国产手机浏览器（华为等）登录 happy-web，但这些浏览器拦截 `javascript:` 协议。需要一个密码保护的静态 HTML 页面，输入密码后自动注入 localStorage 凭据并跳转到主页。

## Approach: Volume mount static HTML into happy-web container

**Key insight**: 现有 nginx `try_files` 会先尝试 `$uri/index.html`，所以 `/auth/qijie/index.html` 会被直接 serve，不需要改 nginx config 也不需要重建 Docker image。

### Steps

1. **创建目录和 HTML 文件**
   - `/root/deploy/auth-pages/qijie/index.html` — 密码保护的登录页
   - 密码: `15828522037`（前端 SHA-256 hash 比对，不明文存储在 HTML 中）
   - 正确后注入 `auth_credentials` + `mmkv.server-config\custom-server-url` 到 localStorage
   - 自动 `location.href = '/'` 跳转

2. **修改 docker-compose.yml**
   - 给 happy-web 添加 volume mount: `/root/deploy/auth-pages:/usr/share/nginx/html/auth:ro`

3. **重启 happy-web 容器**
   - `cd /root/deploy && docker compose up -d happy-web`（安全，不影响 daemon）

### HTML 页面设计
- 简洁密码输入框 + 登录按钮
- 密码用 SHA-256 hash 存储在页面中（不是明文）
- 凭据用密码 AES 加密存储（或直接 base64，因为密码只是防误触级别）
- 输入正确密码 → 注入 localStorage → 跳转 `/`

### Credentials (qijie)
- token: `eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiJjMDE5OWI5Yzk0ZWEzNGYwZDQ1N2QyNDE4IiwiaWF0IjoxNzc1MzkwNjcxLCJuYmYiOjE3NzUzOTA2NzEsImlzcyI6ImhhbmR5IiwianRpIjoiY2ZkM2I4OTEtOWI4Ni00Y2JkLWJmZjctMTBjMTZlMjRjZDI0In0.xxYxMB_CLpnRuK1b8Bnw9aiyxdw0OrV0D72XR1BrNHnyuHTUXY4-XLPYTcvjanym0rMweZ5n2KNfxcaIZIMzDw`
- secret: `t3fZRkAj-esIm_9ewQm2Vu9UrC3xKcpdLgKvjVuRrjw`
- server: `https://api.life-ai.app`

### Files to create/modify
- **Create**: `/root/deploy/auth-pages/qijie/index.html`
- **Modify**: `/root/deploy/docker-compose.yml` (add volume mount to happy-web)

### Verification
1. `curl -s http://localhost:8090/auth/qijie/` 应返回 HTML 页面
2. 手机浏览器打开 `https://life-ai.app/auth/qijie` 看到密码框
3. 输入正确密码 → 跳转到主页并登录
