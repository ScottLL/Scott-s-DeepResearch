from ..base_agent import BaseAnalysisAgent

class TranslationAgent(BaseAnalysisAgent):
    """Agent for handling text translation."""
    
    async def translate(self, text: str, target_lang: str) -> str:
        """
        Translate text to English if it's not already in English.
        Returns the original text if it's already in English or if translation fails.
        """
        if target_lang == 'en':
            return text
            
        async with self.state_context("TRANSLATING"):
            try:
                messages = [
                    {"role": "system", "content": "You are a translator. Translate the given text to English accurately, preserving all meaning and context."},
                    {"role": "user", "content": f"Translate this text to English: {text}"}
                ]
                
                translated_text = await self.execute(messages, temperature=0.0, max_tokens=1000)
                return translated_text
            except Exception as e:
                print(f"[Translation] Error: {e}")
                return text  # Return original text if translation fails 