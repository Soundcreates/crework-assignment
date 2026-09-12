from app.ai.client import AIClient
from app.ai.schemas import SignalExtractionResult


async def extract_signals(
    ai: AIClient,
    company_name: str,
    source_url: str,
    source_title: str,
    source_text: str,
) -> SignalExtractionResult:
    return await ai.extract_signals(company_name, source_url, source_title, source_text)
