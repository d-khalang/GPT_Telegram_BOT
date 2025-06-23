import asyncio
from playwright.async_api import async_playwright

async def fetch_chatgpt_conversation(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        # Wait for at least one message to appear
        await page.wait_for_selector('div[data-message-author-role]')
        # Get all message divs
        message_divs = await page.query_selector_all('div[data-message-author-role]')
        messages = []
        for div in message_divs:
            role = await div.get_attribute('data-message-author-role')
            # Try user message first
            text_div = await div.query_selector('.whitespace-pre-wrap')
            if text_div:
                text = await text_div.inner_text()
            else:
                # Try assistant message (markdown)
                markdown_div = await div.query_selector('.markdown')
                if markdown_div:
                    # Get all text, preserving paragraphs and lists
                    # You can join all <p>, <li>, <h3>, <h4>, etc.
                    parts = []
                    for selector in ['p', 'li', 'h3', 'h4', 'ul', 'ol']:
                        nodes = await markdown_div.query_selector_all(selector)
                        for node in nodes:
                            part = await node.inner_text()
                            if part.strip():
                                parts.append(part.strip())
                    text = '\n'.join(parts) if parts else await markdown_div.inner_text()
                else:
                    text = ""
            messages.append({'role': role, 'text': text.strip()})
        await browser.close()
        return messages

# Example usage:
if __name__ == "__main__":
    url = "https://chatgpt.com/share/68----"
    messages = asyncio.run(fetch_chatgpt_conversation(url))
    for msg in messages:
        print(f"{msg['role']}: {msg['text']}\n{'-'*40}")
