"""
API client interfaces and implementations for My CLI.

This module provides the core API client interfaces and implementations
for communicating with AI models, mirroring the functionality of the
original Gemini CLI's client system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol, Union
import asyncio
import logging
from pathlib import Path

from pydantic import BaseModel, Field
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Authentication types for API clients."""
    API_KEY = "api_key"
    LOGIN_WITH_GOOGLE = "login_with_google"
    APPLICATION_DEFAULT_CREDENTIALS = "application_default_credentials"


@dataclass
class ContentGeneratorConfig:
    """Configuration for content generation."""
    model: str
    auth_type: AuthType
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40


class Content(BaseModel):
    """Represents a piece of content in a conversation."""
    role: str = Field(description="Role of the content (user or model)")
    parts: List[Dict[str, Any]] = Field(description="Content parts")


class GenerateContentResponse(BaseModel):
    """Response from content generation."""
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    usage_metadata: Optional[Dict[str, Any]] = None
    automatic_function_calling_history: Optional[List[Content]] = None


class SendMessageParameters(BaseModel):
    """Parameters for sending a message."""
    message: str = Field(description="Message to send")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Additional config")


class ContentGenerator(Protocol):
    """Protocol for content generation."""
    
    async def generate_content(
        self,
        model: str,
        contents: List[Content],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content based on input."""
        ...
    
    async def generate_content_stream(
        self,
        model: str,
        contents: List[Content],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Generate content with streaming response."""
        ...


class GeminiContentGenerator:
    """Implementation of ContentGenerator for Google Gemini API."""
    
    def __init__(self, config: ContentGeneratorConfig):
        self.config = config
        self._client: Optional[genai.GenerativeModel] = None
        
    async def initialize(self):
        """Initialize the Gemini client."""
        if self.config.auth_type == AuthType.API_KEY:
            if not self.config.api_key:
                raise ValueError("API key is required for API key authentication")
            genai.configure(api_key=self.config.api_key)
        elif self.config.auth_type == AuthType.APPLICATION_DEFAULT_CREDENTIALS:
            # Configure using application default credentials
            genai.configure()
        else:
            raise ValueError(f"Unsupported auth type: {self.config.auth_type}")
        
        self._client = genai.GenerativeModel(self.config.model)
    
    async def generate_content(
        self,
        model: str,
        contents: List[Content],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content using Gemini API."""
        if not self._client:
            await self.initialize()
        
        # Convert contents to Gemini format
        gemini_contents = self._convert_contents_to_gemini(contents)
        
        try:
            # For now, create a simple text prompt from the last user message
            if gemini_contents:
                last_content = gemini_contents[-1]
                if last_content.role == "user" and last_content.parts:
                    # Extract text from parts
                    text_parts = [part.get("text", "") for part in last_content.parts if "text" in part]
                    prompt = " ".join(text_parts)
                    
                    response = await asyncio.to_thread(
                        self._client.generate_content,
                        prompt
                    )
                    
                    return GenerateContentResponse(
                        candidates=[{
                            "content": {
                                "role": "model",
                                "parts": [{"text": response.text}]
                            }
                        }],
                        usage_metadata={
                            "prompt_token_count": getattr(response.usage_metadata, 'prompt_token_count', 0),
                            "candidates_token_count": getattr(response.usage_metadata, 'candidates_token_count', 0),
                            "total_token_count": getattr(response.usage_metadata, 'total_token_count', 0)
                        } if hasattr(response, 'usage_metadata') else None
                    )
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
        
        # Return empty response if no valid content
        return GenerateContentResponse()
    
    async def generate_content_stream(
        self,
        model: str,
        contents: List[Content],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Generate content with streaming response using Gemini API."""
        if not self._client:
            await self.initialize()
        
        # Convert contents to Gemini format
        gemini_contents = self._convert_contents_to_gemini(contents)
        
        try:
            if gemini_contents:
                last_content = gemini_contents[-1]
                if last_content.role == "user" and last_content.parts:
                    # Extract text from parts
                    text_parts = [part.get("text", "") for part in last_content.parts if "text" in part]
                    prompt = " ".join(text_parts)
                    
                    # Use asyncio.to_thread for streaming as well
                    def _stream_generate():
                        return self._client.generate_content(prompt, stream=True)
                    
                    stream = await asyncio.to_thread(_stream_generate)
                    
                    for chunk in stream:
                        if chunk.text:
                            yield GenerateContentResponse(
                                candidates=[{
                                    "content": {
                                        "role": "model",
                                        "parts": [{"text": chunk.text}]
                                    }
                                }]
                            )
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise
    
    def _convert_contents_to_gemini(self, contents: List[Content]) -> List[Content]:
        """Convert internal content format to Gemini format."""
        return contents


class Chat(ABC):
    """Abstract base class for chat sessions."""
    
    def __init__(
        self,
        content_generator: ContentGenerator,
        generation_config: Optional[Dict[str, Any]] = None,
        history: Optional[List[Content]] = None
    ):
        self.content_generator = content_generator
        self.generation_config = generation_config or {}
        self.history = history or []
    
    @abstractmethod
    async def send_message(
        self,
        params: SendMessageParameters,
        prompt_id: str
    ) -> GenerateContentResponse:
        """Send a message and get response."""
        pass
    
    @abstractmethod
    async def send_message_stream(
        self,
        params: SendMessageParameters,
        prompt_id: str
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Send a message and get streaming response."""
        pass
    
    def get_history(self, curated: bool = False) -> List[Content]:
        """Get conversation history."""
        return self.history.copy()
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()
    
    def add_history(self, content: Content) -> None:
        """Add content to history."""
        self.history.append(content)


class MyCliChat(Chat):
    """Implementation of Chat for My CLI."""
    
    def __init__(
        self,
        content_generator: ContentGenerator,
        generation_config: Optional[Dict[str, Any]] = None,
        history: Optional[List[Content]] = None
    ):
        super().__init__(content_generator, generation_config, history)
        self._send_promise: Optional[asyncio.Task] = None
    
    async def send_message(
        self,
        params: SendMessageParameters,
        prompt_id: str
    ) -> GenerateContentResponse:
        """Send a message and get response."""
        # Wait for previous message to complete
        if self._send_promise and not self._send_promise.done():
            await self._send_promise
        
        # Create user content
        user_content = Content(
            role="user",
            parts=[{"text": params.message}]
        )
        
        # Get conversation history and add new message
        request_contents = self.get_history(True) + [user_content]
        
        try:
            # Generate response
            response = await self.content_generator.generate_content(
                model="",  # Model is configured in the generator
                contents=request_contents,
                config=params.config
            )
            
            # Update history asynchronously
            self._send_promise = asyncio.create_task(
                self._record_history(user_content, response)
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def send_message_stream(
        self,
        params: SendMessageParameters,
        prompt_id: str
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Send a message and get streaming response."""
        # Wait for previous message to complete
        if self._send_promise and not self._send_promise.done():
            await self._send_promise
        
        # Create user content
        user_content = Content(
            role="user",
            parts=[{"text": params.message}]
        )
        
        # Get conversation history and add new message
        request_contents = self.get_history(True) + [user_content]
        
        try:
            # Generate streaming response
            stream = self.content_generator.generate_content_stream(
                model="",  # Model is configured in the generator
                contents=request_contents,
                config=params.config
            )
            
            # Collect response chunks for history
            response_chunks = []
            async for chunk in stream:
                response_chunks.append(chunk)
                yield chunk
            
            # Update history after streaming completes
            if response_chunks:
                final_response = response_chunks[-1]  # Use last chunk as final response
                self._send_promise = asyncio.create_task(
                    self._record_history(user_content, final_response)
                )
            
        except Exception as e:
            logger.error(f"Error in streaming message: {e}")
            raise
    
    async def _record_history(
        self,
        user_input: Content,
        model_response: GenerateContentResponse
    ) -> None:
        """Record conversation in history."""
        try:
            # Add user input
            self.add_history(user_input)
            
            # Add model response if valid
            if model_response.candidates:
                candidate = model_response.candidates[0]
                if "content" in candidate:
                    model_content = Content(
                        role=candidate["content"]["role"],
                        parts=candidate["content"]["parts"]
                    )
                    self.add_history(model_content)
        except Exception as e:
            logger.error(f"Error recording history: {e}")


class ApiClient:
    """Main API client for My CLI."""
    
    def __init__(self, config: ContentGeneratorConfig):
        self.config = config
        self.content_generator = GeminiContentGenerator(config)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the API client."""
        if not self._initialized:
            await self.content_generator.initialize()
            self._initialized = True
    
    def create_chat(
        self,
        generation_config: Optional[Dict[str, Any]] = None,
        history: Optional[List[Content]] = None
    ) -> MyCliChat:
        """Create a new chat session."""
        return MyCliChat(
            content_generator=self.content_generator,
            generation_config=generation_config,
            history=history
        )
    
    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content directly without chat session."""
        if not self._initialized:
            await self.initialize()
        
        content = Content(role="user", parts=[{"text": prompt}])
        return await self.content_generator.generate_content(
            model=model or self.config.model,
            contents=[content],
            config=config
        )


def create_content_generator_config(
    api_key: Optional[str] = None,
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    **kwargs
) -> ContentGeneratorConfig:
    """Create a content generator configuration."""
    return ContentGeneratorConfig(
        model=model,
        auth_type=auth_type,
        api_key=api_key,
        **kwargs
    )


def create_api_client(
    api_key: Optional[str] = None,
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    **kwargs
) -> ApiClient:
    """Create an API client with the given configuration."""
    config = create_content_generator_config(
        api_key=api_key,
        model=model,
        auth_type=auth_type,
        **kwargs
    )
    return ApiClient(config)