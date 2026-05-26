#!/usr/bin/env python3
"""Example: Make a message request through Sentinel using Anthropic.

Prerequisites:
    1. Set ANTHROPIC_API_KEY in .env
    2. Run: docker compose up -d
    3. Run: python examples/hello_anthropic.py

The trace will appear in the dashboard at http://localhost:3000.
"""

from sentinel import Anthropic

client = Anthropic(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    # provider_api_key="sk-ant-..."  # or set ANTHROPIC_API_KEY in .env
)

# --- Non-streaming ---
print("=== Non-streaming ===")
response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=100,
    messages=[
        {"role": "user", "content": "What is observability? One sentence."},
    ],
)
print(f"Model: {response.model}")
print(f"Response: {response.content[0].text}")
print(f"Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
print()

# --- Streaming ---
print("=== Streaming ===")
with client.messages.stream(
    model="claude-3-5-haiku-20241022",
    max_tokens=50,
    messages=[
        {"role": "user", "content": "Write a haiku about API proxies."},
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
print("\n")

print("✅ Done! Check http://localhost:3000 for your traces.")
