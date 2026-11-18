import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import OLLAMA_MODEL, OLLAMA_URL


class ModelError(RuntimeError):
    pass


class OllamaModel:
    def generate(self, prompt: str, *, json_output: bool = False) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 500},
        }
        if json_output:
            payload["format"] = "json"
        request = Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                body = json.load(response)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelError(
                f"Ollama request failed. Start Ollama and pull {OLLAMA_MODEL}: {exc}"
            ) from exc
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ModelError("Ollama returned an empty or invalid response.")
        return text.strip()


def json_object(text: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise ModelError("Model did not return valid JSON.") from exc
    if not isinstance(value, dict):
        raise ModelError("Model response must be a JSON object.")
    return value
