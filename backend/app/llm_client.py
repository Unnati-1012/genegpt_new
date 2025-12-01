# backend/app/llm_client.py
import os
import asyncio
from groq import Groq

class LLMClient:
    def __init__(self):
        """
        Initializes the Groq API client using the environment variable GROQ_API_KEY.
        """
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GROQ_API_KEY not found in environment variables. Please set it before running.")
        self.client = Groq(api_key=self.api_key)

    # ---------------------------
    #  (OLD) Single-prompt method
    # ---------------------------
    async def get_response(self, prompt: str) -> str:
        """
        Backward-compatible method:
        Generates a response from a single prompt.
        """
        return await asyncio.to_thread(self._generate_sync_from_prompt, prompt)

    def _generate_sync_from_prompt(self, prompt: str) -> str:
        """Synchronous helper for single prompt use-case."""
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You must NEVER remove, rewrite, paraphrase, or block Markdown provided by the user. "
                            "Especially image Markdown like ![](url). Always return it EXACTLY as provided. "
                            "Do NOT say 'I cannot display images'. Do NOT replace images with descriptions."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            return "Sorry, I couldn't generate a response due to an internal error."

    # --------------------------------------------------
    #  (NEW) Full conversation support: messages = [...]
    # --------------------------------------------------
    async def get_response_from_messages(self, messages: list) -> str:
        return await asyncio.to_thread(self._generate_sync_from_messages, messages)

    def _generate_sync_from_messages(self, messages: list) -> str:
        """Synchronous helper that calls Groq with full conversation history."""
        try:

            # Strong system prompt to preserve markdown
            system_prompt = {
                "role": "system",
                "content": (
                    "IMPORTANT RULES:\n"
                    "- NEVER remove, alter, rewrite, paraphrase, or block Markdown written by the user.\n"
                    "- NEVER replace image markdown with text like 'I cannot display images'.\n"
                    "- When you see image markdown (e.g., ![](https://example.com/img.png)), "
                    "you MUST output it EXACTLY, unchanged.\n"
                    "- Do NOT sanitize, filter, describe, or modify the link.\n"
                    "- If asked to show an image, you MUST reply with the markdown image tag."
                )
            }

            completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[system_prompt] + messages,
                temperature=0.7,
            )

            return completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"❌ Error generating response: {e}")
            return "Sorry, I couldn't generate a response due to an internal error."
