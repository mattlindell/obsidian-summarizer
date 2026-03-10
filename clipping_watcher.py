import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ClippingProcessor(FileSystemEventHandler):
    def __init__(self, clippings_dir, processed_dir):
        self.clippings_dir = clippings_dir
        self.processed_dir = processed_dir
        
        # Create processed directory if it doesn't exist
        os.makedirs(processed_dir, exist_ok=True)
        
        print(f"Watching: {clippings_dir}")
        print(f"Processing to: {processed_dir}")

    def on_created(self, event):
        if event.is_directory:
            return
            
        file_path = str(event.src_path)
        
        # Only process .md files
        if not file_path.lower().endswith('.md'):
            return
            
        print(f"\nNew clipping detected: {os.path.basename(file_path)}")
        
        # Wait a moment for the file to be fully written
        time.sleep(2)
        
        self.process_clipping(file_path)

    def extract_metadata_from_clipping(self, file_path):
        """Extract URL, author, and published date from the web clipping file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = {
                'url': '',
                'author': '',
                'published': '',
                'title': ''
            }
            
            # Look for URL in various formats
            url_patterns = [
                r'source:\s*"?([^"\n]+)"?',  # YAML frontmatter
                r'url:\s*"?([^"\n]+)"?',     # Alternative YAML
                r'https?://[^\s\)]+',        # Any HTTP URL
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    url = matches[0].strip()
                    if url.startswith('http'):
                        metadata['url'] = url
                        break
            
            # Extract author - handle both single author and list format
            author_match = re.search(r'author:\s*\n?\s*-?\s*"?\[\[(.+?)\]\]"?', content, re.IGNORECASE | re.MULTILINE)
            if not author_match:
                author_match = re.search(r'author:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            
            if author_match:
                metadata['author'] = author_match.group(1).strip()
            
            # Extract published date
            published_match = re.search(r'published:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            if published_match:
                metadata['published'] = published_match.group(1).strip()
            
            # Extract title from frontmatter
            title_match = re.search(r'title:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            if title_match:
                metadata['title'] = title_match.group(1).strip().strip('"')
            
            if not metadata['url']:
                print("No URL found in clipping")
                return None
                
            return metadata
            
        except Exception as e:
            print(f"Error reading clipping file: {e}")
            return None

    def extract_article_text(self, url):
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
            if content is not None:
                text = content.get_text(strip=True, separator=' ')
                text = re.sub(r'\s+', ' ', text)
            else:
                text = ""
            
            # Try to extract title
            title = soup.find('title')
            title = title.get_text().strip() if title else "Untitled"
            
            # Try to extract author
            author = None
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
                'url': url
            }
            
        except Exception as e:
            print(f"Error extracting article: {e}")
            return None

    def call_ollama(self, prompt, model="llama3.2:3b"):
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

    def process_clipping(self, file_path):
        """Process a single clipping file"""
        try:
            # Extract metadata from the clipping
            clipping_metadata = self.extract_metadata_from_clipping(file_path)
            if not clipping_metadata:
                print("Skipping - no URL found")
                return
            
            url = clipping_metadata['url']
            print(f"Processing URL: {url}")
            
            # Extract article content
            article = self.extract_article_text(url)
            if not article:
                print("Failed to extract article content")
                return
            
            # Use clipping metadata if available, fallback to scraped data
            title = clipping_metadata.get('title') or article['title']
            author = clipping_metadata.get('author') or article['author']
            published = clipping_metadata.get('published') or 'Unknown'
            
            # Create prompt for LLM
            prompt = f"""Please analyze this article and provide a structured summary.

Article Title: {title}
Article URL: {url}
Article Content: {article['text'][:4000]}...

Please respond in this exact format:

**SUMMARY:**
[Provide a concise 2-3 sentence summary of the main points]

**KEY CONCEPTS:**
- [Key concept 1]
- [Key concept 2] 
- [Key concept 3]

**SUGGESTED CATEGORY:**
[Suggest whether this belongs in: Attention Deficit Disorder, Home Automation, AI and LLMs, Servers and Infrastructure, Development, Management, Operating Systems, Jeep, Dog, Design, or Other]
"""
            
            print("Sending to LLM for processing...")
            llm_response = self.call_ollama(prompt)
            
            if not llm_response:
                print("Failed to get LLM response")
                return
            
            # Create processed filename
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)[:50]
            processed_filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.md"
            processed_path = os.path.join(self.processed_dir, processed_filename)
            
            # Create the formatted output
            output = f"""---
title: "{title}"
source: "{url}"
author: "{author or 'Unknown'}"
published: "{published}"
created: "{datetime.now().strftime('%Y-%m-%d')}"
tags: 
  - clipping
  - resource
  - processed
---
# {title}

## 🤖 AI Summary

{llm_response}

## My Notes

**Key takeaways:** what are the 1-3 most important things you learned?

**Action items:** What specific actions or next steps does this inspire?

**Questions & follow-up:** what questions does this raise? What should I research next?

**Connections:** How does this relate to other things I know or are working on?

**Quality assessment:** How accurate/useful was this? Would I recommend it to others?

## Linked Projects/Domains

```dataview
list
where contains(file.outlinks, this.file.link) and (contains(file.tags, "project") or contains(file.tags, "area") or contains(file.tags, "domain"))
```
"""
            
            # Save processed file
            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(output)
            
            print(f"✅ Processed and saved: {processed_filename}")
            
            # Optionally delete or move the original clipping
            # os.remove(file_path)  # Uncomment to delete original
            
        except Exception as e:
            print(f"Error processing clipping: {e}")

def main():
    # Configuration - UPDATE THESE PATHS
    CLIPPINGS_DIR = r"C:\Users\matt\Obsidian\VaultMatt\Clippings"  # Update this path
    PROCESSED_DIR = r"C:\Users\matt\Obsidian\VaultMatt\Clippings\Processed"  # Update this path
    
    # Verify directories exist
    if not os.path.exists(CLIPPINGS_DIR):
        print(f"Error: Clippings directory not found: {CLIPPINGS_DIR}")
        print("Please update the CLIPPINGS_DIR path in the script")
        return
    
    # Create processor and observer
    processor = ClippingProcessor(CLIPPINGS_DIR, PROCESSED_DIR)
    observer = Observer()
    observer.schedule(processor, CLIPPINGS_DIR, recursive=False)
    
    # Start watching
    observer.start()
    print(f"\n🔍 Folder watcher started!")
    print("Waiting for new clippings...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 Stopping folder watcher...")
    
    observer.join()

if __name__ == "__main__":
    main()