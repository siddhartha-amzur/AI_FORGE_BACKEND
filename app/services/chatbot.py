from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings


class ChatbotService:
    """Service for handling chatbot interactions using LangChain + LiteLLM proxy"""
    
    def __init__(self):
        settings = get_settings()
        
        # Initialize LangChain's ChatOpenAI pointing to LiteLLM proxy
        self.llm = ChatOpenAI(
            model=settings.LITELLM_MODEL,
            openai_api_key=settings.LITELLM_VIRTUAL_KEY,
            openai_api_base=settings.LITELLM_PROXY_URL,
            temperature=0.7,
            max_tokens=500,
            model_kwargs={"user": settings.LITELLM_USER_ID}
        )
    
    async def get_response(self, user_message: str) -> str:
        """
        Get AI response for user message using LangChain
        
        Args:
            user_message: The user's input message
            
        Returns:
            AI-generated response string
        """
        try:
            # Create message chain
            messages = [
                SystemMessage(content="You are a helpful AI assistant. Be concise and friendly."),
                HumanMessage(content=user_message)
            ]
            
            # Get response from LangChain
            response = await self.llm.ainvoke(messages)
            
            return response.content
            
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")


# Singleton instance
chatbot_service = ChatbotService()
