# M2 entries for the root .env.example (M3 owns that file; paste these in)
LLM_PROVIDER=gemini            # gemini | openai | fake (fake = regex stand-in for offline demos/tests)
LLM_MODEL=                     # model name for the chosen provider; never hard-coded in code
GEMINI_API_KEY=
OPENAI_API_KEY=
OFFLINE=0                      # 1 = CPSC connector reads fixtures/ instead of the live API
LLM_CACHE=1                    # 0 disables the runs/llm_cache/ disk cache
LLM_CACHE_DIR=runs/llm_cache
LLM_MAX_RETRIES=5
FIXTURES_DIR=fixtures
