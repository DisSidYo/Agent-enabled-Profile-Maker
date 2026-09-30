# harness — step 0: walking skeleton

Proves the plumbing before any agent logic exists: one call, through the
gateway, logged as a trace. Nothing else.

## What's here

```
harness/
  docker-compose.yml     # runs the LiteLLM gateway
  litellm/config.yaml    # two models registered: "primary" (Claude) and
                          # "fallback" (Gemini), + Langfuse logging turned on
  .env.example            # copy to .env and fill in real keys
  scripts/test_call.py    # the one call that proves everything works
```

## Run it

1. Get a free Langfuse cloud project at https://cloud.langfuse.com (takes
   two minutes, no self-hosting needed for now) and grab its public/secret
   keys.

2. `cp .env.example .env` and fill in:
   - `ANTHROPIC_API_KEY` — your Claude key
   - `GOOGLE_API_KEY` — for the fallback model (skip if you don't want a
     fallback yet — just leave the fallback block in config.yaml unused)
   - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` — from the Langfuse project

3. Start the gateway:
   ```
   docker compose up -d
   ```

4. Run the sanity check:
   ```
   pip install -r requirements.txt
   python scripts/test_call.py
   ```

5. You should see `harness step 0 works.` printed, and within a few
   seconds a trace called `step0_sanity_check` in your Langfuse dashboard
   showing the full request/response, latency, and token cost.

## When this is green

That's the whole bar for step 0 — don't build anything else until both of
those things happen reliably. Once they do, step 1 is turning `test_call.py`
into an actual plan → act → observe loop with a first tool (reading a repo
diff), still logged through the same gateway so every step of the loop
shows up as a nested span in the same trace.
