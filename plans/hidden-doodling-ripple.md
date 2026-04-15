# Issue #3: Subagent Sidechain Envelopes

## Context

When clicking an Agent/Task tool card in the app sidebar, only the prompt and final result are shown. The subagent's internal operations (tool calls, text output, thinking) are missing because they never reach the app.

**Root cause**: The Claude SDK's `stream-json` stdout does NOT emit sidechain messages for subagent internal operations. It only emits the parent tool_use and final tool_result. However, Claude Code DOES write all sidechain messages to the JSONL session file on disk.

**Key insight**: The entire downstream pipeline (mapper, normalizer, tracer, reducer, UI) already works correctly for sidechain messages. The only gap is that sidechain messages from the JSONL file are not being forwarded to the server.

## Changes

### 1. `packages/happy-cli/src/claude/utils/sessionScanner.ts` (~line 51)

In the `sendExisting: false` path, add `isSidechain === true` forwarding alongside the existing `isMeta` forwarding:

```typescript
// Existing: forwards isMeta messages even when sendExisting=false
if ((m as { isMeta?: boolean }).isMeta === true) {
    opts.onMessage(m);
}
// NEW: also forward sidechain messages (subagent internal operations)
if ((m as { isSidechain?: boolean }).isSidechain === true) {
    opts.onMessage(m);
}
```

This ensures sidechain messages are forwarded even if they're already in the JSONL when the scanner starts (same timing fix as isMeta).

### 2. `packages/happy-cli/src/claude/claudeRemoteLauncher.ts`

**a) Add deduplication set** (near line 153, alongside other tracking state):
```typescript
let sentSidechainUuids = new Set<string>();
```

**b) Track sidechain UUIDs in onMessage** (after `messageQueue.enqueue`, around line 326):
```typescript
// Track sidechain message UUIDs for deduplication with JSONL scanner
if ((logMessage as any).isSidechain === true && (logMessage as any).uuid) {
    sentSidechainUuids.add((logMessage as any).uuid);
}
```

**c) Extend meta-scanner callback** (line 438-443) to also forward sidechain messages:
```typescript
onMessage: (message) => {
    if ((message as { isMeta?: boolean }).isMeta === true) {
        session.client.sendClaudeSessionMessage(message);
    }
    // Forward sidechain messages (subagent internal operations)
    const uuid = (message as any).uuid;
    if ((message as { isSidechain?: boolean }).isSidechain === true
        && typeof uuid === 'string'
        && !sentSidechainUuids.has(uuid)) {
        sentSidechainUuids.add(uuid);
        session.client.sendClaudeSessionMessage(message);
    }
}
```

**d) Remove fake Task sidechain root** (lines 329-342):
Delete the `convertSidechainUserMessage` block. Real sidechain messages will come from the JSONL scanner, including the root prompt message.

**e) Reset dedup set** in the finally block alongside other resets:
```typescript
sentSidechainUuids.clear();
```

### No changes needed

- **`sessionProtocolMapper.ts`**: Already produces correct envelopes with `subagent` field for sidechain messages (verified by tests including `task_non_sdk.jsonl` fixture)
- **`typesRaw.ts`**: `normalizeSessionEnvelope()` already converts `envelope.subagent` to `parentUUID` and `isSidechain: true`
- **`reducerTracer.ts`**: Already links sidechain messages via `toolCallToMessageId.get(parentUUID)`, with `getToolCallParentIds` extracting both tool `id` and `sessionSubagent` from args
- **`reducer.ts`**: Phase 4 already processes sidechain messages and populates `state.sidechains`
- **`SidebarAgentConversation.tsx`**: Already renders `message.children`

## Data Flow (after fix)

```
Claude Code JSONL file (contains ALL messages including sidechain)
  -> sessionScanner detects file change
  -> onMessage callback filters for isSidechain === true
  -> sendClaudeSessionMessage(message) 
  -> sessionProtocolMapper produces envelopes with subagent field
  -> envelopes sent to server -> app
  -> normalizeSessionEnvelope sets parentUUID = subagent, isSidechain = true
  -> reducerTracer links via toolCallToMessageId
  -> reducer Phase 4 stores in state.sidechains
  -> message.children populated from state.sidechains
  -> SidebarAgentConversation renders children
```

## Verification

1. Build CLI: `cd packages/happy-cli && yarn build`
2. Deploy to dev: rebuild dev daemon from happy-dev source
3. Start a dev session and ask Claude to use the Agent tool (e.g., "use the Agent tool to search for README files")
4. Open dev.life-ai.app, find the Agent tool card
5. Click to open sidebar - should see subagent internal conversation (tool calls, text, not just prompt + result)
6. Run existing tests: `cd packages/happy-cli && yarn test` (mapper tests should still pass)
