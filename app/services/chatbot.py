from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from typing import Optional


class ChatbotService:
    """Service for handling chatbot interactions using LangChain + LiteLLM proxy"""
    
    def __init__(self):
        settings = get_settings()
        litellm_key = settings.LITELLM_API_KEY or settings.LITELLM_VIRTUAL_KEY
        
        # Initialize LangChain's ChatOpenAI pointing to LiteLLM proxy
        self.llm = ChatOpenAI(
            model=settings.LITELLM_MODEL,
            openai_api_key=litellm_key,
            openai_api_base=settings.LITELLM_PROXY_URL,
            temperature=0.7,
            max_tokens=settings.LITELLM_MAX_TOKENS,
            model_kwargs={"user": settings.LITELLM_USER_ID}
        )
    
    async def get_response(
        self,
        user_message: str,
        conversation_context: str = "",
        attachment_context: str = "",
        image_parts: Optional[list[dict]] = None,
    ) -> str:
        """
        Get AI response for user message using LangChain
        
        Args:
            user_message: The user's input message
            conversation_context: Optional previous conversation history to include in prompt
            
        Returns:
            AI-generated response string
        """
        try:
            sections = []
            if conversation_context:
                sections.append("Conversation history:\n" + conversation_context.strip())
            if attachment_context:
                sections.append(attachment_context.strip())

            current_message = user_message.strip() or "Please analyze the attached files and answer based on them."
            sections.append(f"User question:\n{current_message}")
            full_prompt = "\n\n".join(sections)
            prompt_preview = full_prompt[:1200]
            print("[chatbot] conversation context present:", bool(conversation_context))
            print("[chatbot] attachment context present:", bool(attachment_context))
            print("[chatbot] image part count:", len(image_parts or []))
            print("[chatbot] prompt preview:\n", prompt_preview)

            human_content = full_prompt
            if image_parts:
                human_content = [{"type": "text", "text": full_prompt}, *image_parts]
            
            # Create message chain
            messages = [
                SystemMessage(content="You are a helpful AI assistant. Be concise and accurate. When attachment content or images are provided, use them directly in your answer. Do not say that no file was provided if attached file content or image parts are present. If a file could not be parsed, explain that limitation clearly."),
                HumanMessage(content=human_content)
            ]
            
            # Get response from LangChain
            response = await self.llm.ainvoke(messages)
            print("[chatbot] response received length:", len(str(response.content)))
            
            return response.content
            
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")

    async def get_rag_response(self, rag_prompt: str) -> str:
        """Get grounded AI response for a RAG prompt."""
        try:
            messages = [
                SystemMessage(content="You answer questions only from provided document context. If information is missing, clearly say that it was not found in the uploaded document."),
                HumanMessage(content=rag_prompt),
            ]
            response = await self.llm.ainvoke(messages)
            print("[chatbot] rag response received length:", len(str(response.content)))
            return response.content
        except Exception as e:
            raise Exception(f"Error generating RAG response: {str(e)}")


# Singleton instance
chatbot_service = ChatbotService()
