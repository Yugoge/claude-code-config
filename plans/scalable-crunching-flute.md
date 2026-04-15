# Issue #3: Subagent Sidechain Envelopes

## Context

When clicking an Agent/Task tool card in the sidebar, only the prompt + final result are shown. Subagent internal operations (tool calls, text, thinking) are missing because:

1. The CLI mapper sends sidechain root user messages as `text` events, but the App tracer needs `sidechain` content type for prompt matching
2. The wire protocol lacks a `sidechain` event type
3. The App normalizer doesn't create `sidechain` content from session protocol envelopes
4. For Agent tools (not Task), no synthetic sidechain root message is created
5. Children can't inherit `sidechainId` because the subagent CUID2 isn't registered in the tracer's UUID map

The buffering/replay mechanism in the mapper already works correctly - sidechain messages ARE emitted with the `subagent` CUID2 field. The gap is in the App's ability to link them to their parent tool call.

## Changes (5 files)

### 1. Wire Protocol: Add `sidechain` event type
**File:** `packages/happy-wire/src/sessionProtocol.ts`

Add new schema after line 87 (after `sessionWrapEventSchema`):
```typescript
const sessionSidechainEventSchema = z.object({
    t: z.literal('sidechain'),
    prompt: z.string(),
});
```

Add to `sessionEventSchema` discriminated union (line 89-100):
```typescript
export const sessionEventSchema = z.discriminatedUnion('t', [
    // ... existing ...
    sessionSidechainEventSchema,
]);
```

### 2. CLI Mapper: Emit `sidechain` event for root prompt
**File:** `packages/happy-cli/src/claude/utils/sessionProtocolMapper.ts`

Change lines 680-683 from:
```typescript
if (message.isSidechain) {
    const turnId = ensureTurn(state, envelopes);
    maybeEmitSubagentStart(state, turnId, subagent, envelopes);
    envelopes.push(createEnvelope('agent', { t: 'text', text }, { turn: turnId, subagent }));
}
```
to:
```typescript
if (message.isSidechain) {
    const turnId = ensureTurn(state, envelopes);
    maybeEmitSubagentStart(state, turnId, subagent, envelopes);
    envelopes.push(createEnvelope('agent', { t: 'sidechain', prompt: text }, { turn: turnId, subagent }));
}
```

### 3. CLI Launcher: Create synthetic sidechain root for Agent too
**File:** `packages/happy-cli/src/claude/claudeRemoteLauncher.ts`

Change the condition (around line 330) from:
```typescript
if (c.type === 'tool_use' && c.name === 'Task' && c.input && typeof (c.input as any).prompt === 'string')
```
to:
```typescript
if (c.type === 'tool_use' && (c.name === 'Task' || c.name === 'Agent') && c.input && typeof (c.input as any).prompt === 'string')
```

### 4. App Normalizer: Handle `sidechain` event
**File:** `packages/happy-app/sources/sync/typesRaw.ts`

In `normalizeSessionEnvelope()`, add a new handler before the final `return null` (line 720):
```typescript
if (envelope.ev.t === 'sidechain') {
    return {
        id: messageId,
        localId,
        createdAt: messageCreatedAt,
        role: 'agent',
        isSidechain: true,
        content: [{
            type: 'sidechain',
            uuid: messageId,
            prompt: envelope.ev.prompt,
        }],
        meta,
    } satisfies NormalizedMessage;
}
```

### 5. App Tracer: Register subagent CUID2 for child inheritance
**File:** `packages/happy-app/sources/sync/reducer/reducerTracer.ts`

When processing tool-call-start for Agent/Task (around line 188-209), add registration of `sessionSubagent` CUID2:
```typescript
if (content.type === 'tool-call' && isSubagentToolCall(content.name)) {
    if (content.input && 'prompt' in content.input) {
        state.taskTools.set(message.id, { messageId: message.id, prompt: content.input.prompt });
        state.promptToTaskId.set(content.input.prompt, message.id);
    }
    // NEW: Register sessionSubagent CUID2 so children with parentUUID=CUID2 can inherit
    if (content.input && 'sessionSubagent' in content.input && typeof content.input.sessionSubagent === 'string') {
        state.uuidToSidechainId.set(content.input.sessionSubagent, message.id);
    }
}
```

## Data Flow After Fix

```
1. Claude SDK outputs assistant msg with tool_use (Agent/Task)
   → CLI launcher creates synthetic sidechain user msg (prompt)
   → mapper emits: tool-call-start (with args.sessionSubagent=CUID2)
   → mapper emits: sidechain event (with subagent=CUID2, prompt=...)

2. Claude SDK outputs sidechain msgs (text, tool calls, thinking)
   → mapper emits: text/tool-call-start/tool-call-end (with subagent=CUID2)

3. App normalizer:
   → tool-call-start → tool-call content (with input.sessionSubagent)
   → sidechain event → sidechain content (with prompt)
   → text/tool events → text/tool content (with parentUUID=CUID2)

4. App tracer:
   → tool-call-start → registers CUID2→messageId in uuidToSidechainId
   → sidechain root → prompt matches → sidechainId=messageId
   → children → parentUUID=CUID2 → found in uuidToSidechainId → inherit sidechainId

5. Reducer Phase 4: processes traced sidechain msgs → state.sidechains
6. message.children populated → SidebarAgentConversation renders
```

## Verification

1. Build CLI: `cd packages/happy-cli && yarn build`
2. Build wire: `cd packages/happy-wire && yarn build`
3. Build App: `cd packages/happy-app && npx expo export --platform web`
4. Deploy dev web: `docker build -f Dockerfile.webapp --build-arg HAPPY_SERVER_URL=https://api-dev.life-ai.app -t happy-app:dev . && cd /root/deploy && docker compose up -d happy-web-dev`
5. Open dev.life-ai.app, trigger Agent tool in a session
6. Click the Agent tool card → sidebar should show subagent's full conversation
7. Verify on both desktop and mobile (390x844) viewports
