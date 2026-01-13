"""
DTA Proxy client for LLM interactions.

Provides a wrapper around the OpenAI SDK configured for DTA Proxy.
"""

import base64
from pathlib import Path
from typing import Optional

from openai import OpenAI

from avaliador.config import settings


class DTAProxyClient:
    """
    Client for interacting with DTA Proxy LLM service.

    Uses OpenAI SDK with custom base URL pointing to DTA Proxy.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize DTA Proxy client.

        Args:
            api_key: DTA Proxy API key. Defaults to settings.dta_proxy_api_key.
            base_url: DTA Proxy base URL. Defaults to settings.dta_proxy_base_url.
            model: Model to use. Defaults to settings.dta_model.
        """
        self.api_key = api_key or settings.dta_proxy_api_key
        self.base_url = base_url or settings.dta_proxy_base_url
        self.model = model or settings.dta_model

        if not self.api_key:
            raise ValueError(
                "DTA Proxy API key not configured. "
                "Set DTA_PROXY_API_KEY environment variable or pass api_key parameter."
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def chat_completion(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            system_prompt: System message content.
            user_content: User message content.
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens in response.
            timeout: Request timeout in seconds.

        Returns:
            Response content as string.
        """
        timeout = timeout or settings.llm_timeout

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        return response.choices[0].message.content or ""

    def describe_image(
        self,
        image_data: bytes,
        prompt: str,
        mime_type: str = "image/png",
        max_tokens: int = 500,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Describe an image using vision capabilities.

        Args:
            image_data: Raw image bytes.
            prompt: Prompt describing what to analyze.
            mime_type: MIME type of the image.
            max_tokens: Maximum tokens in response.
            timeout: Request timeout in seconds.

        Returns:
            Description of the image.
        """
        timeout = timeout or settings.vision_timeout

        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=max_tokens,
            timeout=timeout,
        )

        return response.choices[0].message.content or ""

    def describe_image_from_path(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = 500,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Describe an image from file path.

        Args:
            image_path: Path to the image file.
            prompt: Prompt describing what to analyze.
            max_tokens: Maximum tokens in response.
            timeout: Request timeout in seconds.

        Returns:
            Description of the image.
        """
        # Determine MIME type from extension
        extension = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(extension, "image/png")

        image_data = image_path.read_bytes()
        return self.describe_image(
            image_data=image_data,
            prompt=prompt,
            mime_type=mime_type,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def test_connection(self) -> bool:
        """
        Test connection to DTA Proxy.

        Returns:
            True if connection is successful.
        """
        try:
            response = self.chat_completion(
                system_prompt="You are a helpful assistant.",
                user_content="Say 'OK' if you can hear me.",
                max_tokens=10,
                timeout=30,
            )
            return "OK" in response.upper()
        except Exception:
            return False
