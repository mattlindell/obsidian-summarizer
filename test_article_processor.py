import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

def extract_article_text(url):
    """Extract readable text from a web page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Try to find the main content
        content = None
        for selector in ['article', '[role="main"]', 'main', '.content', '#content']:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            content = soup.find('body')
        
        # Extract text
        text = content.get_text(strip=True, separator=' ')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Try to extract title
        title = soup.find('title')
        title = title.get_text().strip() if title else "Untitled"
        
        # Try to extract author and date (basic attempt)
        author = None
        published = None
        
        # Look for common author patterns
        author_selectors = ['.author', '[rel="author"]', '.byline', '.writer']
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get_text().strip()
                break
        
        return {
            'title': title,
            'text': text,
            'author': author,
            'published': published,
            'url': url
        }
        
    except Exception as e:
        print(f"Error extracting article: {e}")
        return None

def call_ollama(prompt, model="llama3.2:3b"):
    """Call the local Ollama API"""
    try:
        response = requests.post('http://localhost:11434/api/generate', 
                               json={
                                   'model': model,
                                   'prompt': prompt,
                                   'stream': False
                               })
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None

def process_article(url):
    """Main function to process an article URL"""
    print(f"Processing: {url}")
    
    # Extract article content
    article = extract_article_text(url)
    if not article:
        print("Failed to extract article content")
        return None
    
    print(f"Extracted article: {article['title'][:60]}...")
    
    # Create prompt for LLM
    prompt = f"""Please analyze this article and provide a structured summary.

Article Title: {article['title']}
Article URL: {url}
Article Content: {article['text'][:4000]}...

Please respond in this exact format:

SUMMARY:
[Provide a concise 2-3 sentence summary of the main points]

KEY CONCEPTS:
- [Key concept 1]
- [Key concept 2] 
- [Key concept 3]

SUGGESTED CATEGORY:
[Suggest whether this belongs in: Work, Personal, Tech, Business, or Other]
"""
    
    print("Sending to LLM for processing...")
    llm_response = call_ollama(prompt)
    
    if not llm_response:
        print("Failed to get LLM response")
        return None
    
    # Create the formatted output
    output = f"""---
title: "{article['title']}"
source: "{url}"
author: "{article['author'] or 'Unknown'}"
published: "{article['published'] or 'Unknown'}"
created: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
tags: 
  - clipping
  - to-process
---

# {article['title']}

**Source:** [{article['title']}]({url})
**Author:** {article['author'] or 'Unknown'}
**Created:** {datetime.now().strftime('%Y-%m-%d')}

{llm_response}

## Original Content (Excerpt)
{article['text'][:1000]}...
"""
    
    return output

# Test with a URL
if __name__ == "__main__":
    test_url = input("Enter a URL to test: ").strip()
    
    result = process_article(test_url)
    
    if result:
        print("\n" + "="*50)
        print("PROCESSED RESULT:")
        print("="*50)
        print(result)
        
        # Optionally save to file
        save = input("\nSave to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"test_clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"Saved to {filename}")
    else:
        print("Failed to process article")