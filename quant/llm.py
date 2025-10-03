import openai
from abc import ABC

class LLMClient(ABC):
    def __init__(self, temperature:float=0):
        self.temperature = temperature

    def chat(self, prompt:str) -> str:
        pass

class OpenAIClient(LLMClient):
    def __init__(self, 
            model:str="gpt-4o-mini", 
            temperature:float=0,
            api_key:str=None,
            base_url:str=None,
        ):
        super().__init__(temperature)
        self.model = model
        self.api_key = api_key if api_key is not None else "sk-p1JBAYtwircCFdGP407a6185DdA64878BaF9F1Bd731349F6"
        self.base_url = base_url if base_url is not None else "https://free.v36.cm/v1/"

    def chat(self, prompt:str) -> str:
        openai.api_key = self.api_key
        openai.base_url = self.base_url
        openai.default_headers = {"x-foo": "true"}

        completion = openai.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        return completion.choices[0].message.content
