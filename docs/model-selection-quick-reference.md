# Model Selection Quick Reference

**Last Updated**: October 12, 2025

---

## 🎯 Choose a Model Based on Your Needs

### Need Long Context? (Large datasets, long conversations)
- **Gemini 1.5 Pro**: 1M tokens, excellent tools, expert reasoning ($1.25/M input)
- **Gemini 1.5 Flash**: 1M tokens, good tools, advanced reasoning ($0.075/M input)
- **Gemini 2.0 Flash Exp**: 1M tokens, excellent tools, expert reasoning (**FREE**)
- GPT-5 series: 200K tokens, excellent tools, expert reasoning ($0.25-15/M input)

### Need Best Reasoning? (Complex spatial analysis)
**"Expert" level models**:
- GPT-4o: 128K context, excellent tools ($2.50/M input)
- GPT-5: 200K context, excellent tools ($1.25/M input)
- Gemini 1.5 Pro: 1M context, excellent tools ($1.25/M input)
- Gemini 2.0 Flash Exp: 1M context, excellent tools (**FREE**)
- Mistral Large: 128K context, excellent tools ($2.00/M input)
- DeepSeek Reasoner: 64K context, excellent tools ($0.55/M input)

### Need Excellent Tool Calling? (Reliable function execution)
**"Excellent" quality models**:
- All GPT-5 series (except nano)
- GPT-4.1, GPT-4o
- Gemini 1.5 Pro, Gemini 2.0 Flash Exp
- Mistral Large
- DeepSeek Reasoner

### Need Best Value? (Cost optimization)
- **Gemini 2.0 Flash Exp**: FREE, expert reasoning, excellent tools, 1M context
- DeepSeek Chat: $0.14/M input, good tools, intermediate reasoning
- GPT-5 Nano: $0.05/M input, good tools, intermediate reasoning
- Gemini 1.5 Flash: $0.075/M input, good tools, advanced reasoning

### Need Vision Support? (Image analysis)
- GPT-4o, GPT-4o-mini, GPT-5 Mini
- Gemini 1.5 Pro/Flash, Gemini 2.0 Flash Exp
- Most GPT-4.1 series

### Need Parallel Tool Calls? (Performance optimization)
**26 out of 29 models support this**, including:
- All OpenAI models
- All Google models except Gemini 1.0 Pro
- All Mistral models except open-mistral-7b
- All DeepSeek models

---

## 📊 Model Tiers at a Glance

### Premium Tier (Expert reasoning, Excellent tools)
| Model | Context | Cost/M | Best For |
|-------|---------|--------|----------|
| GPT-4o | 128K | $2.50 | Production quality, vision |
| GPT-5 | 200K | $1.25 | Latest generation |
| Gemini 1.5 Pro | 1M | $1.25 | Long context needs |
| Gemini 2.0 Flash Exp | 1M | **FREE** | Development, testing |
| Mistral Large | 128K | $2.00 | Alternative to GPT-4o |

### Balanced Tier (Advanced reasoning, Good tools)
| Model | Context | Cost/M | Best For |
|-------|---------|--------|----------|
| GPT-4o-mini | 128K | $0.15 | Production, cost-effective |
| GPT-5 Mini | 200K | $0.25 | Balanced performance |
| Gemini 1.5 Flash | 1M | $0.075 | Long context, low cost |
| DeepSeek Coder | 32K | $0.14 | Code-heavy tasks |

### Budget Tier (Intermediate reasoning, Good tools)
| Model | Context | Cost/M | Best For |
|-------|---------|--------|----------|
| DeepSeek Chat | 32K | $0.14 | High volume, simple queries |
| GPT-5 Nano | 200K | $0.05 | Ultra-low cost |
| Mistral Small | 32K | $0.20 | European data residency |

---

## 🔍 Understanding the Metadata

### Context Window
- **What**: Maximum total tokens (input + output) the model can process
- **Why it matters**: Long conversations + large GeoJSON + tool schemas need space
- **Range**: 32K (basic) to 1M (Gemini)
- **Rule of thumb**: 128K+ is comfortable for most geospatial work

### Tool Calling Quality
- **"Excellent"**: Rarely makes mistakes, handles complex schemas well
- **"Good"**: Reliable for most use cases, occasional errors on edge cases
- **"Basic"**: Works for simple tools, struggles with complex parameters
- **"None"**: Does not support function calling

### Reasoning Capability
- **"Expert"**: Handles complex multi-step spatial reasoning, self-correction
- **"Advanced"**: Good for most geospatial queries, reliable planning
- **"Intermediate"**: Suitable for straightforward tasks, limited planning
- **"Basic"**: Simple queries only, minimal reasoning depth

### Parallel Tool Calls
- **True**: Can call multiple tools in one response (e.g., "find hospitals AND schools")
- **False**: Calls tools sequentially (slower but sometimes more predictable)

---

## 🎯 Use Case Recommendations

### "Find hospitals near rivers in protected areas"
**Recommended**: GPT-4o, Gemini 1.5 Pro, or Mistral Large
- **Why**: Multi-step reasoning (expert/advanced), excellent tool calling
- **Budget option**: Gemini 2.0 Flash Exp (FREE) or DeepSeek Reasoner ($0.55/M)

### "Load this 10MB GeoJSON and analyze biodiversity"
**Recommended**: Gemini 1.5 Pro/Flash (1M context window)
- **Why**: Can fit entire dataset in context, no chunking needed
- **Alternative**: GPT-5 series (200K context) if dataset compresses well

### "Show me hospitals in Berlin"
**Recommended**: DeepSeek Chat, GPT-4o-mini, or GPT-5 Nano
- **Why**: Simple query, intermediate reasoning sufficient, low cost
- **Note**: Any model with "good" or better tool calling will work

### High-volume production API (1000s of requests/day)
**Recommended**: DeepSeek Chat or Gemini 1.5 Flash
- **Why**: Ultra-low cost ($0.14/M and $0.075/M respectively)
- **Check**: Rate limits and latency requirements

### Development/Testing (don't want to pay)
**Recommended**: Gemini 2.0 Flash Exp
- **Why**: FREE during experimental period
- **Capabilities**: Expert reasoning, excellent tools, 1M context
- **Note**: May have rate limits or stability issues

---

## ⚡ Performance Tips

1. **Use parallel tool calls when possible**: 89.7% of models support it
2. **Match context window to needs**: Don't pay for 1M tokens if you only need 32K
3. **Consider token counting**: Input + output + tools must fit in context window
4. **Cache when possible**: Some models offer cache cost discounts
5. **Test with cheaper models first**: Validate approach before using premium models

---

## 🚨 Common Mistakes to Avoid

1. ❌ **Using "basic" tool calling models for complex operations**
   - Use "good" or "excellent" quality for production

2. ❌ **Choosing models with insufficient context windows**
   - Large GeoJSON files need 128K+ context
   - Multi-turn conversations accumulate quickly

3. ❌ **Ignoring reasoning capability for complex queries**
   - "Intermediate" models struggle with multi-step spatial reasoning
   - Use "advanced" or "expert" for complex analysis

4. ❌ **Not considering free alternatives**
   - Gemini 2.0 Flash Exp is FREE and has expert-level capabilities

5. ❌ **Overlooking DeepSeek for high volume**
   - At $0.14/M, it's 18x cheaper than GPT-4o for simple queries

---

## 📚 More Information

- **Full Analysis**: See `docs/llm-model-selection-enhancement-analysis.md`
- **Implementation Details**: See `docs/phase-1-model-selection-implementation.md`
- **API Documentation**: Run backend and visit `http://localhost:8000/docs`
- **Model Metadata**: GET `/api/settings/options` for live data

---

**TIP**: When in doubt, start with **Gemini 2.0 Flash Exp** (free, expert capabilities) for testing, then optimize for cost/performance based on actual usage patterns.
