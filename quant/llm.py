import openai
import ollama
import asyncio
from openai import AsyncOpenAI
from abc import ABC, abstractmethod
from config import OpenAI_CONFIG, OLLAMA_CONFIG

class LLMClient(ABC):
    def __init__(self, temperature:float = 0):
        self.temperature = temperature

    @abstractmethod
    def chat(
            self, 
            prompt:str,
            max_tokens: int = 8192,
            temperature: float = None,
            top_p: float = 0,
        ) -> str: ...

    @abstractmethod
    async def achat(
            self,
            prompt:str,
            max_tokens: int = 8192,
            temperature: float = None,
            top_p: float = 0,
        ) -> str: ...

class OllamaClient(LLMClient):
    def __init__(
            self,
            model:str=None,
            base_url:str=None,
            temperature:float=0,
        ):
        super().__init__(temperature)
        self.model = model or OLLAMA_CONFIG["model"]
        self.base_url = base_url or OLLAMA_CONFIG["base_url"]

    def chat(
            self, 
            prompt:str,
            max_tokens: int = 8192,
            temperature: float = None,
            top_p: float = 0,
        ) -> str:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                options={
                    "temperature": self.temperature,        # 控制随机性
                    "seed": 42,                # 固定随机种子（复现结果）
                }
            )
            return response.message.content.strip()
        except Exception as e:
            raise RuntimeError(f"Ollama chat failed: {e}") from e
        
    async def achat(
            self,
            prompt:str,
            max_tokens: int = 8192,
            temperature: float = None,
            top_p: float = 0,
        ) -> str:
        try:
            response = await ollama.AsyncClient().chat(
                model=self.model,
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                options={
                    "temperature": self.temperature,
                    "seed": 42,
                }
            )
            return response.message.content.strip()
        except Exception as e:
            raise RuntimeError(f"Ollama chat failed: {e}") from e
        
class OpenAIClient(LLMClient):
    def __init__(
            self, 
            model:str=None, 
            api_key:str=None,
            base_url:str=None,
            temperature:float=0,
            default_headers:dict=None,
        ):
        super().__init__(temperature)
        self.model = model or OpenAI_CONFIG["model"]
        openai.api_key = api_key or OpenAI_CONFIG["api_key"]
        openai.base_url = base_url or OpenAI_CONFIG["base_url"]
        openai.default_headers = default_headers or {"x-foo": "true"}
        self.async_client = AsyncOpenAI(
            api_key=api_key or OpenAI_CONFIG["api_key"], 
            base_url=base_url or OpenAI_CONFIG["base_url"]
        )

    def chat(
            self, 
            prompt:str,
            max_tokens: int = 8192,
            temperature: float = None,
            top_p: float = 0,
        ) -> str:
        try:
            completion = openai.chat.completions.create(
                model=self.model,
                temperature=temperature or self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI chat failed: {e}") from e

    async def achat(
        self,
        prompt:str,
        max_tokens: int = 8192,
        temperature: float = None,
        top_p: float = 0,
    ) -> str:
        """异步请求（asyncio 并发友好）"""
        try:
            completion = await self.async_client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI async chat failed: {e}") from e

if __name__=="__main__":
    async def main():
        client = OpenAIClient(temperature=0.7)
        client = OllamaClient(temperature=0.7)
        prompts = [
            "写一个快速排序的 Python 代码",
            "写一个冒泡排序的 Python 代码",
            "写一个二分查找的 Python 代码"
        ]

        tasks = [client.achat(p) for p in prompts]
        results = await asyncio.gather(*tasks)

        for r in results:
            print(r)

    asyncio.run(main())
