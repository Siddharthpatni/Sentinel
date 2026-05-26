#!/usr/bin/env python3
"""Example: Make a chat completion through Sentinel using OpenAI.

Prerequisites:
    1. Set OPENAI_API_KEY in .env
    2. Run: docker compose up -d
    3. Run: python examples/hello_openai.py

The trace will appear in the dashboard at http://localhost:3000.
"""

from sentinel import OpenAI

client = OpenAI(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    # provider_api_key="sk-..."  # or set OPENAI_API_KEY in .env
)

# --- Non-streaming ---
print("=== Non-streaming ===")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is observability in software engineering? Answer in one sentence."},
    ],
    max_tokens=100,
)
print(f"Model: {response.model}")
print(f"Response: {response.choices[0].message.content}")
print(f"Tokens: {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")
print()

# --- Streaming ---
print("=== Streaming ===")
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Write a haiku about debugging."},
    ],
    stream=True,
    max_tokens=50,
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print("\n")

print("✅ Done! Check http://localhost:3000 for your traces.")
