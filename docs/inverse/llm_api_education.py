#!/usr/bin/env python3
"""
LLM API Integration Education Script
=====================================

This script explains different approaches to calling LLM APIs:
1. Direct API calls (what we implemented)
2. LiteLLM (unified interface)
3. Portkey (proxy/gateway)
4. MiniSweAgent (agent framework)

Run this script to see examples and comparisons.
"""

# =============================================================================
# SECTION 1: DIRECT API CALLS (Our Current Approach)
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  APPROACH 1: DIRECT API CALLS   
╚══════════════════════════════════════════════════════════════════════════════╝

How it works:
- Import each provider's SDK directly (openai, anthropic)
- Write separate code paths for each provider
- Handle authentication, retries, errors ourselves

Our code in code_extractor.py:
""")

DIRECT_APPROACH_CODE = '''
# We have separate methods for each provider:

def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
    import openai
    client = openai.OpenAI(api_key=self.llm_config.api_key)
    response = client.chat.completions.create(
        model=self.llm_config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content

def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=self.llm_config.api_key)
    response = client.messages.create(
        model=self.llm_config.model,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text

def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
    # Route based on model name
    if "claude" in self.llm_config.model.lower():
        return self._call_anthropic(system_prompt, user_prompt)
    else:
        return self._call_openai(system_prompt, user_prompt)
'''
print(DIRECT_APPROACH_CODE)

print("""
✅ PROS:
   - Full control over API calls
   - No extra dependencies
   - Direct access to provider-specific features
   - Easier to debug (no abstraction layers)

❌ CONS:
   - Must maintain separate code for each provider
   - Handle retries, rate limits, errors manually
   - Adding new providers requires code changes
   - No built-in caching, logging, or observability
""")

# =============================================================================
# SECTION 2: LITELLM (Unified Interface)
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  APPROACH 2: LITELLM (Unified API Interface)                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

What is LiteLLM?
- A Python library that provides ONE interface for 100+ LLMs
- pip install litellm
- Same code works with OpenAI, Anthropic, Cohere, HuggingFace, local models, etc.

How it works:
""")

LITELLM_CODE = '''
import litellm

# ONE function works for ALL providers!
# Just change the model string

# OpenAI
response = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Anthropic (just change model name!)
response = litellm.completion(
    model="claude-3-sonnet-20240229",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Azure OpenAI
response = litellm.completion(
    model="azure/my-deployment",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Local model via Ollama
response = litellm.completion(
    model="ollama/llama2",
    messages=[{"role": "user", "content": "Hello!"}]
)

# All return the same response format!
print(response.choices[0].message.content)
'''
print(LITELLM_CODE)

print("""
Key Features:
- Automatic provider detection from model name
- Built-in retries with exponential backoff
- Fallbacks: try OpenAI, if fails try Anthropic
- Caching support
- Cost tracking
- Streaming support

Environment Variables (LiteLLM auto-detects):
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- AZURE_API_KEY
- etc.

✅ PROS:
   - Write once, use any provider
   - Built-in retries, fallbacks, caching
   - Easy to switch providers (just change model string)
   - Active development, supports latest models
   - Cost tracking built-in

❌ CONS:
   - Extra dependency
   - Abstraction may hide provider-specific features
   - Must trust the library to stay updated
   - Slight overhead vs direct calls
""")

# =============================================================================
# SECTION 3: PORTKEY (Gateway/Proxy Service)
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  APPROACH 3: PORTKEY (AI Gateway / Proxy Service)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

What is Portkey?
- A HOSTED SERVICE that sits between your code and LLM providers
- All your API calls go through Portkey's servers
- Portkey routes them to the right provider

Architecture:
                                              ┌─────────────┐
                                         ┌───►│   OpenAI    │
    ┌──────────┐      ┌─────────────┐    │    └─────────────┘
    │ Your App │─────►│   Portkey   │────┤    ┌─────────────┐
    └──────────┘      │   Gateway   │    ├───►│  Anthropic  │
                      └─────────────┘    │    └─────────────┘
                                         │    ┌─────────────┐
                                         └───►│   Azure     │
                                              └─────────────┘

How CodeClash uses it (from their config):
""")

PORTKEY_CODE = '''
# In CodeClash config.yaml:
{
    "model": {
        "model_class": "portkey",
        "config": {
            "model_name": "@openai/gpt-5-mini"  # Portkey routing syntax
        }
    }
}

# Using Portkey with litellm:
import litellm

response = litellm.completion(
    model="portkey/gpt-4",  # Route through Portkey
    messages=[{"role": "user", "content": "Hello!"}],
    api_base="https://api.portkey.ai/v1",
    api_key="your-portkey-api-key",
    headers={
        "x-portkey-api-key": "your-portkey-key",
        "x-portkey-provider": "openai"
    }
)

# Or using Portkey's SDK directly:
from portkey_ai import Portkey

client = Portkey(api_key="PORTKEY_API_KEY")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    # Portkey adds extra features via headers:
    metadata={"user_id": "user123", "session_id": "abc"}
)
'''
print(PORTKEY_CODE)

print("""
Key Features of Portkey:
1. UNIFIED BILLING - One API key, routes to any provider
2. OBSERVABILITY - Logs all requests, tracks costs, latency
3. CACHING - Cache responses to save money
4. FALLBACKS - Auto-retry with different providers
5. LOAD BALANCING - Distribute across multiple API keys
6. GUARDRAILS - Content filtering, rate limiting

Why CodeClash uses Portkey:
- Team can share ONE Portkey API key
- Portkey manages all the underlying provider keys
- Built-in monitoring and cost tracking
- Easy to switch providers without code changes

✅ PROS:
   - Centralized billing and key management
   - Built-in observability (logs, metrics, traces)
   - Smart routing, caching, fallbacks
   - No code changes to switch providers
   - Great for teams

❌ CONS:
   - ADDS LATENCY (extra network hop through Portkey servers)
   - COSTS MONEY (Portkey charges on top of LLM costs)
   - DEPENDENCY on external service
   - Your prompts go through third-party servers (privacy?)
   - If Portkey is down, your app is down
""")

# =============================================================================
# SECTION 4: MINISWEAGENT (Agent Framework)
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  APPROACH 4: MINISWEAGENT (Agent Framework)                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

What is MiniSweAgent?
- A minimal framework for building LLM agents (like SWE-Agent)
- Used by CodeClash to build their code-solving agents
- Wraps LLM calls with tool use, memory, and action loops

Architecture:
    ┌─────────────────────────────────────────────────────┐
    │                    MiniSweAgent                     │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
    │  │   Models    │  │    Tools    │  │   Memory    │ │
    │  │ (LiteLLM/   │  │  (bash,     │  │  (history,  │ │
    │  │  Portkey)   │  │   edit,     │  │   context)  │ │
    │  │             │  │   search)   │  │             │ │
    │  └─────────────┘  └─────────────┘  └─────────────┘ │
    └─────────────────────────────────────────────────────┘

How CodeClash uses it:
""")

MINISWEAGENT_CODE = '''
# From CodeClash's model.py:
from minisweagent.models import get_model

class MinisweAgentModel:
    def __init__(self, config):
        self.config = config
        self.model = get_model(config=self.config["config"]["model"])
    
    def generate(self, prompt):
        # MiniSweAgent handles:
        # - LLM selection (via config)
        # - Retries
        # - Tool calling
        # - Context management
        return self.model.generate(prompt)

# The get_model() function:
# - Reads config to determine provider
# - Returns appropriate model wrapper
# - Supports: openai, anthropic, portkey, litellm, local

# Config example:
config = {
    "model": {
        "model_class": "portkey",  # or "openai", "anthropic", "litellm"
        "config": {
            "model_name": "@openai/gpt-5-mini",
            "temperature": 0.0
        }
    }
}
'''
print(MINISWEAGENT_CODE)

print("""
MiniSweAgent is NOT just about LLM calls - it's a full agent framework:
- Action loop (observe → think → act → repeat)
- Tool integration (run bash, edit files, search code)
- Memory management (keep conversation history)
- Error recovery

✅ PROS:
   - 
   - Full agent framework, not just LLM wrapperIntegrates tools, memory, actions
   - Config-driven (easy to change models)
   - Built for code-related tasks

❌ CONS:
   - Overkill if you just need LLM calls
   - Another dependency to learn
   - Framework lock-in
   - Less control over individual API calls
""")

# =============================================================================
# SECTION 5: COMPARISON TABLE
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  COMPARISON TABLE                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌────────────────┬─────────────┬─────────────┬─────────────┬─────────────────┐
│ Feature        │ Direct API  │ LiteLLM     │ Portkey     │ MiniSweAgent    │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Dependencies   │ Per-provider│ litellm     │ External    │ minisweagent    │
│                │ SDKs        │ (Python)    │ service     │ + litellm       │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Multi-provider │ ❌ Manual   │ ✅ Auto     │ ✅ Auto     │ ✅ Via config   │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Retries        │ ❌ Manual   │ ✅ Built-in │ ✅ Built-in │ ✅ Built-in     │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Fallbacks      │ ❌ Manual   │ ✅ Built-in │ ✅ Built-in │ ✅ Built-in     │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Caching        │ ❌ Manual   │ ✅ Optional │ ✅ Built-in │ ❌ Manual       │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Observability  │ ❌ Manual   │ ⚠️ Basic    │ ✅ Full     │ ⚠️ Basic        │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Cost Tracking  │ ❌ Manual   │ ✅ Built-in │ ✅ Dashboard│ ❌ Manual       │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Extra Latency  │ None        │ None        │ ~50-100ms   │ None            │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Extra Cost     │ None        │ None        │ $$$ Service │ None            │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Privacy        │ ✅ Direct   │ ✅ Direct   │ ⚠️ Via proxy│ ✅ Direct       │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Learning Curve │ Low         │ Low         │ Medium      │ High            │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Agent Features │ ❌ None     │ ❌ None     │ ❌ None     │ ✅ Full         │
└────────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘
""")

# =============================================================================
# SECTION 6: RECOMMENDATION FOR INVERSE_STRATEGY
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  RECOMMENDATION FOR INVERSE_STRATEGY                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

For our inverse_strategy project, I recommend: LITELLM

Why?
1. We need multi-provider support (OpenAI, Anthropic, local models)
2. We don't need agent features (we're doing inference, not tool use)
3. We want to avoid external service dependency (no Portkey)
4. We want built-in retries and fallbacks
5. Easy to add new providers later

Here's how to refactor our code:
""")

RECOMMENDATION_CODE = '''
# BEFORE (our current approach):
def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
    if "claude" in self.llm_config.model.lower():
        return self._call_anthropic(system_prompt, user_prompt)
    else:
        return self._call_openai(system_prompt, user_prompt)

# AFTER (with LiteLLM):
def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
    import litellm
    
    response = litellm.completion(
        model=self.llm_config.model,  # Works for ANY provider!
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=self.llm_config.max_tokens,
        temperature=self.llm_config.temperature,
    )
    return response.choices[0].message.content

# That's it! ONE method for ALL providers.
# LiteLLM auto-detects provider from model name:
# - "gpt-4" → OpenAI
# - "claude-3-sonnet" → Anthropic
# - "ollama/llama2" → Local Ollama
# - "azure/deployment" → Azure OpenAI
'''
print(RECOMMENDATION_CODE)

# =============================================================================
# SECTION 7: LIVE DEMO (if litellm is installed)
# =============================================================================

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LIVE DEMO                                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

try:
    import litellm
    print("✅ LiteLLM is installed! Version:", litellm.__version__)
    print("\nSupported providers (partial list):")
    providers = [
        "openai", "anthropic", "azure", "huggingface", "cohere",
        "replicate", "palm", "ai21", "ollama", "bedrock", "together_ai"
    ]
    for p in providers:
        print(f"  - {p}")
    
    print("\nTo test (needs API key in environment):")
    print('  litellm.completion(model="gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])')
    
except ImportError:
    print("❌ LiteLLM not installed. Install with: pip install litellm")
    print("\nTo try it:")
    print("  pip install litellm")
    print("  export OPENAI_API_KEY=your-key")
    print('  python -c "import litellm; print(litellm.completion(model=\'gpt-4o-mini\', messages=[{\'role\': \'user\', \'content\': \'Hi\'}]))"')

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  SUMMARY                                                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

1. DIRECT API (our current approach)
   → Simple, full control, but manual multi-provider support

2. LITELLM (recommended upgrade)
   → Same interface for all providers, built-in retries
   → pip install litellm

3. PORTKEY (what CodeClash uses)
   → Hosted gateway service, great observability
   → Extra cost, latency, privacy concerns

4. MINISWEAGENT (CodeClash's framework)
   → Full agent framework with tools
   → Overkill for just LLM inference

For inverse_strategy: Use LiteLLM for simplicity + flexibility.
""")
