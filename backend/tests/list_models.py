"""List available models on the Bedrock mantle endpoint."""
import asyncio
from openai import AsyncOpenAI
from backend.config import get_settings


async def main():
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)
    models = await client.models.list()
    for m in models.data:
        print(m.id)


asyncio.run(main())
