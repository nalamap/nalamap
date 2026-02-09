# AI Providers in NaLaMap

NaLaMap supports multiple AI providers for map generation and data analysis.

## Supported Providers

### 1. OpenAI
- **Key Environment Variable:** `OPENAI_API_KEY`
- **Featured Models:**
  - `gpt-5.5` (Expert reasoning)
  - `gpt-5.5-mini` (Fast and capable)
  - `gpt-5`
  - `o3-mini` (STEM/Coding optimized)

### 2. Anthropic
- **Key Environment Variable:** `ANTHROPIC_API_KEY`
- **Featured Models:**
  - `claude-4-5-sonnet-20260207` (Best balance)
  - `claude-4-opus-20260207` (Most powerful)
  - `claude-4-5-haiku-20260207` (Fastest)

### 3. Google Gemini
- **Key Environment Variable:** `GOOGLE_API_KEY`
- **Featured Models:**
  - `gemini-2.0-pro-latest`
  - `gemini-2.0-flash`
  - `gemini-1.5-pro-latest`

### 4. Mistral AI
- **Key Environment Variable:** `MISTRAL_API_KEY`
- **Featured Models:**
  - `pixtral-large-latest` (Multimodal)
  - `mistral-large-latest`

### 5. DeepSeek
- **Key Environment Variable:** `DEEPSEEK_API_KEY`
- **Featured Models:**
  - `deepseek-v3` (Latest generation)
  - `deepseek-reasoner`

## Configuration

To change the default provider, set the `LLM_PROVIDER` environment variable:
- `LLM_PROVIDER=anthropic`
- `LLM_PROVIDER=openai` (Default)
- `LLM_PROVIDER=google`
- `LLM_PROVIDER=mistral`
- `LLM_PROVIDER=deepseek`

You can also specify a default model via `OPENAI_MODEL`, `ANTHROPIC_MODEL`, etc.
