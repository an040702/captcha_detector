import asyncio
import re
import sys
import os
import base64
import random
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page
# from playwright_stealth import stealth_async
from stealth import stealth_async
from colorama import init, Fore, Style
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize colorama
init(autoreset=True)

# Initialize OpenAI Client (Expects OPENAI_API_KEY in environment variables)
# If not set, visual detection will be skipped.
api_key = os.getenv("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=api_key) if api_key else None

class CaptchaDetector:
    def __init__(self):
        # Signatures for known CAPTCHA providers
        self.signatures = {
            "ReCaptcha v2/v3": {
                "selectors": [
                    "iframe[src*='google.com/recaptcha']",
                    "iframe[src*='www.google.com/recaptcha']",
                    ".g-recaptcha",
                    "#g-recaptcha-response"
                ]
            },
            "hCaptcha": {
                "selectors": [
                    "iframe[src*='hcaptcha.com']",
                    ".h-captcha",
                    "textarea[name='h-captcha-response']"
                ]
            },
            "Cloudflare Turnstile": {
                "selectors": [
                    "iframe[src*='challenges.cloudflare.com']",
                    ".cf-turnstile"
                ]
            },
            "AWS WAF Captcha": {
                "selectors": [
                    "iframe[src*='aws-waf-captcha']",
                    "#aws-waf-captcha-modal"
                ]
            },
            "Generic Captcha": {
                "selectors": [
                    "img[src*='captcha']",
                    "input[name*='captcha']",
                    ".captcha",
                    "#captcha"
                ]
            }
        }

    async def detect_visual_ai(self, page: Page):
        """
        Uses GPT-4o Vision to detect Captcha from screenshot.
        Returns: (bool, str) -> (Found?, Description)
        """
        if not openai_client:
            return False, "AI Vision not configured (Missing OPENAI_API_KEY)"

        try:
            # Take screenshot in memory
            screenshot_bytes = await page.screenshot(full_page=False)
            base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini", # Use mini for speed and cost
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Look at this webpage screenshot. Is there any CAPTCHA, puzzle, or bot protection challenge visible? Answer YES or NO followed by the type if found."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50
            )
            
            answer = response.choices[0].message.content
            if "YES" in answer.upper():
                return True, f"AI VISION DETECTED: {answer}"
            else:
                return False, None

        except Exception as e:
            return False, f"AI Error: {str(e)}"

    async def detect(self, page: Page, url: str, use_ai: bool = False):
        results = []
        
        # 1. Check specific selectors (DOM Signature)
        for name, data in self.signatures.items():
            for selector in data["selectors"]:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        results.append(f"DETECTED: {name} (Selector: {selector})")
                        break # Found this type, move to next type
                except Exception:
                    continue

        # 2. Text analysis (Simple Heuristic)
        try:
            content = await page.content()
            if "captcha" in content.lower():
                results.append("WARNING: Keyword 'captcha' found in HTML source")
        except:
            pass

        # 3. Visual AI Analysis (Fallback if DOM didn't find anything BUT use_ai is True)
        # Only trigger AI if no results yet and use_ai is enabled
        if use_ai and not results:
             found, desc = await self.detect_visual_ai(page)
             if found:
                 results.append(desc)

        return results

class SiteScanner:
    def __init__(self, input_file: str, max_depth: int = 2, max_pages: int = 20, use_ai: bool = False):
        self.input_file = input_file
        self.max_depth = max_depth
        self.max_pages_per_site = max_pages
        self.visited_urls = set()
        self.detector = CaptchaDetector()
        self.output_file = "captcha_found.txt"
        self.use_ai = use_ai
        
        # Clear output file on init
        with open(self.output_file, 'w') as f:
            f.write("")

    def read_urls(self):
        try:
            with open(self.input_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"{Fore.RED}Error: File {self.input_file} not found.{Style.RESET_ALL}")
            return []

    def save_found_url(self, url: str):
        # Avoid duplicates in output file
        try:
            with open(self.output_file, 'r') as f:
                if url in f.read():
                    return
        except FileNotFoundError:
            pass
            
        with open(self.output_file, 'a') as f:
            f.write(f"{url}\n")

    def normalize_url(self, url):
        """
        Normalize URL to avoid duplicates (e.g. trailing slashes)
        """
        try:
            parsed = urlparse(url)
            # Normalize scheme and netloc to lower case
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path
            
            # Remove trailing slash from path if present
            if path.endswith('/') and len(path) > 1:
                path = path[:-1]
                
            # Sort query params (optional, but good for strict deduplication)
            # For now, we keep query params as is to be safe
            
            # Reconstruct URL
            return f"{scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")
        except:
            return url

    def is_strict_scope(self, start_url, target_url):
        """
        Checks if target_url is within the strict scope of start_url.
        Must match the exact hostname (no other subdomains allowed).
        """
        try:
            start_parsed = urlparse(start_url)
            target_parsed = urlparse(target_url)
            
            start_host = start_parsed.netloc.lower().replace('www.', '')
            target_host = target_parsed.netloc.lower().replace('www.', '')
            
            return start_host == target_host
        except:
            return False

    def get_priority_score(self, url):
        # Expanded keyword list
        priority_keywords = [
            'login', 'signin', 'register', 'signup', 'auth', 'account', 
            'contact', 'forgot', 'verify', 'check', 'search', 'password',
            'feedback', 'support', 'join', 'create', 'newsletter', 'subscribe'
        ]
        url_lower = url.lower()
        for keyword in priority_keywords:
            if keyword in url_lower:
                return 2
        return 1

    async def handle_cookie_consent(self, page: Page):
        """
        Attempts to close typical cookie consent popups to reveal page content.
        """
        try:
            # Common selectors for "Accept" buttons
            # We look for buttons containing specific text
            keywords = ["Accept All", "Allow All", "Accept Cookies", "Agree", "I Agree", "Accept"]
            
            for keyword in keywords:
                # Try to find a button or link with this text (case insensitive)
                button = page.get_by_role("button", name=re.compile(keyword, re.IGNORECASE))
                if await button.count() > 0 and await button.first.is_visible():
                    # print(f"    [i] Auto-clicking cookie consent: {keyword}")
                    await button.first.click(timeout=2000)
                    await asyncio.sleep(1) # Wait for popup to disappear
                    return # Stop after first successful click
                    
            # Fallback: check for specific IDs commonly used
            common_ids = ["onetrust-accept-btn-handler", "accept-cookies", "cookie-accept"]
            for cid in common_ids:
                loc = page.locator(f"#{cid}")
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(timeout=2000)
                    await asyncio.sleep(1)
                    return

        except Exception:
            pass # Ignore errors here, it's just an optimization

    async def simulate_human_behavior(self, page: Page):
        """
        Moves mouse randomly to simulate human activity.
        """
        try:
            # Get viewport size
            viewport = page.viewport_size
            width = viewport['width'] if viewport else 1280
            height = viewport['height'] if viewport else 720

            # Random mouse movements
            for _ in range(random.randint(3, 6)):
                x = random.randint(0, width)
                y = random.randint(0, height)
                await page.mouse.move(x, y, steps=10)
                await asyncio.sleep(random.uniform(0.1, 0.5))
        except Exception:
            pass

    async def scan_site(self, context, start_url):
        queue = asyncio.Queue()
        start_normalized = self.normalize_url(start_url)
        await queue.put((start_url, 0))  # (url, depth)
        queued_urls = {start_normalized}
        
        site_visited = set()
        pages_scanned = 0
        
        print(f"\n{Fore.MAGENTA}=== Starting Deep Scan for: {start_url} ==={Style.RESET_ALL}")

        while not queue.empty() and pages_scanned < self.max_pages_per_site:
            current_url, depth = await queue.get()
            
            # Normalize URL for checking
            normalized_url = self.normalize_url(current_url)
            
            if normalized_url in site_visited or normalized_url in self.visited_urls:
                continue
            site_visited.add(normalized_url)
            self.visited_urls.add(normalized_url)
            
            # Skip non-http
            if not current_url.startswith(('http://', 'https://')):
                continue
            
            # Skip static files
            skip_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', 
                             '.ico', '.svg', '.zip', '.tar', '.gz', '.mp4', '.mp3', 
                             '.woff', '.woff2', '.ttf', '.xml', '.json')
            if current_url.lower().endswith(skip_extensions):
                continue

            print(f"{Fore.CYAN}[*] Scanning (Depth {depth}): {current_url}{Style.RESET_ALL}")
            
            page = await context.new_page()
            
            # APPLY STEALTH MODE
            await stealth_async(page)

            try:
                # Load page
                try:
                    # Increased timeout to 60s and allow more wait time
                    await page.goto(current_url, wait_until='domcontentloaded', timeout=60000)
                    
                    # Simulate Human Behavior immediately
                    await self.simulate_human_behavior(page)

                    # Try to wait for network to settle (useful for heavy SPAs)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass # Continue even if network is busy

                    # Fixed wait to ensure rendering
                    await asyncio.sleep(3)
                    
                    # 0. Try to handle Cookie Consent Popup
                    await self.handle_cookie_consent(page)

                    # Auto-scroll to trigger lazy loading
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2) 
                except Exception as e:
                    print(f"{Fore.YELLOW}[!] Timeout/Error loading {current_url}: {e}{Style.RESET_ALL}")
                    await page.close()
                    continue

                # 1. Detect Captcha
                # Logic: Use AI only if DOM detection fails AND page is high priority
                
                # First pass: DOM Detection only
                detections = await self.detector.detect(page, current_url, use_ai=False)
                
                # Second pass: AI Vision (if no detections and high priority and AI enabled)
                if not detections and self.use_ai and self.get_priority_score(current_url) > 1:
                    print(f"{Fore.YELLOW}[~] Checking with AI Vision...{Style.RESET_ALL}")
                    detections = await self.detector.detect(page, current_url, use_ai=True)

                if detections:
                    print(f"{Fore.RED}[!] CAPTCHA FOUND at {current_url}{Style.RESET_ALL}")
                    for d in detections:
                         print(f"    -> {d}")
                    self.save_found_url(current_url)
                else:
                    print(f"{Fore.GREEN}[+] No CAPTCHA at {current_url}{Style.RESET_ALL}")

                # 2. Crawl for more links if depth allows
                if depth < self.max_depth:
                    links = await page.locator('a').evaluate_all("els => els.map(e => e.href)")
                    
                    for link in links:
                        link = (link or "").split('#')[0].strip()
                        if not link:
                            continue
                        if link.startswith(('javascript:', 'mailto:', 'tel:')):
                            continue

                        # Resolve relative URLs
                        if link.startswith(('http://', 'https://')):
                            absolute_link = link
                        else:
                            absolute_link = urljoin(current_url, link)

                        # Strict scope check: must be same hostname (subdomain sensitive)
                        if self.is_strict_scope(start_url, absolute_link):
                            norm_link = self.normalize_url(absolute_link)
                            if norm_link not in site_visited and norm_link not in self.visited_urls and norm_link not in queued_urls:
                                await queue.put((absolute_link, depth + 1))
                                queued_urls.add(norm_link)
                    
                pages_scanned += 1

            except Exception as e:
                print(f"{Fore.YELLOW}[!] Error processing {current_url}: {str(e)}{Style.RESET_ALL}")
            finally:
                await page.close()

    async def run(self):
        urls = self.read_urls()
        if not urls:
            return

        async with async_playwright() as p:
            # Use Firefox which is often less blocked by default WAF rules than Chromium
            browser = await p.firefox.launch(headless=True) 
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                viewport={'width': 1280, 'height': 720},
                locale='en-US',
                timezone_id='Europe/London'
            )
            
            for base_url in urls:
                if not base_url.startswith('http'):
                    base_url = 'https://' + base_url
                
                await self.scan_site(context, base_url)

            await browser.close()

if __name__ == "__main__":
    # To enable AI, set env var OPENAI_API_KEY and change use_ai=True below
    # Currently disabled by default to avoid costs unless configured
    use_ai_vision = True if os.getenv("OPENAI_API_KEY") else False
    
    if use_ai_vision:
        print(f"{Fore.YELLOW}[INFO] AI Vision Enabled (GPT-4o-mini){Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}[INFO] AI Vision Disabled (No API Key found). Using DOM detection only.{Style.RESET_ALL}")

    scanner = SiteScanner("urls.txt", max_depth=3, max_pages=50, use_ai=use_ai_vision)
    asyncio.run(scanner.run())
