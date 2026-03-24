# Applio - 商业化求职助手网站架构计划

## Context
将 `/root/application-assistant` 的 12步AI流水线（16个Agent、30+Python脚本）商业化为Web服务。MVP 包含完整的简历+求职信双流水线，先本地开发。

---

## 技术栈

| 层 | 技术 | 理由 |
|---|---|---|
| **前端** | Next.js 14 + Tailwind + shadcn/ui | SSR(SEO)、React交互、快速原型 |
| **后端** | FastAPI (Python) | 直接复用30+现有Python脚本，原生async |
| **任务队列** | Celery + Redis | 15-30分钟流水线不能阻塞请求 |
| **数据库** | PostgreSQL + SQLAlchemy 2.0 | 用户/生成记录/状态追踪 |
| **AI** | Anthropic Python SDK | 替代Claude Code的Task()调用 |
| **PDF** | Playwright (Python) | 替代已停维的pyppeteer |
| **实时进度** | SSE (Server-Sent Events) | 单向推送，比WebSocket简单 |

---

## 系统架构

```
Next.js (3000) → FastAPI (8000) → Celery Worker → Pipeline Engine
                                         ↕               ↕
                                      Redis          PostgreSQL
                                    (broker+pubsub)   (状态持久化)
```

**核心模式**：用户提交 → API创建Generation记录 → Celery异步执行12步流水线 → Redis发布进度 → SSE推送前端

---

## 复用策略

### Python脚本（直接导入，不用subprocess）
从 `application-assistant/scripts/` 复制到 `applio/backend/pipeline/scripts/`：
- `assemble_resume.py`, `aggregate_critiques.py`, `simulate_layout.py`
- `generate_file_paths.py`, `generate_bullet_manifest.py`
- `apply_resume_template.py`, `apply_cover_letter_template.py`
- `check_page_height.py`, `mustache.py`, `config.py` 等
- **需迁移**：`pdf_converter.py` pyppeteer → Playwright

### Agent提示词（原样复制）
16个 `.md` 文件从 `application-assistant/.claude/agents/` 复制到 `applio/backend/pipeline/agents/`
- 启动时加载到内存注册表
- `anthropic.messages.create(system=AGENTS["designer"], messages=[...])`
- 轻量修改：移除Claude Code工具调用指令，改为直接JSON输入/输出

### HTML模板（原样复制）
`template/resume/` 和 `template/cover_letter/` 直接复制

---

## 项目结构

```
/root/applio/
├── docker-compose.yml          # PostgreSQL, Redis
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic/                # DB migrations
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── config.py           # pydantic-settings
│   │   ├── database.py         # SQLAlchemy
│   │   ├── models/             # User, Generation, Job, ResumeProfile
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── api/
│   │   │   ├── generations.py  # POST/GET/DELETE /api/generations
│   │   │   └── auth.py         # Phase 2
│   │   └── services/
│   │       ├── generation_service.py
│   │       └── progress_service.py  # Redis SSE
│   ├── pipeline/
│   │   ├── orchestrator.py     # 12步编排（Celery task）
│   │   ├── agent_registry.py   # 加载.md提示词
│   │   ├── agent_caller.py     # Anthropic SDK封装
│   │   ├── steps/              # step01-step12
│   │   ├── scripts/            # 从application-assistant复制
│   │   ├── agents/             # 16个.md文件
│   │   └── templates/          # HTML模板
│   └── celery_app.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # 落地页
│   │   ├── generate/
│   │   │   ├── page.tsx        # 生成表单
│   │   │   └── [id]/
│   │   │       ├── page.tsx    # 进度仪表盘（SSE）
│   │   │       └── result/page.tsx  # 结果下载
│   │   └── dashboard/page.tsx  # Phase 2
│   ├── components/
│   │   ├── GenerationForm.tsx
│   │   ├── ProgressTracker.tsx # 12步可视化
│   │   └── PdfPreview.tsx
│   └── lib/
│       ├── api.ts
│       └── sse.ts              # SSE连接管理
```

---

## API 端点 (MVP)

```
POST   /api/generations              提交生成（上传YAML + 职位描述）
GET    /api/generations/{id}         获取状态和结果
GET    /api/generations/{id}/progress SSE实时进度流
GET    /api/generations/{id}/resume   下载简历PDF
GET    /api/generations/{id}/cover-letter  下载求职信PDF
DELETE /api/generations/{id}         取消生成
```

---

## 实现阶段

### Phase 1: MVP（核心流水线可用）
1. 项目骨架 + Docker Compose (PostgreSQL, Redis)
2. 复制Python脚本 + 迁移pdf_converter到Playwright
3. 实现agent_caller (Anthropic SDK) + agent_registry
4. 实现orchestrator.py 12步编排 + Celery task
5. FastAPI API端点 + SSE进度推送
6. Next.js前端：生成表单 → 进度仪表盘 → 结果下载

### Phase 2: 用户系统
7. NextAuth.js 登录注册
8. 简历档案管理 + 职位收藏
9. 生成历史仪表盘

### Phase 3: 商业化
10. Stripe支付集成
11. 分级定价（Free/Pro/Enterprise）
12. 使用量追踪 + 计费

---

## 关键技术决策

1. **Celery而非asyncio后台任务** — 15-30分钟流水线需要进程隔离，FastAPI重启不丢任务
2. **文件+DB混合状态** — 中间文件留在磁盘（复用现有脚本），DB追踪高级状态
3. **pyppeteer → Playwright** — pyppeteer已停维，Playwright API相似且活跃
4. **模型选择** — Sonnet用于大多数Agent（快/便宜），Opus用于designer+writing-expert（质量敏感）
5. **MVP无登录** — Session cookie + UUID，先验证核心流水线
6. **并发控制** — asyncio.gather() + semaphore限制5-10个并发Claude API调用

---

## 验证方式

1. 启动Docker Compose（PostgreSQL + Redis）
2. 启动Celery worker + FastAPI
3. 启动Next.js dev server
4. 在前端提交一个职位描述 + 示例YAML
5. 观察进度仪表盘实时更新12步
6. 下载生成的PDF，与application-assistant的输出对比质量
