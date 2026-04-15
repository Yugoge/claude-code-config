# Plan: JD Input Source Tab Redesign

## Context

Generate 页面的 "Recent JDs" 和 "Upload JD File" 两个毛玻璃按钮在扁平化表单中突兀。改为 3-tab segmented control（复用 `GlassSegmentedControl` 组件），三个 tab：Saved Jobs / Recent JDs / Manual。选中 Saved Job 或 Recent JD 后自动填入 textarea 并切回 Manual tab。

## File Changes

### 1. `frontend/src/app/generate/recent-jds.tsx` — 导出接口
- Export `RecentJd` interface 和 `getRecentJds()` function

### 2. NEW `frontend/src/app/generate/saved-jobs-list.tsx`
- 使用 `useSavedJobs("all", 1)` 获取已保存职位
- 渲染 `max-h-60 overflow-y-auto thin-scrollbar` 列表
- 每项显示 title (bold) + company + description 前60字符预览
- 点击调用 `onSelect(job.description)`
- 空态/加载态/无 description 处理
- 使用 `glass-menu-item` 样式

### 3. NEW `frontend/src/app/generate/recent-jds-list.tsx`
- 调用 `getRecentJds()` 读 localStorage
- 内联列表（非 portal dropdown），`glass-menu-item` 样式
- 点击调用 `onSelect(item.text)`

### 4. `frontend/src/app/generate/jd-section.tsx` — 主要重写
- 删除 `RecentJdsToggle` 和 `JdToolbar`
- 新增 `activeTab` state：`"saved-jobs" | "recent-jds" | "manual"`，默认 `"manual"`
- 渲染 `GlassSegmentedControl` 三个选项
- `saved-jobs` tab → `<SavedJobsList>`
- `recent-jds` tab → `<RecentJdsList>`
- `manual` tab → `<JdUrlInput>` + `<UploadJdFileButton>`
- `JobDescriptionField` textarea 始终可见
- 选中回调：填入 textarea + `setActiveTab("manual")`

### 5. `frontend/src/app/generate/generate-form.tsx` — 微调
- 将 `JdUrlInput` 移入 `JdSectionWithRecents` 内部（Manual tab）
- 移除 generate-form 中的独立 `<JdUrlInput>`

### 6. `frontend/src/locales/en.json` + `zh.json`
- 新增 `generate.jdSource.savedJobs` / `.recentJds` / `.manual` 等 i18n keys

## Verification
1. 打开 /generate，确认 3-tab segmented control 显示
2. 点 Saved Jobs tab，确认列表加载
3. 点选一个 saved job，确认 textarea 填入并自动切回 Manual
4. 点 Recent JDs tab，确认列表显示
5. Manual tab 保持原有功能（URL parse + upload + textarea）
6. 移动端 375px 验证 tab 不溢出
