"""Web search tool implementation for performing web searches.

This module provides a web search tool similar to the Gemini CLI's web search functionality,
allowing users to search the web and get AI-processed results.
"""

import asyncio
import json
import os
import aiohttp
from typing import Any, Dict, List, Optional, Callable, Union
from urllib.parse import quote_plus

from ..base import ReadOnlyTool
from ..types import Icon, ToolResult, ToolLocation


class WebSearchTool(ReadOnlyTool):
    """
    Performs web searches and returns AI-processed results.
    
    This tool searches the web for information based on a query and provides
    structured results with sources and citations.
    """
    
    NAME = "web_search"
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find information on the web"
                }
            },
            "required": ["query"]
        }
        
        super().__init__(
            name=self.NAME,
            display_name="Web Search",
            description="Performs a web search and returns the results. This tool is useful for finding information on the internet based on a query.",
            icon=Icon.GLOBE,
            schema=schema,
            config=config
        )
        
        # Search configuration
        self.SEARCH_TIMEOUT = 10.0  # seconds
        self.MAX_RESULTS = 10
        self.MAX_SNIPPET_LENGTH = 300
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate the search parameters."""
        if not params.get("query"):
            return "The 'query' parameter cannot be empty"
        
        query = params["query"].strip()
        if not query:
            return "The 'query' parameter cannot be empty"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get a description of the search operation."""
        query = params.get("query", "")
        return f'Searching the web for: "{query}"'
    
    async def _search_with_simple_ddg(self, query: str) -> List[Dict[str, Any]]:
        """
        Simple DuckDuckGo search using their instant answer API.
        """
        try:
            # Use DuckDuckGo instant answer API
            api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&pretty=1&no_html=1&skip_disambig=1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    # Get instant answer if available
                    if data.get('AbstractText'):
                        results.append({
                            'title': data.get('AbstractSource', 'DuckDuckGo'),
                            'url': data.get('AbstractURL', ''),
                            'snippet': data.get('AbstractText', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': data.get('AbstractSource', 'DuckDuckGo')
                        })
                    
                    # Get related topics
                    for topic in data.get('RelatedTopics', [])[:self.MAX_RESULTS-len(results)]:
                        if isinstance(topic, dict) and topic.get('Text'):
                            results.append({
                                'title': topic.get('Text', 'No title')[:100],
                                'url': topic.get('FirstURL', ''),
                                'snippet': topic.get('Text', '')[:self.MAX_SNIPPET_LENGTH],
                                'source': 'DuckDuckGo'
                            })
                    
                    # Get answer if available
                    if data.get('Answer') and not results:
                        results.append({
                            'title': f"Answer for '{query}'",
                            'url': data.get('AnswerURL', ''),
                            'snippet': data.get('Answer', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': 'DuckDuckGo'
                        })
                    
                    return results
                    
        except Exception as e:
            print(f"Simple DDG search error: {e}")
            return []

    async def _perform_search_fallback(self, query: str) -> List[Dict[str, Any]]:
        """
        Enhanced fallback search that tries to provide useful information.
        """
        # First try the simple DuckDuckGo API
        try:
            simple_results = await self._search_with_simple_ddg(query)
            if simple_results:
                return simple_results
        except Exception:
            pass
        
        # If that fails, return informative mock results
        search_results = [
            {
                'title': f'Search results for "{query}" are currently limited',
                'url': 'https://github.com/your-project/kimi-code',
                'snippet': f'Real-time web search for "{query}" is temporarily using fallback mode. The search system is designed to integrate with multiple search providers including Google, Bing, and DuckDuckGo APIs.',
                'source': 'Kimi-Code Search'
            },
            {
                'title': f'About "{query}" - Information Available',
                'url': 'https://duckduckgo.com/?q=' + quote_plus(query),
                'snippet': f'You can search for "{query}" directly on search engines. This tool supports real search when properly configured with API keys or when search providers are accessible.',
                'source': 'Search Info'
            },
            {
                'title': f'Configure Real Search for "{query}"',
                'url': 'https://github.com/your-project/kimi-code/blob/main/README.md',
                'snippet': f'To enable real search results for queries like "{query}", configure API keys for Bing Search API or ensure network access to search providers.',
                'source': 'Configuration Help'
            }
        ]
        
        return search_results
    
    async def _search_with_google_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Google Custom Search API (if configured).
        
        This would require:
        1. Google Custom Search API key
        2. Custom Search Engine ID
        3. Proper error handling and rate limiting
        """
        # Placeholder for Google API integration
        # You would implement this if you have Google API credentials
        
        # For now, fall back to the mock implementation
        return await self._perform_search_fallback(query)
    
    async def _search_with_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo HTML interface.
        """
        try:
            # Use DuckDuckGo HTML search
            search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    html_content = await response.text()
                    results = self._parse_duckduckgo_html(html_content)
                    
                    return results if results else []
                    
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return []
    
    def _parse_duckduckgo_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo HTML search results."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Try multiple selectors for DuckDuckGo results
            result_selectors = [
                'div.result',
                'div[class*="result"]',
                'div.web-result',
                'div[data-testid="result"]'
            ]
            
            result_divs = []
            for selector in result_selectors:
                result_divs = soup.select(selector)
                if result_divs:
                    break
            
            # If no specific result divs found, look for any links
            if not result_divs:
                # Fallback: look for any meaningful links in the page
                all_links = soup.find_all('a')
                for link in all_links:
                    href = link.get('href', '')
                    if (href.startswith('http') and 
                        'duckduckgo.com' not in href and 
                        len(link.get_text(strip=True)) > 10):
                        
                        title = link.get_text(strip=True)
                        
                        # Try to find snippet text near the link
                        parent = link.parent
                        snippet = ""
                        if parent:
                            snippet_text = parent.get_text(strip=True)
                            # Remove the title from snippet
                            if title in snippet_text:
                                snippet = snippet_text.replace(title, '').strip()
                            else:
                                snippet = snippet_text
                        
                        results.append({
                            'title': title[:200],
                            'url': href,
                            'snippet': snippet[:self.MAX_SNIPPET_LENGTH],
                            'source': 'DuckDuckGo'
                        })
                        
                        if len(results) >= self.MAX_RESULTS:
                            break
                
                return results
            
            # Parse structured results
            for div in result_divs[:self.MAX_RESULTS]:
                try:
                    # Try different selectors for title link
                    title_link = None
                    link_selectors = ['a.result__a', 'a[data-testid="result-title-a"]', 'h2 a', 'h3 a', 'a']
                    
                    for selector in link_selectors:
                        title_link = div.select_one(selector)
                        if title_link and title_link.get('href'):
                            break
                    
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
                    
                    # Skip internal DuckDuckGo links
                    if not url.startswith('http') or 'duckduckgo.com' in url:
                        continue
                    
                    # Try different selectors for snippet
                    snippet = ''
                    snippet_selectors = [
                        'a.result__snippet', 
                        '.result__snippet',
                        '[data-testid="result-snippet"]',
                        '.snippet'
                    ]
                    
                    for selector in snippet_selectors:
                        snippet_elem = div.select_one(selector)
                        if snippet_elem:
                            snippet = snippet_elem.get_text(strip=True)
                            break
                    
                    # If no snippet found, try to get text from the div
                    if not snippet:
                        div_text = div.get_text(strip=True)
                        # Remove title from text to get snippet
                        if title in div_text:
                            snippet = div_text.replace(title, '').strip()
                        else:
                            snippet = div_text
                    
                    if title and url:
                        results.append({
                            'title': title[:200],
                            'url': url,
                            'snippet': snippet[:self.MAX_SNIPPET_LENGTH],
                            'source': 'DuckDuckGo'
                        })
                        
                except Exception as e:
                    print(f"Error parsing result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            return []
    
    def _parse_duckduckgo_lite_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo lite HTML search results."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Find all result rows in the lite interface
            result_rows = soup.find_all('tr')
            
            for row in result_rows:
                try:
                    # Look for links in the row
                    link = row.find('a')
                    if not link or not link.get('href'):
                        continue
                    
                    href = link.get('href')
                    # Skip internal DuckDuckGo links
                    if href.startswith('/') or 'duckduckgo.com' in href:
                        continue
                    
                    title = link.get_text(strip=True)
                    if not title:
                        continue
                    
                    # Look for snippet text in the same row or next row
                    snippet = ""
                    text_elements = row.find_all(text=True)
                    snippet_parts = []
                    for text in text_elements:
                        clean_text = text.strip()
                        if clean_text and clean_text != title and len(clean_text) > 10:
                            snippet_parts.append(clean_text)
                    
                    snippet = " ".join(snippet_parts)[:self.MAX_SNIPPET_LENGTH]
                    
                    if title and href:
                        results.append({
                            'title': title[:200],
                            'url': href,
                            'snippet': snippet,
                            'source': 'DuckDuckGo'
                        })
                        
                        if len(results) >= self.MAX_RESULTS:
                            break
                        
                except Exception:
                    continue
            
            return results
            
        except Exception:
            return []
    
    async def _search_with_searx(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using SearX (open source search engine).
        You can use public SearX instances or self-host one.
        """
        try:
            # Public SearX instances (you can change this to your preferred instance)
            searx_instances = [
                "https://searx.be",
                "https://search.sapti.me", 
                "https://searx.info"
            ]
            
            for instance in searx_instances:
                try:
                    search_url = f"{instance}/search"
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': 'google,bing,duckduckgo'
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            search_url,
                            params=params,
                            timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                        ) as response:
                            if response.status != 200:
                                continue
                            
                            data = await response.json()
                            results = []
                            
                            for result in data.get('results', [])[:self.MAX_RESULTS]:
                                results.append({
                                    'title': result.get('title', 'No title')[:200],
                                    'url': result.get('url', ''),
                                    'snippet': result.get('content', '')[:self.MAX_SNIPPET_LENGTH],
                                    'source': result.get('engine', 'SearX')
                                })
                            
                            if results:
                                return results
                                
                except Exception:
                    continue
            
            # If all SearX instances fail, return empty results
            return []
            
        except Exception:
            return []
    
    async def _search_with_serper_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Serper API (Google Search API alternative).
        Set SERPER_API_KEY environment variable.
        Free tier: 2500 searches/month.
        """
        api_key = os.getenv('SERPER_API_KEY')
        if not api_key:
            return []
        
        try:
            search_url = "https://google.serper.dev/search"
            headers = {
                'X-API-KEY': api_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'q': query,
                'num': self.MAX_RESULTS
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    search_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    # Parse organic results
                    for result in data.get('organic', []):
                        results.append({
                            'title': result.get('title', 'No title')[:200],
                            'url': result.get('link', ''),
                            'snippet': result.get('snippet', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': 'Serper/Google'
                        })
                    
                    return results
                    
        except Exception as e:
            print(f"Serper API error: {e}")
            return []
    
    async def _search_with_tavily_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Tavily Search API (AI-focused search).
        Set TAVILY_API_KEY environment variable.
        """
        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            return []
        
        try:
            search_url = "https://api.tavily.com/search"
            headers = {
                'Content-Type': 'application/json'
            }
            payload = {
                'api_key': api_key,
                'query': query,
                'search_depth': 'basic',
                'include_answer': False,
                'include_images': False,
                'include_raw_content': False,
                'max_results': self.MAX_RESULTS
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    search_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    # Parse results
                    for result in data.get('results', []):
                        results.append({
                            'title': result.get('title', 'No title')[:200],
                            'url': result.get('url', ''),
                            'snippet': result.get('content', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': 'Tavily'
                        })
                    
                    return results
                    
        except Exception as e:
            print(f"Tavily API error: {e}")
            return []
    
    async def _search_with_brave_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Brave Search API.
        Set BRAVE_API_KEY environment variable.
        """
        api_key = os.getenv('BRAVE_API_KEY')
        if not api_key:
            return []
        
        try:
            search_url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'X-Subscription-Token': api_key
            }
            params = {
                'q': query,
                'count': self.MAX_RESULTS,
                'safesearch': 'moderate',
                'search_lang': 'en',
                'country': 'US'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    # Parse web results
                    for result in data.get('web', {}).get('results', []):
                        results.append({
                            'title': result.get('title', 'No title')[:200],
                            'url': result.get('url', ''),
                            'snippet': result.get('description', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': 'Brave'
                        })
                    
                    return results
                    
        except Exception as e:
            print(f"Brave API error: {e}")
            return []
    
    async def _search_news_feeds(self, query: str) -> List[Dict[str, Any]]:
        """
        Search recent news using RSS feeds and news APIs for news-related queries.
        """
        # Check if query is news-related
        news_keywords = ['news', 'latest', 'recent', 'today', 'breaking', 'update', 'current']
        is_news_query = any(keyword in query.lower() for keyword in news_keywords)
        
        if not is_news_query:
            return []
        
        try:
            # Use NewsAPI if available
            api_key = os.getenv('NEWS_API_KEY')
            if api_key:
                return await self._search_with_newsapi(query, api_key)
            
            # Fallback to RSS feeds
            return await self._search_rss_feeds(query)
            
        except Exception as e:
            print(f"News search error: {e}")
            return []
    
    async def _search_with_newsapi(self, query: str, api_key: str) -> List[Dict[str, Any]]:
        """Search using NewsAPI."""
        try:
            search_url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'apiKey': api_key,
                'pageSize': self.MAX_RESULTS,
                'sortBy': 'publishedAt',
                'language': 'en'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    for article in data.get('articles', []):
                        if article.get('title') and article.get('url'):
                            results.append({
                                'title': article.get('title', 'No title')[:200],
                                'url': article.get('url', ''),
                                'snippet': (article.get('description') or '')[:self.MAX_SNIPPET_LENGTH],
                                'source': article.get('source', {}).get('name', 'NewsAPI')
                            })
                    
                    return results
                    
        except Exception:
            return []
    
    async def _search_rss_feeds(self, query: str) -> List[Dict[str, Any]]:
        """Search RSS feeds for news (basic implementation)."""
        # This would require RSS parsing, simplified for now
        return []

    async def _search_with_bing_api(self, query: str) -> List[Dict[str, Any]]:
        """
        Search using Bing Search API (requires API key).
        Set BING_SEARCH_API_KEY environment variable.
        """
        api_key = os.getenv('BING_SEARCH_API_KEY')
        if not api_key:
            return []
        
        try:
            search_url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                'Ocp-Apim-Subscription-Key': api_key,
                'Content-Type': 'application/json'
            }
            params = {
                'q': query,
                'count': self.MAX_RESULTS,
                'mkt': 'en-US'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    for result in data.get('webPages', {}).get('value', []):
                        results.append({
                            'title': result.get('name', 'No title')[:200],
                            'url': result.get('url', ''),
                            'snippet': result.get('snippet', '')[:self.MAX_SNIPPET_LENGTH],
                            'source': 'Bing'
                        })
                    
                    return results
                    
        except Exception:
            return []
    
    def _format_search_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Format search results into a readable format."""
        if not results:
            return f'No search results found for query: "{query}"'
        
        formatted_parts = []
        formatted_parts.append(f'Web search results for "{query}":')
        formatted_parts.append('=' * 50)
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'Untitled')
            url = result.get('url', 'No URL')
            snippet = result.get('snippet', 'No description available')
            source = result.get('source', 'Unknown source')
            
            formatted_parts.append(f"\n[{i}] {title}")
            formatted_parts.append(f"Source: {source}")
            formatted_parts.append(f"URL: {url}")
            formatted_parts.append(f"Description: {snippet}")
            formatted_parts.append('-' * 30)
        
        # Add sources section
        if results:
            formatted_parts.append('\nSources:')
            for i, result in enumerate(results, 1):
                title = result.get('title', 'Untitled')
                url = result.get('url', 'No URL')
                formatted_parts.append(f"[{i}] {title} ({url})")
        
        return '\n'.join(formatted_parts)
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """Execute the web search operation."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: Invalid parameters. {validation_error}",
                return_display=f"Invalid parameters: {validation_error}",
                success=False
            )
        
        try:
            query = params["query"]
            
            if update_callback:
                update_callback(f"Searching the web for: {query}")
            
            # Perform the search (try different providers in order of reliability)
            search_results = []
            
            # Priority 1: Try Serper API (Google Search API, most reliable)
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying Serper API (Google Search)...")
                    search_results = await self._search_with_serper_api(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"Serper API successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"Serper API not available")
            
            # Priority 2: Try Tavily API (AI-focused search)
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying Tavily Search API...")
                    search_results = await self._search_with_tavily_api(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"Tavily API successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"Tavily API not available")
            
            # Priority 3: Try Brave Search API
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying Brave Search API...")
                    search_results = await self._search_with_brave_api(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"Brave API successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"Brave API not available")
            
            # Priority 4: Try Bing Search API
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying Bing Search API...")
                    search_results = await self._search_with_bing_api(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"Bing API successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"Bing API not available")
            
            # Priority 5: Try News APIs for news queries
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying news search...")
                    search_results = await self._search_news_feeds(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"News search successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"News search not available")
            
            # Priority 6: Try SearX (less reliable, often blocked)
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying SearX aggregator...")
                    search_results = await self._search_with_searx(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"SearX successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"SearX failed: {str(e)}")
            
            # Priority 7: Try DuckDuckGo (often blocked)
            if not search_results:
                try:
                    if update_callback:
                        update_callback("Trying DuckDuckGo...")
                    search_results = await self._search_with_duckduckgo(query)
                    if search_results:
                        if update_callback:
                            update_callback(f"DuckDuckGo successful - found {len(search_results)} results")
                except Exception as e:
                    if update_callback:
                        update_callback(f"DuckDuckGo failed: {str(e)}")
            
            # Final fallback
            if not search_results:
                if update_callback:
                    update_callback("Using fallback search information...")
                search_results = await self._perform_search_fallback(query)
            
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Search operation was cancelled",
                    return_display="Search cancelled",
                    success=False
                )
            
            # Format the results
            formatted_results = self._format_search_results(query, search_results)
            
            if update_callback:
                update_callback(f"Found {len(search_results)} search results")
            
            return self.create_result(
                llm_content=formatted_results,
                return_display=f'Search results for "{query}" returned ({len(search_results)} results)'
            )
            
        except Exception as e:
            error_msg = f"Error during web search for query '{params.get('query', 'unknown')}': {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False
            )