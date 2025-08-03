"""Web fetch tool implementation for fetching and processing web content.

This module provides a web fetch tool similar to the Gemini CLI's web fetch functionality,
allowing users to fetch and process content from URLs with AI assistance.
"""

import asyncio
import re
import aiohttp
import html2text
from typing import Any, Dict, List, Optional, Callable, Union
from urllib.parse import urlparse

from ..base import ReadOnlyTool
from ..types import Icon, ToolResult, ToolLocation


class WebFetchTool(ReadOnlyTool):
    """
    Processes content from URL(s) by fetching and analyzing web pages.
    
    This tool can fetch content from up to 20 URLs embedded in a prompt and process them
    according to specific instructions (e.g., summarize, extract data).
    """
    
    NAME = "web_fetch"
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A comprehensive prompt that includes the URL(s) (up to 20) to fetch and specific instructions on how to process their content (e.g., 'Summarize https://example.com/article and extract key points from https://another.com/data'). Must contain at least one URL starting with http:// or https://."
                }
            },
            "required": ["prompt"]
        }
        
        super().__init__(
            name=self.NAME,
            display_name="Web Fetch",
            description="Processes content from URL(s), including local and private network addresses (e.g., localhost), embedded in a prompt. Include up to 20 URLs and instructions (e.g., summarize, extract specific data) directly in the 'prompt' parameter.",
            icon=Icon.GLOBE,
            schema=schema,
            config=config
        )
        
        # Configure html2text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = True
        self.html_converter.ignore_images = True
        self.html_converter.body_width = 0  # Don't wrap lines
        
        # Constants
        self.URL_FETCH_TIMEOUT = 10.0  # seconds
        self.MAX_CONTENT_LENGTH = 100000  # characters
        self.MAX_URLS = 20
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        return urls[:self.MAX_URLS]  # Limit to max URLs
    
    def _is_private_ip(self, url: str) -> bool:
        """Check if URL points to a private/local IP address."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return False
            
            # Check for localhost variants
            if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                return True
            
            # Check for private IP ranges
            parts = hostname.split('.')
            if len(parts) == 4:
                try:
                    first_octet = int(parts[0])
                    second_octet = int(parts[1])
                    
                    # 10.0.0.0/8
                    if first_octet == 10:
                        return True
                    
                    # 172.16.0.0/12
                    if first_octet == 172 and 16 <= second_octet <= 31:
                        return True
                    
                    # 192.168.0.0/16
                    if first_octet == 192 and second_octet == 168:
                        return True
                        
                except ValueError:
                    pass
            
            return False
            
        except Exception:
            return False
    
    def _convert_github_url(self, url: str) -> str:
        """Convert GitHub blob URLs to raw URLs for better content access."""
        if 'github.com' in url and '/blob/' in url:
            return url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
        return url
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate the web fetch parameters."""
        if not params.get("prompt"):
            return "The 'prompt' parameter cannot be empty and must contain URL(s) and instructions"
        
        prompt = params["prompt"].strip()
        if not prompt:
            return "The 'prompt' parameter cannot be empty and must contain URL(s) and instructions"
        
        # Check for URLs in the prompt
        if 'http://' not in prompt and 'https://' not in prompt:
            return "The 'prompt' must contain at least one valid URL (starting with http:// or https://)"
        
        urls = self._extract_urls(prompt)
        if not urls:
            return "No valid URLs found in the prompt"
        
        if len(urls) > self.MAX_URLS:
            return f"Too many URLs found ({len(urls)}). Maximum allowed is {self.MAX_URLS}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get a description of the web fetch operation."""
        prompt = params.get("prompt", "")
        display_prompt = prompt[:100] + "..." if len(prompt) > 100 else prompt
        return f'Processing URLs and instructions from prompt: "{display_prompt}"'
    
    async def _fetch_url_content(self, url: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch content from a single URL."""
        try:
            # Convert GitHub URLs to raw format
            fetch_url = self._convert_github_url(url)
            
            async with session.get(
                fetch_url,
                timeout=aiohttp.ClientTimeout(total=self.URL_FETCH_TIMEOUT)
            ) as response:
                if response.status != 200:
                    return {
                        'url': url,
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'content': None
                    }
                
                # Get content type
                content_type = response.headers.get('content-type', '').lower()
                
                # Read content
                content = await response.text()
                
                # Convert HTML to text if it's HTML content
                if 'html' in content_type:
                    text_content = self.html_converter.handle(content)
                else:
                    text_content = content
                
                # Truncate if too long
                if len(text_content) > self.MAX_CONTENT_LENGTH:
                    text_content = text_content[:self.MAX_CONTENT_LENGTH] + "\n... (content truncated)"
                
                return {
                    'url': url,
                    'success': True,
                    'error': None,
                    'content': text_content,
                    'content_type': content_type
                }
                
        except asyncio.TimeoutError:
            return {
                'url': url,
                'success': False,
                'error': f'Request timeout after {self.URL_FETCH_TIMEOUT} seconds',
                'content': None
            }
        except Exception as e:
            return {
                'url': url,
                'success': False,
                'error': str(e),
                'content': None
            }
    
    async def _process_with_ai(self, prompt: str, url_contents: List[Dict[str, Any]]) -> str:
        """Process the fetched content with AI (placeholder for now)."""
        # For now, we'll return a formatted response
        # In a full implementation, this would call the AI model to process the content
        
        result_parts = []
        result_parts.append(f"Processed content based on prompt: '{prompt[:200]}...' if len(prompt) > 200 else prompt")
        result_parts.append("\n" + "="*50 + "\n")
        
        for i, content_info in enumerate(url_contents, 1):
            url = content_info['url']
            success = content_info['success']
            
            result_parts.append(f"URL {i}: {url}")
            
            if success:
                content = content_info['content']
                content_type = content_info.get('content_type', 'unknown')
                result_parts.append(f"Status: Successfully fetched ({content_type})")
                result_parts.append(f"Content preview (first 500 chars):")
                result_parts.append(content[:500] + ("..." if len(content) > 500 else ""))
            else:
                error = content_info['error']
                result_parts.append(f"Status: Failed - {error}")
            
            result_parts.append("\n" + "-"*30 + "\n")
        
        return "\n".join(result_parts)
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """Execute the web fetch operation."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: Invalid parameters. {validation_error}",
                return_display=f"Invalid parameters: {validation_error}",
                success=False
            )
        
        try:
            prompt = params["prompt"]
            urls = self._extract_urls(prompt)
            
            if update_callback:
                update_callback(f"Fetching content from {len(urls)} URL(s)...")
            
            # Check for private IPs and handle differently if needed
            private_urls = [url for url in urls if self._is_private_ip(url)]
            if private_urls:
                # For private URLs, we might want to handle them specially
                # For now, we'll proceed but note this in the results
                pass
            
            # Fetch content from all URLs
            url_contents = []
            
            # Create aiohttp session with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; KimiCode-WebFetch/1.0)'
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                tasks = []
                for url in urls:
                    if abort_signal.is_set():
                        break
                    task = self._fetch_url_content(url, session)
                    tasks.append(task)
                
                # Wait for all fetches to complete
                if tasks:
                    url_contents = await asyncio.gather(*tasks, return_exceptions=False)
            
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Operation was cancelled",
                    return_display="Operation cancelled",
                    success=False
                )
            
            if update_callback:
                successful_fetches = sum(1 for content in url_contents if content['success'])
                update_callback(f"Successfully fetched {successful_fetches}/{len(urls)} URLs")
            
            # Process the content
            processed_content = await self._process_with_ai(prompt, url_contents)
            
            # Prepare summary for display
            successful_urls = [content['url'] for content in url_contents if content['success']]
            failed_urls = [content['url'] for content in url_contents if not content['success']]
            
            display_parts = []
            if successful_urls:
                display_parts.append(f"Successfully processed {len(successful_urls)} URL(s)")
            if failed_urls:
                display_parts.append(f"Failed to fetch {len(failed_urls)} URL(s)")
            
            return_display = "; ".join(display_parts) if display_parts else "Content processed"
            
            return self.create_result(
                llm_content=processed_content,
                return_display=return_display
            )
            
        except Exception as e:
            error_msg = f"Error during web fetch operation: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False
            )