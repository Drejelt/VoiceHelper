from openai import OpenAI

client = OpenAI(
  api_key="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"
)

completion = client.chat.completions.create(
  model="gpt-4o-mini",
  store=True,
  messages=[
    {"role": "user", "content": "write a haiku about ai"}
  ]
)

print(completion.choices[0].message);
