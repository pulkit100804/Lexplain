# Production-Level AI Agents with n8n

This guide explains:
1. How to build agents in n8n.
2. What the model/version dropdown means.
3. Starter code and workflow patterns you can use in production.

---

## 1) Can you build agents with n8n?

Yes. n8n is a strong orchestration layer for AI agents because it gives you:
- Triggering (Webhook, Cron, queues)
- Tool use (HTTP, DB, Slack, Notion, etc.)
- Memory (Postgres/Redis/vector DB)
- Control flow (if/else, retries, loops)
- Observability (execution logs, error workflows)

Think of n8n as the **agent runtime + integration bus**.

---

## 2) Model/version dropdown: how it works

In n8n AI nodes, the model dropdown usually maps to the provider API model ID.

- **Provider**: OpenAI / Anthropic / Google / etc.
- **Model**: e.g. `gpt-4.1`, `gpt-4o-mini`, etc.
- **Version behavior**:
  - Some IDs are pinned (stable behavior)
  - Some are rolling aliases (provider may update behind the same name)

### Recommended production practice

- Use a **config variable** for model (e.g., `OPENAI_MODEL`) instead of hardcoding.
- Keep one model per use-case tier:
  - Fast/cheap classifier model
  - High-quality reasoning model
- Add fallback logic:
  - On timeout/rate limit, retry with backoff
  - Optional second model fallback

---

## 3) Production architecture pattern

Use this 7-step workflow shape:

1. **Ingress**: Webhook/queue receives request + correlation ID.
2. **Validation**: Schema check + auth + rate limit guard.
3. **Planner**: LLM decides intent and required tools.
4. **Tools**: n8n nodes call APIs/DB/search.
5. **Responder**: LLM crafts final answer using tool outputs.
6. **Safety/Policy**: redaction, allowed-action checks.
7. **Egress + Logs**: return response; store traces/metrics.

---

## 4) Environment variables (example)

```bash
# LLM
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini

# Infra
POSTGRES_URL=postgres://...
REDIS_URL=redis://...

# App
APP_ENV=production
REQUEST_TIMEOUT_MS=30000
MAX_RETRIES=3
```

---

## 5) Example: n8n Code Node helper (tool-call router)

Use this in a **Code** node after planner output:

```javascript
// Input expected from previous AI node:
// {
//   "action": "get_customer" | "create_ticket" | "search_docs",
//   "payload": {...},
//   "requestId": "..."
// }

const item = $input.first().json;

const allowedActions = new Set([
  'get_customer',
  'create_ticket',
  'search_docs',
]);

if (!item.action || !allowedActions.has(item.action)) {
  throw new Error(`Blocked or missing action: ${item.action}`);
}

return [{
  json: {
    route: item.action,
    payload: item.payload || {},
    requestId: item.requestId || crypto.randomUUID(),
    ts: new Date().toISOString(),
  }
}];
```

Then branch with a **Switch** node:
- `route == get_customer` -> HTTP/DB node
- `route == create_ticket` -> Jira/Zendesk node
- `route == search_docs` -> vector search/API node

---

## 6) Example: robust OpenAI call (Node.js microservice tool)

If you want production reliability, many teams put LLM calls behind a small service and call it from n8n via HTTP.

```ts
import express from 'express';
import OpenAI from 'openai';
import pRetry from 'p-retry';

const app = express();
app.use(express.json({ limit: '1mb' }));

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });
const model = process.env.OPENAI_MODEL || 'gpt-4.1-mini';

app.post('/generate', async (req, res) => {
  const { system, user, requestId } = req.body ?? {};
  if (!user) return res.status(400).json({ error: 'Missing user input' });

  try {
    const response = await pRetry(
      async () => {
        return client.responses.create({
          model,
          input: [
            { role: 'system', content: system || 'You are a reliable assistant.' },
            { role: 'user', content: user },
          ],
          temperature: 0.2,
          max_output_tokens: 500,
        });
      },
      {
        retries: Number(process.env.MAX_RETRIES || 3),
        minTimeout: 500,
        maxTimeout: 4000,
      }
    );

    res.json({
      requestId,
      model,
      output: response.output_text,
      id: response.id,
    });
  } catch (err: any) {
    res.status(500).json({
      requestId,
      error: 'LLM generation failed',
      details: err?.message,
    });
  }
});

app.listen(3000, () => {
  console.log('Agent service listening on :3000');
});
```

Call this from n8n using an **HTTP Request** node.

---

## 7) Hardening checklist for production

- Timeouts on every external node
- Retries with exponential backoff
- Idempotency key for write actions
- Strict JSON schema validation before tool execution
- PII redaction before logging
- Role-based permissions for dangerous actions
- Circuit breaker/fallback model
- Dead-letter queue for failed runs
- Dashboards: latency, cost, token usage, error rate

---

## 8) Quick answer to your question

- Yes, I can help you design and ship n8n agents.
- The model dropdown selects provider model IDs; treat versions as configurable and test pinned IDs before production rollout.
- Use the code above as a baseline and add retries, validation, permissions, and monitoring for production readiness.
