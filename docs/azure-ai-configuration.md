# Azure AI Configuration Guide

**Last Updated**: October 14, 2025

This guide explains how to configure **Azure OpenAI** and **Azure AI Foundry** models in NaLaMap, including support for embeddings and multiple model deployments.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Azure OpenAI Setup](#azure-openai-setup)
3. [Azure AI Foundry Models](#azure-ai-foundry-models)
4. [Azure Embeddings Configuration](#azure-embeddings-configuration)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Configuration Examples](#configuration-examples)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

NaLaMap supports two Azure AI configuration modes:

### 1. **Single Deployment (Legacy)**
- Simple configuration for one Azure OpenAI deployment
- Uses `AZURE_OPENAI_DEPLOYMENT` environment variable
- Backward compatible with existing setups

### 2. **Multi-Model Configuration (Recommended)**
- Configure multiple Azure OpenAI and Azure AI Foundry models
- Uses `AZURE_MODELS_CONFIG` JSON array
- Supports custom pricing, capabilities, and context windows
- Enables Azure AI Foundry models: Meta Llama, DeepSeek, Mistral, etc.

---

## 🚀 Azure OpenAI Setup

### Prerequisites

1. **Azure OpenAI Resource**
   - Create an Azure OpenAI resource in Azure Portal
   - Deploy one or more models (e.g., GPT-4o, GPT-4, GPT-3.5)
   - Note your endpoint URL and API key

2. **API Credentials**
   - `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint
   - `AZURE_OPENAI_API_KEY`: Your API key
   - `AZURE_OPENAI_API_VERSION`: API version (default: `2024-02-01`)

### Single Deployment Configuration

For a simple setup with one model:

```bash
# Required
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Optional
AZURE_OPENAI_API_VERSION=2024-02-01
```

---

## 🌐 Azure AI Foundry Models

Azure AI Foundry provides access to third-party models from Meta, Mistral, DeepSeek, and others. Use the multi-model configuration to access these.

### Supported Model Providers

- **Meta**: Llama 3.2, Llama 3.1, Llama 3
- **Mistral AI**: Mistral Large, Mistral Small, Mistral NeMo
- **Cohere**: Command R, Command R+
- **DeepSeek**: DeepSeek Coder, DeepSeek Chat
- **Azure OpenAI**: GPT-4o, GPT-4, GPT-3.5-turbo

### Multi-Model Configuration

Use `AZURE_MODELS_CONFIG` to define multiple models as a **JSON string**:

```bash
AZURE_MODELS_CONFIG='[
  {
    "deployment": "gpt-4o",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 5.00,
    "output_cost": 15.00,
    "cache_cost": 1.25,
    "description": "GPT-4o - Multimodal flagship model",
    "supports_tools": true,
    "supports_vision": true,
    "parallel_tools": true,
    "tool_quality": "excellent",
    "reasoning": "expert"
  },
  {
    "deployment": "llama-3-2-90b",
    "model_name": "meta-llama-3.2-90b-instruct",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 0.80,
    "output_cost": 0.80,
    "description": "Meta Llama 3.2 90B via Azure AI Foundry",
    "supports_tools": true,
    "supports_vision": false,
    "parallel_tools": true,
    "tool_quality": "good",
    "reasoning": "advanced"
  },
  {
    "deployment": "deepseek-coder",
    "model_name": "deepseek-coder-v2",
    "max_tokens": 8192,
    "context_window": 128000,
    "input_cost": 0.14,
    "output_cost": 0.28,
    "description": "DeepSeek Coder V2 - Ultra-low cost coding model",
    "supports_tools": true,
    "supports_vision": false,
    "parallel_tools": false,
    "tool_quality": "basic",
    "reasoning": "intermediate"
  }
]'
```

> ⚠️ **Important for Terraform/IaC**: When using Terraform `.tfvars` files, you **cannot** use `jsonencode()` function. Instead, provide the JSON string directly or use a `.tf` file with locals/variables.

### Model Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deployment` | string | ✅ Yes | Azure deployment name |
| `model_name` | string | ✅ Yes | Model identifier for frontend |
| `max_tokens` | number | No | Maximum output tokens (default: 4096) |
| `context_window` | number | No | Context window size (default: 128000) |
| `input_cost` | number | No | Cost per 1M input tokens (USD) |
| `output_cost` | number | No | Cost per 1M output tokens (USD) |
| `cache_cost` | number | No | Cache cost per 1M tokens (USD) |
| `description` | string | No | Model description |
| `supports_tools` | boolean | No | Function calling support (default: true) |
| `supports_vision` | boolean | No | Vision/image support (default: false) |
| `parallel_tools` | boolean | No | Parallel tool calls (default: true) |
| `tool_quality` | string | No | Tool quality: "none", "basic", "good", "excellent" (default: "good") |
| `reasoning` | string | No | Reasoning capability: "basic", "intermediate", "advanced", "expert" (default: "advanced") |

---

## 🔍 Azure Embeddings Configuration

NaLaMap supports Azure OpenAI embeddings for semantic search in the GeoServer vector store.

### Configuration Methods

#### Method 1: Using EMBEDDING_PROVIDER (Recommended)

```bash
# Azure AI endpoint and credentials
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_API_VERSION=2024-02-01

# Embedding configuration
EMBEDDING_PROVIDER=azure
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_EMBEDDING_MODEL=text-embedding-3-small
```

#### Method 2: Using USE_AZURE_EMBEDDINGS (Legacy)

```bash
USE_AZURE_EMBEDDINGS=true
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_EMBEDDING_MODEL=text-embedding-3-small
```

### Available Embedding Models

Azure OpenAI supports these embedding models:

- `text-embedding-3-small`: 1536 dimensions, cost-effective
- `text-embedding-3-large`: 3072 dimensions, highest quality
- `text-embedding-ada-002`: 1536 dimensions, legacy model

### Embedding Priority Order

1. **Custom Factory**: `NALAMAP_GEOSERVER_EMBEDDING_FACTORY`
2. **Azure AI**: `EMBEDDING_PROVIDER=azure` or `USE_AZURE_EMBEDDINGS=true`
3. **OpenAI**: `EMBEDDING_PROVIDER=openai` or `USE_OPENAI_EMBEDDINGS=true`
4. **Hashing** (default): Lightweight, no dependencies

---

## 📚 Environment Variables Reference

### Core Azure Settings

```bash
# Azure OpenAI endpoint (required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# API key (required)
AZURE_OPENAI_API_KEY=your-api-key-here

# API version (optional, default: 2024-02-01)
AZURE_OPENAI_API_VERSION=2024-02-01
```

### Chat Models

```bash
# Single deployment (legacy)
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Multi-model configuration (JSON array)
AZURE_MODELS_CONFIG='[...]'
```

### Embeddings

```bash
# Embedding provider
EMBEDDING_PROVIDER=azure  # Options: hashing, openai, azure

# Azure-specific
USE_AZURE_EMBEDDINGS=true  # Legacy alternative
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_EMBEDDING_MODEL=text-embedding-3-small
```

---

## 💡 Configuration Examples

### Example 1: Single GPT-4o Deployment

```bash
# .env
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-production
AZURE_OPENAI_API_VERSION=2024-02-01

# Embeddings
EMBEDDING_PROVIDER=azure
AZURE_EMBEDDING_DEPLOYMENT=embeddings-prod
AZURE_EMBEDDING_MODEL=text-embedding-3-small
```

### Example 2: Multiple Azure OpenAI Models

```bash
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...

AZURE_MODELS_CONFIG='[
  {
    "deployment": "gpt-4o-prod",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 5.00,
    "output_cost": 15.00,
    "supports_tools": true,
    "supports_vision": true,
    "tool_quality": "excellent",
    "reasoning": "expert"
  },
  {
    "deployment": "gpt-35-turbo",
    "model_name": "gpt-3.5-turbo",
    "max_tokens": 4096,
    "context_window": 16385,
    "input_cost": 0.50,
    "output_cost": 1.50,
    "supports_tools": true,
    "tool_quality": "good",
    "reasoning": "advanced"
  }
]'
```

### Example 3: Azure AI Foundry with Meta Llama

```bash
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...

AZURE_MODELS_CONFIG='[
  {
    "deployment": "llama-3-2-90b-instruct",
    "model_name": "meta-llama-3.2-90b",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 0.80,
    "output_cost": 0.80,
    "description": "Meta Llama 3.2 90B Instruct",
    "supports_tools": true,
    "parallel_tools": true,
    "tool_quality": "good",
    "reasoning": "advanced"
  },
  {
    "deployment": "llama-3-2-11b-vision",
    "model_name": "meta-llama-3.2-11b-vision",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 0.35,
    "output_cost": 0.35,
    "description": "Meta Llama 3.2 11B Vision",
    "supports_tools": false,
    "supports_vision": true,
    "tool_quality": "none",
    "reasoning": "intermediate"
  }
]'
```

### Example 4: Mixed Azure OpenAI and AI Foundry

```bash
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...

AZURE_MODELS_CONFIG='[
  {
    "deployment": "gpt-4o",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "input_cost": 5.00,
    "output_cost": 15.00,
    "supports_vision": true,
    "tool_quality": "excellent"
  },
  {
    "deployment": "mistral-large",
    "model_name": "mistral-large-2407",
    "max_tokens": 8000,
    "input_cost": 2.00,
    "output_cost": 6.00,
    "tool_quality": "excellent"
  },
  {
    "deployment": "deepseek-chat",
    "model_name": "deepseek-chat",
    "max_tokens": 4096,
    "input_cost": 0.14,
    "output_cost": 0.28,
    "tool_quality": "basic"
  }
]'
```

---

## 🏗️ Terraform / Infrastructure as Code

### Issue: Function Calls Not Allowed in .tfvars

Terraform `.tfvars` files **do not support function calls** like `jsonencode()`. You'll get this error:

```
Error: Function calls not allowed
  on vars/myfile.tfvars line XX:
  XX: azure_models_config = jsonencode([...])

Functions may not be called here.
```

### Solution 1: Use Pre-Encoded JSON String (Recommended)

In your `.tfvars` file, provide the JSON as a **string**:

```hcl
# vars/bmz_development.tfvars
azure_models_config = "[{\"deployment\":\"gpt-4o\",\"model_name\":\"gpt-4o\",\"max_tokens\":4096,\"context_window\":128000,\"input_cost\":5.00,\"output_cost\":15.00,\"supports_tools\":true,\"supports_vision\":true,\"tool_quality\":\"excellent\",\"reasoning\":\"expert\"},{\"deployment\":\"llama-3-3-70b\",\"model_name\":\"meta-llama-3.3-70b-instruct\",\"max_tokens\":8192,\"input_cost\":0.27,\"output_cost\":0.27,\"supports_tools\":true,\"tool_quality\":\"excellent\",\"reasoning\":\"expert\"}]"
```

### Solution 2: Use locals in .tf File

Define the JSON structure in a `.tf` file using `locals` and `jsonencode()`:

```hcl
# variables.tf
variable "azure_models_config" {
  type        = string
  description = "Azure models configuration JSON"
}

# main.tf or locals.tf
locals {
  azure_models = [
    {
      deployment       = "gpt-4o"
      model_name       = "gpt-4o"
      max_tokens       = 4096
      context_window   = 128000
      input_cost       = 5.00
      output_cost      = 15.00
      supports_tools   = true
      supports_vision  = true
      tool_quality     = "excellent"
      reasoning        = "expert"
    },
    {
      deployment       = "llama-3-3-70b"
      model_name       = "meta-llama-3.3-70b-instruct"
      max_tokens       = 8192
      input_cost       = 0.27
      output_cost      = 0.27
      supports_tools   = true
      tool_quality     = "excellent"
      reasoning        = "expert"
    }
  ]
  
  azure_models_json = jsonencode(local.azure_models)
}

# Use in your resource
resource "azurerm_container_app" "backend" {
  # ...
  
  template {
    container {
      env {
        name  = "AZURE_MODELS_CONFIG"
        value = local.azure_models_json
      }
    }
  }
}
```

### Solution 3: Use External JSON File

Store configuration in a separate JSON file:

```json
// config/azure_models.json
[
  {
    "deployment": "gpt-4o",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 5.00,
    "output_cost": 15.00,
    "supports_tools": true,
    "supports_vision": true,
    "tool_quality": "excellent",
    "reasoning": "expert"
  }
]
```

Then load it in your Terraform:

```hcl
# main.tf
locals {
  azure_models_json = file("${path.module}/config/azure_models.json")
}

resource "azurerm_container_app" "backend" {
  # ...
  template {
    container {
      env {
        name  = "AZURE_MODELS_CONFIG"
        value = local.azure_models_json
      }
    }
  }
}
```

### Solution 4: Use Terraform templatefile

For complex configurations with variables:

```hcl
# templates/azure_models.json.tpl
[
  {
    "deployment": "${gpt4o_deployment}",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "input_cost": ${gpt4o_input_cost}
  }
]
```

```hcl
# main.tf
locals {
  azure_models_json = templatefile("${path.module}/templates/azure_models.json.tpl", {
    gpt4o_deployment   = var.gpt4o_deployment_name
    gpt4o_input_cost   = var.gpt4o_pricing.input
  })
}
```

### Quick Fix for Your Current Setup

Replace this in your `.tfvars`:

```hcl
# ❌ This doesn't work in .tfvars
azure_models_config = jsonencode([
  {
    deployment = "gpt-4o"
    # ...
  }
])
```

With this:

```hcl
# ✅ This works in .tfvars
azure_models_config = "[{\"deployment\":\"gpt-4o\",\"model_name\":\"gpt-4o\",\"max_tokens\":4096,\"input_cost\":5.0}]"
```

Or move the configuration to a `.tf` file as shown in **Solution 2**.

---

## 🐛 Troubleshooting

### Issue: Models Not Appearing

**Solution**:
1. Check `AZURE_MODELS_CONFIG` is valid JSON
2. Verify all required fields are present
3. Check backend logs for parsing errors:
   ```bash
   docker logs nalamap-backend 2>&1 | grep -i azure
   ```

### Issue: Authentication Errors

**Solution**:
1. Verify `AZURE_OPENAI_ENDPOINT` includes `https://` and trailing `/`
2. Check API key is correct and not expired
3. Ensure API version is supported: `2024-02-01` is recommended

### Issue: Deployment Not Found

**Solution**:
1. Verify deployment name in Azure Portal matches config
2. Check deployment is in "Succeeded" state
3. Ensure model is deployed in the same region as your endpoint

### Issue: Embeddings Not Working

**Solution**:
1. Verify embedding deployment exists in Azure
2. Check `EMBEDDING_PROVIDER=azure` is set
3. Ensure `AZURE_EMBEDDING_DEPLOYMENT` matches Azure deployment name

### Issue: Tool Calling Failures

**Solution**:
1. Ensure `supports_tools: true` in model config
2. Some Azure AI Foundry models have limited tool support
3. Check model supports function calling in Azure documentation

---

## 📖 Additional Resources

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Terraform Configuration Guide](./terraform-azure-models-config.md) - **Fix for `jsonencode()` error**
- [NaLaMap Model Selection Guide](./phase-1-model-selection-implementation.md)
- [OpenAI Embeddings Guide](./openai-embeddings.md)

---

## 🔄 Migration from Single to Multi-Model

If you're using the legacy single deployment configuration:

### Before (Legacy)
```bash
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### After (Multi-Model)
```bash
AZURE_OPENAI_ENDPOINT=https://mycompany.openai.azure.com/
AZURE_OPENAI_API_KEY=sk-abc123...

AZURE_MODELS_CONFIG='[
  {
    "deployment": "gpt-4o",
    "model_name": "gpt-4o",
    "max_tokens": 4096,
    "context_window": 128000,
    "input_cost": 5.00,
    "output_cost": 15.00,
    "cache_cost": 1.25,
    "supports_tools": true,
    "supports_vision": true,
    "tool_quality": "excellent",
    "reasoning": "expert"
  }
]'
```

**Note**: The single deployment configuration still works for backward compatibility.

---

**Last Updated**: October 14, 2025  
**Maintainers**: NaLaMap Development Team  
**Contact**: [info@nalamap.org](mailto:info@nalamap.org)
