# Web Search API Configuration

The `google_web_search` tool supports multiple search providers. To get real search results instead of fallback information, configure one or more API keys.

## Supported Search APIs

### 1. Serper API (Recommended) 🥇
**Google Search results via API**
- **Free tier**: 2,500 searches/month
- **Reliability**: Highest (Google-powered)
- **Setup**: 
  ```bash
  export SERPER_API_KEY="your-serper-api-key"
  ```
- **Get API key**: https://serper.dev/
- **Cost**: Free tier, then $5/1000 searches

### 2. Tavily Search API 🤖
**AI-focused search engine**
- **Free tier**: 1,000 searches/month
- **Reliability**: High (designed for AI applications)
- **Setup**:
  ```bash
  export TAVILY_API_KEY="your-tavily-api-key"
  ```
- **Get API key**: https://tavily.com/
- **Cost**: Free tier, then $0.005/search

### 3. Brave Search API 🔒
**Privacy-focused search**
- **Free tier**: 2,000 searches/month
- **Reliability**: High
- **Setup**:
  ```bash
  export BRAVE_API_KEY="your-brave-api-key"
  ```
- **Get API key**: https://api.search.brave.com/
- **Cost**: Free tier, then $3/1000 searches

### 4. Bing Search API (Microsoft) 🔵
**Microsoft's search engine**
- **Free tier**: 1,000 searches/month
- **Reliability**: High
- **Setup**:
  ```bash
  export BING_SEARCH_API_KEY="your-bing-api-key"
  ```
- **Get API key**: https://azure.microsoft.com/en-us/services/cognitive-services/bing-web-search-api/
- **Cost**: Free tier, then $7/1000 searches

### 5. NewsAPI (For news queries) 📰
**News-specific search**
- **Free tier**: 1,000 requests/month
- **Reliability**: High for news content
- **Setup**:
  ```bash
  export NEWS_API_KEY="your-news-api-key"
  ```
- **Get API key**: https://newsapi.org/
- **Cost**: Free tier, then $449/month for commercial

## Quick Setup (Recommended)

For best results, set up **Serper API**:

1. Visit https://serper.dev/
2. Sign up for free account
3. Get your API key
4. Add to your environment:
   ```bash
   echo 'export SERPER_API_KEY="your-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

## Search Provider Priority

The tool tries providers in this order:
1. **Serper API** (Google Search) - Most reliable
2. **Tavily API** - AI-optimized
3. **Brave API** - Privacy-focused
4. **Bing API** - Microsoft search
5. **NewsAPI** - For news queries only
6. **SearX** - Open source (often blocked)
7. **DuckDuckGo** - Free but often blocked
8. **Fallback** - Informational messages

## Usage Examples

```bash
# Basic search (will use configured APIs)
my-cli chat --model kimi-k2-base "Use google_web_search to find Python tutorials"

# News search (will prioritize NewsAPI if configured)
my-cli chat --model kimi-k2-base "Use google_web_search to find latest AI news"

# Technical search
my-cli chat --model kimi-k2-base "Use google_web_search to search for 'asyncio python documentation'"
```

## Testing Your Configuration

To test which search providers are working:

```bash
# This will show which providers are tried
my-cli chat --model kimi-k2-base "Use google_web_search to find test query" --verbose
```

## Troubleshooting

### No Real Results?
- Check if environment variables are set: `echo $SERPER_API_KEY`
- Verify API key is valid by testing on the provider's website
- Check your API quota/limits

### Network Issues?
- SearX and DuckDuckGo often fail due to anti-bot measures
- Use API-based providers (Serper, Tavily, Brave, Bing) for reliability
- Consider using a VPN if providers are geo-blocked

### Rate Limits?
- Most APIs have generous free tiers
- Monitor your usage on the provider dashboards
- Consider rotating between multiple APIs

## Cost Optimization

**Free Setup** (Recommended):
- Serper API: 2,500 searches/month free
- Total cost: $0/month for moderate usage

**Power User Setup**:
- Serper API + Tavily API + Brave API
- Combined: ~6,500 free searches/month
- Automatic failover between providers

**Enterprise Setup**:
- All APIs configured
- Maximum reliability and coverage
- Cost: ~$10-50/month depending on usage