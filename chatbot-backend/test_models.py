import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("BASE_URL")
)

# Test chat model
response = client.chat.completions.create(
    model=os.getenv("CHAT_MODEL"),
    messages=[{"role": "user", "content": "Say hello"}]
)

print("Chat:", response.choices[0].message.content)

# Test embedding model
embeddings = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("BASE_URL"),
    model=os.getenv("EMBEDDING_MODEL")
)

vector = embeddings.embed_query("What is artificial intelligence?")

print("Embedding dimensions:", len(vector))