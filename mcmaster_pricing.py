#!/usr/bin/env python3
"""
McMaster-Carr Pricing Intelligence Tool

McMaster is usually more automation-friendly than Grainger.
"""

import re
import json
import os
import urllib.parse
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

# Try to use playwright-stealth if available
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class McMasterPricingTool:
    """McMaster-Carr pricing extraction."""
    
    def __init__(self, headless: bool = True, verbose: bool = False, email: str = None, password: str = None, scraperapi_key: str = None):
        self.headless = headless
        self.verbose = verbose
        self.base_url = "https://www.mcmaster.com"
        self.email = email
        self.password = password
        # Only use ScraperAPI if explicitly passed (not from env var)
        # This allows us to force pure Selenium when scraperapi_key=None
        if scraperapi_key is not None:
            self.scraperapi_key = scraperapi_key
            self.use_scraperapi = True
            if self.verbose:
                print(f"  [DEBUG] ScraperAPI enabled (key: {self.scraperapi_key[:10]}...)")
        else:
            self.scraperapi_key = None
            self.use_scraperapi = False
    
    def _get_url(self, target_url: str) -> str:
        """Get URL - either direct or through ScraperAPI."""
        if self.use_scraperapi:
            import urllib.parse
            encoded_url = urllib.parse.quote(target_url)
            scraperapi_url = f"http://api.scraperapi.com?api_key={self.scraperapi_key}&url={encoded_url}"
            if self.verbose:
                print(f"  [DEBUG] Using ScraperAPI for: {target_url[:60]}...")
            return scraperapi_url
        return target_url
    
    def normalize_query(self, query: str) -> str:
        """Normalize search query."""
        return re.sub(r'\s+', ' ', query.lower().strip())
    
    def mcmaster_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search McMaster and collect product results."""
        normalized = self.normalize_query(query)
        encoded_query = urllib.parse.quote_plus(normalized)
        # McMaster search URL format
        search_url = f"{self.base_url}/{encoded_query}"
        
        candidates = []
        
        if self.verbose:
            print(f"  [DEBUG] Searching McMaster: {search_url}")
        
        with sync_playwright() as p:
            # Enhanced stealth settings
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials'
                ]
            )
            # Use persistent context to maintain cookies/session (looks more real)
            # BUT: Don't load old state if it might be flagged - start fresh sometimes
            import os
            import random
            context_path = os.path.join(os.path.dirname(__file__), '.browser_context')
            os.makedirs(context_path, exist_ok=True)
            state_file = os.path.join(context_path, 'state.json')
            
            # Sometimes start fresh (30% chance) to avoid using flagged sessions
            use_old_state = os.path.exists(state_file) and random.random() > 0.3
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                # Store cookies/session (but sometimes start fresh)
                storage_state=state_file if use_old_state else None,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                    'Referer': self.base_url  # Add referer to look like coming from site
                }
            )
            page = context.new_page()
            
            # Apply stealth plugin if available
            if HAS_STEALTH:
                if self.verbose:
                    print(f"  [DEBUG] Applying playwright-stealth...")
                stealth_sync(page)
            
            # Comprehensive stealth script
            page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Add chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Mock webGL
                const getParameter = WebGLRenderingContext.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter(parameter);
                };
                
                // Mock battery API
                Object.defineProperty(navigator, 'getBattery', {
                    get: () => {
                        return () => Promise.resolve({
                            charging: true,
                            chargingTime: 0,
                            dischargingTime: Infinity,
                            level: 1
                        });
                    }
                });
                
                // Override toString methods
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
            """)
            
            try:
                # Skip login - pricing visible without login
                # (Login disabled - not needed)
                if False and self.email and self.password:
                    if self.verbose:
                        print(f"  [DEBUG] Logging in to McMaster...")
                    page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # Look for login button/link
                    login_selectors = [
                        'a:has-text("Sign In")',
                        'a:has-text("Login")',
                        'a[href*="login"]',
                        'a[href*="signin"]',
                        'button:has-text("Sign In")',
                        '[data-testid*="login"]',
                        '[class*="login"]'
                    ]
                    
                    login_clicked = False
                    for selector in login_selectors:
                        try:
                            login_btn = page.query_selector(selector)
                            if login_btn and login_btn.is_visible():
                                if self.verbose:
                                    print(f"  [DEBUG] Found login button, clicking...")
                                login_btn.click()
                                page.wait_for_timeout(2000)
                                login_clicked = True
                                break
                        except:
                            continue
                    
                    if login_clicked or 'login' in page.url.lower() or 'signin' in page.url.lower():
                        # Wait for login form to load
                        page.wait_for_timeout(2000)
                        
                        # Fill in email - try multiple approaches
                        email_filled = False
                        email_selectors = [
                            'input[type="email"]',
                            'input[name*="email" i]',
                            'input[id*="email" i]',
                            'input[name*="user" i]',
                            'input[id*="user" i]',
                            'input[name*="username" i]',
                            'input[id*="username" i]',
                            '#email',
                            '#username',
                            'input[placeholder*="email" i]',
                            'input[placeholder*="Email" i]',
                            'input[autocomplete="email"]',
                            'input[autocomplete="username"]'
                        ]
                        
                        for selector in email_selectors:
                            try:
                                email_field = page.query_selector(selector)
                                if email_field and email_field.is_visible():
                                    email_field.click()
                                    page.wait_for_timeout(300)
                                    email_field.fill(self.email)
                                    page.wait_for_timeout(300)
                                    if self.verbose:
                                        print(f"  [DEBUG] Entered email using: {selector}")
                                    email_filled = True
                                    break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Email selector {selector} failed: {e}")
                                continue
                        
                        if not email_filled:
                            # Try to find any text input that might be email field
                            try:
                                all_inputs = page.query_selector_all('input[type="text"], input:not([type])')
                                for inp in all_inputs:
                                    if inp.is_visible():
                                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                                        name = (inp.get_attribute('name') or '').lower()
                                        inp_id = (inp.get_attribute('id') or '').lower()
                                        if 'email' in placeholder or 'email' in name or 'email' in inp_id or 'user' in placeholder or 'user' in name:
                                            inp.click()
                                            page.wait_for_timeout(300)
                                            inp.fill(self.email)
                                            if self.verbose:
                                                print(f"  [DEBUG] Entered email in field: {placeholder or name or inp_id}")
                                            email_filled = True
                                            break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Fallback email search failed: {e}")
                        
                        page.wait_for_timeout(500)
                        
                        # Fill in password
                        password_filled = False
                        password_selectors = ['input[type="password"]', 'input[name*="password"]', 'input[id*="password"]', '#password']
                        for selector in password_selectors:
                            try:
                                password_field = page.query_selector(selector)
                                if password_field and password_field.is_visible():
                                    password_field.click()
                                    page.wait_for_timeout(300)
                                    password_field.fill(self.password)
                                    if self.verbose:
                                        print(f"  [DEBUG] Entered password using: {selector}")
                                    password_filled = True
                                    break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Password selector {selector} failed: {e}")
                                continue
                        
                        page.wait_for_timeout(500)
                        
                        # Click submit/sign in button
                        submit_selectors = [
                            'button[type="submit"]',
                            'button:has-text("Sign In")',
                            'button:has-text("Log In")',
                            'input[type="submit"]',
                            'button[class*="submit"]'
                        ]
                        for selector in submit_selectors:
                            try:
                                submit_btn = page.query_selector(selector)
                                if submit_btn:
                                    submit_btn.click()
                                    if self.verbose:
                                        print(f"  [DEBUG] Clicked submit")
                                    break
                            except:
                                continue
                        
                        # Wait for login to complete
                        page.wait_for_timeout(3000)
                        page.wait_for_load_state("networkidle", timeout=10000)
                        
                        # Check if one-time code is required
                        code_indicators = [
                            'one-time code',
                            'verification code',
                            'enter the code',
                            'check your email',
                            'code sent to',
                            'verification',
                            'two-factor'
                        ]
                        
                        page_text = page.inner_text('body').lower()
                        needs_code = any(indicator in page_text for indicator in code_indicators)
                        
                        if needs_code or page.url.lower().count('verify') > 0 or page.url.lower().count('code') > 0:
                            if self.verbose:
                                print(f"  [DEBUG] One-time code required")
                            
                            # Look for code input field
                            code_selectors = [
                                'input[type="text"][name*="code" i]',
                                'input[type="text"][id*="code" i]',
                                'input[type="text"][placeholder*="code" i]',
                                'input[name*="verification" i]',
                                'input[id*="verification" i]',
                                'input[name*="otp" i]',
                                'input[id*="otp" i]',
                                'input[autocomplete="one-time-code"]',
                                'input[inputmode="numeric"]'
                            ]
                            
                            code_field = None
                            for selector in code_selectors:
                                try:
                                    field = page.query_selector(selector)
                                    if field and field.is_visible():
                                        code_field = field
                                        break
                                except:
                                    continue
                            
                            # Fallback: find any visible text input that might be the code field
                            if not code_field:
                                try:
                                    all_inputs = page.query_selector_all('input[type="text"], input[type="number"]')
                                    for inp in all_inputs:
                                        if inp.is_visible():
                                            placeholder = (inp.get_attribute('placeholder') or '').lower()
                                            name = (inp.get_attribute('name') or '').lower()
                                            if 'code' in placeholder or 'code' in name or 'verify' in placeholder or 'verify' in name:
                                                code_field = inp
                                                break
                                except:
                                    pass
                            
                            if code_field:
                                # Prompt user for code
                                print("\n" + "="*80)
                                print("ONE-TIME CODE REQUIRED")
                                print("="*80)
                                print("Please check your email for the verification code.")
                                code = input("Enter the code: ").strip()
                                
                                if code:
                                    try:
                                        code_field.click()
                                        page.wait_for_timeout(300)
                                        code_field.fill(code)
                                        page.wait_for_timeout(500)
                                        
                                        if self.verbose:
                                            print(f"  [DEBUG] Entered verification code")
                                        
                                        # Look for submit/continue button
                                        submit_selectors = [
                                            'button[type="submit"]',
                                            'button:has-text("Verify")',
                                            'button:has-text("Continue")',
                                            'button:has-text("Submit")',
                                            'input[type="submit"]',
                                            'button[class*="submit"]',
                                            'button[class*="continue"]'
                                        ]
                                        
                                        for selector in submit_selectors:
                                            try:
                                                submit_btn = page.query_selector(selector)
                                                if submit_btn and submit_btn.is_visible():
                                                    submit_btn.click()
                                                    if self.verbose:
                                                        print(f"  [DEBUG] Clicked verify/submit button")
                                                    break
                                            except:
                                                continue
                                        
                                        # Wait for verification to complete
                                        page.wait_for_timeout(3000)
                                        page.wait_for_load_state("networkidle", timeout=10000)
                                        
                                    except Exception as e:
                                        if self.verbose:
                                            print(f"  [DEBUG] Error entering code: {e}")
                            else:
                                if self.verbose:
                                    print(f"  [DEBUG] Could not find code input field - you may need to enter it manually")
                                print("\n⚠️  One-time code required but field not found automatically.")
                                print("   Please enter the code manually in the browser, then press Enter here to continue...")
                                input()
                        
                        if self.verbose:
                            print(f"  [DEBUG] Login complete, current URL: {page.url}")
                
                if self.verbose:
                    print(f"  [DEBUG] Loading search page...")
                    print(f"  [DEBUG] Using SLOW mode to avoid detection...")
                
                # Navigate like a real user (not instant)
                # Use ScraperAPI if enabled
                actual_url = self._get_url(search_url) if self.use_scraperapi else search_url
                page.goto(actual_url, wait_until="domcontentloaded", timeout=60000 if self.use_scraperapi else 30000)
                
                # MUCH slower - simulate human reading/scanning
                page.mouse.move(500, 300)
                page.wait_for_timeout(4000)  # 4 second delay
                page.evaluate("window.scrollTo(0, 300)")
                page.wait_for_timeout(3000)  # 3 second delay
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(3000)  # 3 second delay
                
                # Wait for full load
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(5000)  # 5 second delay before interacting
                
                if self.verbose:
                    print(f"  [DEBUG] Page loaded. Looking for products...")
                    print(f"  [DEBUG] Page title: {page.title()}")
                
                # Find ACTUAL product links - be VERY strict
                # McMaster search results can show products in tables or as links
                product_links = []
                query_words = set(normalized.split())
                
                if self.verbose:
                    print(f"  [DEBUG] Looking for product links (STRICT mode)...")
                
                try:
                    # First, try to find product links in tables (like the screenshot shows)
                    # Products in tables might have part numbers as clickable links
                    table_links = page.query_selector_all('table a[href], td a[href], [class*="table"] a[href]')
                    if table_links and len(table_links) > 0:
                        if self.verbose:
                            print(f"  [DEBUG] Found {len(table_links)} links in tables")
                        for link in table_links:
                            try:
                                href = link.get_attribute('href')
                                if href and ('mcmaster.com' in href or href.startswith('/')):
                                    # Check if it's a product URL
                                    if re.search(r'/products/\d+', href) or re.search(r'/([\dA-Z]{6,})/?$', href):
                                        if not re.search(r'/products/[a-z-]+/?$', href.lower()):
                                            product_links.append(link)
                                            if self.verbose:
                                                print(f"    ✓ Table product link: {href[:70]}...")
                            except:
                                continue
                    
                    # Also scan all links on page
                    all_links = page.query_selector_all('a[href]')
                    if self.verbose:
                        print(f"  [DEBUG] Scanning {len(all_links)} total links on page...")
                    
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            if not href:
                                continue
                            
                            # Skip if already found in tables
                            if link in product_links:
                                continue
                            
                            # STRICT: Only accept URLs with numeric product IDs
                            # Format: /products/123456 (numeric ID after /products/)
                            has_numeric_product_id = bool(re.search(r'/products/\d+', href))
                            
                            # OR part number format: /97083A490/ (alphanumeric, 6+ chars, mostly uppercase)
                            has_part_number = False
                            part_match = re.search(r'/([\dA-Z]{6,})/?$', href)
                            if part_match and '/products/' not in href:
                                part_str = part_match.group(1)
                                # Must be mostly uppercase/numbers (not lowercase category)
                                if part_str.isupper() or sum(1 for c in part_str if c.isdigit()) >= 2:
                                    has_part_number = True
                            
                            # REJECT category URLs (lowercase words after /products/)
                            is_category = bool(re.search(r'/products/[a-z-]+/?$', href.lower()))
                            
                            # Only accept if it's a real product URL
                            if (has_numeric_product_id or has_part_number) and not is_category:
                                # Get link text for relevance check
                                link_text = link.inner_text().strip().lower()
                                
                                # For specific queries (3+ words), require some text match
                                # For generic queries, accept any product
                                if len(query_words) >= 3:
                                    if link_text:
                                        link_words = set(link_text.split())
                                        overlap = query_words & link_words
                                        if overlap:  # Must match some query words
                                            product_links.append(link)
                                            if self.verbose:
                                                print(f"    ✓ Product: {href[:70]}... (matches: {overlap})")
                                    else:
                                        # No text but has product URL - accept it
                                        product_links.append(link)
                                        if self.verbose:
                                            print(f"    ✓ Product (no text): {href[:70]}...")
                                else:
                                    # Generic query - accept any product
                                    product_links.append(link)
                                    if self.verbose:
                                        print(f"    ✓ Product: {href[:70]}...")
                        except:
                            continue
                    
                    # Remove duplicates
                    seen_hrefs = set()
                    unique_links = []
                    for link in product_links:
                        try:
                            href = link.get_attribute('href')
                            if href and href not in seen_hrefs:
                                seen_hrefs.add(href)
                                unique_links.append(link)
                        except:
                            continue
                    product_links = unique_links
                    
                    if self.verbose:
                        print(f"  [DEBUG] Found {len(product_links)} unique product links")
                except Exception as e:
                    if self.verbose:
                        print(f"  [DEBUG] Error finding products: {e}")
                
                # Extract product URLs IMMEDIATELY (before any navigation that might destroy context)
                # This is critical - we need to get URLs while the page context is still valid
                product_urls = []
                seen_hrefs = set()
                
                if self.verbose:
                    print(f"  [DEBUG] Extracting product URLs from {len(product_links)} links found...")
                
                for link in product_links:
                    try:
                        href = link.get_attribute('href')
                        if not href or href in seen_hrefs:
                            continue
                        
                        # Make absolute URL
                        if href.startswith('/'):
                            full_url = f"{self.base_url}{href}"
                        elif href.startswith('http') and 'mcmaster.com' in href:
                            full_url = href
                        else:
                            continue
                        
                        seen_hrefs.add(href)
                        product_urls.append(full_url)
                        
                        if self.verbose:
                            print(f"    ✓ Extracted URL: {full_url}")
                    except Exception as e:
                        if self.verbose:
                            print(f"    ⚠️  Error extracting URL from link: {e}")
                        continue
                
                # If we found product URLs, use them! Don't navigate to categories.
                # Only explore categories if we found ZERO products
                if len(product_urls) == 0:
                    if self.verbose:
                        print(f"  [DEBUG] No products found, exploring categories...")
                    
                    # Look for category links that might contain our products
                    try:
                        category_links = page.query_selector_all('a[href*="/products/"]')
                        relevant_category = None
                        
                        for link in category_links:
                            try:
                                href = link.get_attribute('href')
                                text = link.inner_text().strip().lower()
                                
                                # Look for categories related to our query
                                query_lower = normalized.lower()
                                if any(word in text for word in query_lower.split()):
                                    relevant_category = link
                                    if self.verbose:
                                        print(f"    → Found relevant category: {text[:50]}... ({href})")
                                    break
                            except:
                                continue
                        
                        # If we found a relevant category, navigate to it and find products there
                        if relevant_category:
                            try:
                                cat_href = relevant_category.get_attribute('href')
                                if cat_href:
                                    if cat_href.startswith('/'):
                                        cat_url = f"{self.base_url}{cat_href}"
                                    else:
                                        cat_url = cat_href
                                    
                                    if self.verbose:
                                        print(f"  [DEBUG] Navigating to category page: {cat_url}")
                                    
                                    page.goto(cat_url, wait_until="networkidle", timeout=30000)
                                    page.wait_for_timeout(2000)
                                    
                                    # Now find products on this category page (STRICT)
                                    cat_links = page.query_selector_all('a[href]')
                                    if self.verbose:
                                        print(f"  [DEBUG] Scanning {len(cat_links)} links in category...")
                                    
                                    for link in cat_links:
                                        try:
                                            href = link.get_attribute('href')
                                            if not href:
                                                continue
                                            
                                            # STRICT: Only numeric product IDs or part numbers
                                            has_numeric_id = bool(re.search(r'/products/\d+', href))
                                            has_part_num = False
                                            part_match = re.search(r'/([\dA-Z]{6,})/?$', href)
                                            if part_match and '/products/' not in href:
                                                part_str = part_match.group(1)
                                                if part_str.isupper() or sum(1 for c in part_str if c.isdigit()) >= 2:
                                                    has_part_num = True
                                            
                                            is_cat = bool(re.search(r'/products/[a-z-]+/?$', href.lower()))
                                            
                                            if (has_numeric_id or has_part_num) and not is_cat:
                                                # Make absolute URL
                                                if href.startswith('/'):
                                                    full_url = f"{self.base_url}{href}"
                                                elif href.startswith('http') and 'mcmaster.com' in href:
                                                    full_url = href
                                                else:
                                                    continue
                                                
                                                if full_url not in product_urls:
                                                    product_urls.append(full_url)
                                                    if self.verbose:
                                                        print(f"    ✓ Product in category: {full_url[:70]}...")
                                                    if len(product_urls) >= max_results:
                                                        break
                                        except:
                                            continue
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Error exploring category: {e}")
                    except Exception as e:
                        if self.verbose:
                            print(f"  [DEBUG] Error finding categories: {e}")
                
                # Now we have product URLs - create candidates from URLs
                # Extract part numbers from URLs for basic info
                candidates = []
                seen_urls = set()
                
                for url in product_urls[:max_results * 2]:
                    try:
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        # Extract part number from URL
                        part_number = None
                        part_match = re.search(r'/products/(\d+)', url)
                        if part_match:
                            part_number = part_match.group(1)
                        else:
                            part_match2 = re.search(r'/([\dA-Z]{6,})/?$', url)
                            if part_match2:
                                part_number = part_match2.group(1)
                        
                        # Basic candidate - we'll get full details when we extract
                        candidates.append({
                            'url': url,
                            'title': f"Product {part_number or 'Unknown'}",
                            'part_number': part_number,
                            'relevance_score': 1  # Will be updated during extraction
                        })
                        
                        if self.verbose:
                            print(f"    ✓ Candidate URL: {url[:70]}... (Part: {part_number or 'N/A'})")
                    except Exception as e:
                        if self.verbose:
                            print(f"  [DEBUG] Error processing URL: {e}")
                        continue
                
                # Sort candidates by relevance score (most relevant first)
                candidates.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
                candidates = candidates[:max_results]  # Take top N
                
                if self.verbose:
                    print(f"\n  [DEBUG] Found {len(candidates)} product candidates")
                    print(f"  [DEBUG] Now extracting pricing from each product...")
                
                # Now actually extract pricing from each product URL
                results = []
                for i, candidate in enumerate(candidates, 1):
                    try:
                        url = candidate.get('url')
                        if not url:
                            continue
                        
                        if self.verbose:
                            print(f"\n  [DEBUG] Extracting from product {i}/{len(candidates)}: {url[:70]}...")
                        
                        # Extract pricing from this product page
                        product_data = self.mcmaster_extract(url)
                        
                        # Merge candidate info with extracted data
                        product_data['url'] = url
                        if candidate.get('title') and not product_data.get('title'):
                            product_data['title'] = candidate['title']
                        if candidate.get('part_number') and not product_data.get('part_number'):
                            product_data['part_number'] = candidate['part_number']
                        
                        results.append(product_data)
                        
                        if self.verbose:
                            if product_data.get('title'):
                                print(f"    ✓ Extracted: {product_data.get('title', 'N/A')[:50]}...")
                            else:
                                print(f"    ⚠️  Could not extract data")
                        
                        # Small delay between extractions
                        import time
                        time.sleep(1)
                        
                    except Exception as e:
                        if self.verbose:
                            print(f"    ❌ Error extracting from {candidate.get('url', 'unknown')}: {e}")
                        continue
                
                # Save context state (cookies, session) for next time
                try:
                    import os
                    context_path = os.path.join(os.path.dirname(__file__), '.browser_context')
                    os.makedirs(context_path, exist_ok=True)
                    context.storage_state(path=os.path.join(context_path, 'state.json'))
                except:
                    pass
                
                context.close()
                browser.close()
                
            except Exception as e:
                if self.verbose:
                    print(f"  [DEBUG] Error: {e}")
                try:
                    context.close()
                    browser.close()
                except:
                    pass
                return []
        
        return results
    
    def _extract_with_scraperapi_http(self, url: str) -> Dict:
        """Extract using ScraperAPI via HTTP requests (not browser automation)."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            if self.verbose:
                print("  [DEBUG] requests/beautifulsoup4 not installed, falling back to Playwright")
            return None
        
        result = {
            'source': 'mcmaster',
            'url': url,
            'title': None,
            'part_number': None,
            'price': None,
            'unit_price': None,
            'selling_unit': 'each',
            'cost_qty_5': None,
            'cost_qty_20': None,
            'availability': None
        }
        
        # Extract part number from URL
        part_match = re.search(r'/products/(\d+)', url)
        if part_match:
            result['part_number'] = part_match.group(1)
        else:
            part_match2 = re.search(r'/([\dA-Z]+)/?$', url)
            if part_match2:
                result['part_number'] = part_match2.group(1)
        
        # Build ScraperAPI URL - try without render first (faster)
        scraperapi_url = f"http://api.scraperapi.com"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        if self.verbose:
            print(f"  [DEBUG] Fetching via ScraperAPI HTTP: {url}")
        
        # Try without render first (faster, 10-15 seconds)
        try:
            params_no_render = {
                'api_key': self.scraperapi_key,
                'url': url,
                'country_code': 'us'
            }
            if self.verbose:
                print(f"  [DEBUG] Trying without JavaScript rendering (faster)...")
            response = requests.get(scraperapi_url, params=params_no_render, timeout=30, headers=headers)
            response.raise_for_status()
            
            if self.verbose:
                print(f"  [DEBUG] ScraperAPI response status: {response.status_code}")
                print(f"  [DEBUG] Response length: {len(response.text)} chars")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check if we got actual product content (not homepage)
            page_text = soup.get_text()
            if 'BROWSE CATALOG' in page_text and len(page_text) < 5000:
                # Got homepage, need JavaScript rendering
                if self.verbose:
                    print(f"  [DEBUG] Got homepage, retrying with JavaScript rendering (slower, 30-60s)...")
                raise ValueError("Need JavaScript rendering")
            
        except (requests.exceptions.Timeout, ValueError) as e:
            # Try with render=true (slower but handles JS)
            if self.verbose:
                print(f"  [DEBUG] Retrying with render=true (JavaScript rendering)...")
            try:
                params_render = {
                    'api_key': self.scraperapi_key,
                    'url': url,
                    'render': 'true',
                    'country_code': 'us'
                }
                response = requests.get(scraperapi_url, params=params_render, timeout=90, headers=headers)
                response.raise_for_status()
                
                if self.verbose:
                    print(f"  [DEBUG] ScraperAPI (with render) response status: {response.status_code}")
                    print(f"  [DEBUG] Response length: {len(response.text)} chars")
                
                soup = BeautifulSoup(response.text, 'html.parser')
            except Exception as e2:
                if self.verbose:
                    print(f"  [DEBUG] ScraperAPI with render also failed: {e2}")
                return None
        
        # Extract title
        title_selectors = ['h1', '.product-title', '[data-product-title]', 'h2']
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title and len(title) > 5:
                    result['title'] = title
                    break
        
        # Extract price
        page_text = soup.get_text()
        price_selectors = [
            '[class*="price"]',
            '[data-price]',
            '.price'
        ]
        
        price_text = None
        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                price_text = elem.get_text(strip=True)
                if '$' in price_text:
                    break
        
        # Fallback: regex search
        if not price_text:
            price_match = re.search(r'\$([\d,]+\.?\d*)', page_text.replace(',', ''))
            if price_match:
                price_text = f"${price_match.group(1)}"
        
        if price_text:
            price_match = re.search(r'\$?([\d,]+\.?\d*)', price_text.replace(',', ''))
            if price_match:
                price_value = float(price_match.group(1))
                result['price'] = price_value
                result['unit_price'] = price_value
                result['cost_qty_5'] = price_value * 5
                result['cost_qty_20'] = price_value * 20
        
        # Extract availability
        availability_patterns = [
            r'In\s+stock',
            r'Available',
            r'Ships\s+today',
            r'Usually\s+ships'
        ]
        for pattern in availability_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                result['availability'] = match.group(0)
                break
        
        if self.verbose:
            print(f"  [DEBUG] Extracted - Title: {result['title']}, Price: {result['price']}")
        
        return result
    
    def _extract_with_selenium(self, url: str) -> Dict:
        """Extract using Selenium with real Chrome browser (better at bypassing detection)."""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
        except ImportError:
            if self.verbose:
                print("  [DEBUG] undetected-chromedriver not installed, skipping Selenium")
            return None
        
        result = {
            'source': 'mcmaster',
            'url': url,
            'title': None,
            'part_number': None,
            'price': None,
            'unit_price': None,
            'selling_unit': 'each',
            'cost_qty_5': None,
            'cost_qty_20': None,
            'availability': None
        }
        
        # Extract part number from URL
        part_match = re.search(r'/products/(\d+)', url)
        if part_match:
            result['part_number'] = part_match.group(1)
        else:
            part_match2 = re.search(r'/([\dA-Z]+)/?$', url)
            if part_match2:
                result['part_number'] = part_match2.group(1)
        
        if self.verbose:
            print(f"  [DEBUG] Using Selenium with real Chrome browser (NO ScraperAPI)")
            print(f"  [DEBUG] Browser will be VISIBLE (non-headless) - this helps bypass detection")
        
        driver = None
        try:
            # Use undetected-chromedriver (better at bypassing detection)
            # Force visible browser - headless is easier to detect
            options = uc.ChromeOptions()
            # Don't use headless - visible browser looks more human
            # if self.headless:
            #     options.add_argument('--headless=new')
            
            # More stealth options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            options.add_argument('--window-size=1920,1080')  # Normal window size
            
            # Remove automation indicators
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option("detach", True)
            
            # Set a normal user agent
            options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            if self.verbose:
                print(f"  [DEBUG] Launching Chrome browser with enhanced stealth...")
            driver = uc.Chrome(options=options, version_main=None, use_subprocess=True)
            
            # Comprehensive stealth scripts
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    // Remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Add chrome object
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Override plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                '''
            })
            
            if self.verbose:
                print(f"  [DEBUG] Navigating to: {url}")
            
            import time
            from selenium.webdriver.common.action_chains import ActionChains
            
            # Visit homepage first (like real user) - spend more time here
            try:
                if self.verbose:
                    print(f"  [DEBUG] Visiting homepage first to establish session...")
                driver.get(self.base_url)
                time.sleep(3)  # Wait longer on homepage
                
                # Simulate human behavior - move mouse, scroll
                try:
                    actions = ActionChains(driver)
                    actions.move_by_offset(100, 100).perform()
                    time.sleep(0.5)
                    driver.execute_script("window.scrollTo(0, 200)")
                    time.sleep(1)
                except:
                    pass
            except Exception as e:
                if self.verbose:
                    print(f"  [DEBUG] Homepage visit failed: {e}")
            
            # Navigate to product page
            if self.verbose:
                print(f"  [DEBUG] Navigating to product page...")
            driver.get(url)
            time.sleep(3)  # Wait longer for page to load
            
            # Simulate human reading behavior
            try:
                actions = ActionChains(driver)
                actions.move_by_offset(400, 300).perform()
                time.sleep(0.8)
            except:
                pass
            
            # Scroll slowly like a human
            driver.execute_script("window.scrollTo(0, 300)")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 600)")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # Extra wait for dynamic content
            
            if self.verbose:
                page_title = driver.title
                current_url = driver.current_url
                page_source_snippet = driver.page_source[:500] if len(driver.page_source) > 500 else driver.page_source
                print(f"  [DEBUG] Page title: {page_title}")
                print(f"  [DEBUG] Current URL: {current_url[:100]}...")
                
                # Check if we got blocked or redirected
                if 'access' in page_title.lower() and 'restricted' in page_title.lower():
                    print(f"  [DEBUG] ⚠️  Possible access restriction detected")
                if 'mcmaster' not in page_title.lower() and 'mcmaster' not in current_url.lower():
                    print(f"  [DEBUG] ⚠️  May have been redirected away from McMaster")
            
            # Get page text for analysis
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Check if we got blocked or asked to login
            login_keywords = ['log in', 'please log in', 'sign in', 'continue browsing', 'please log']
            if any(keyword in page_text.lower() for keyword in login_keywords):
                if self.verbose:
                    print(f"  [DEBUG] ⚠️  McMaster is asking for login - automation detected")
                    print(f"  [DEBUG] Page content indicates login required")
                result['error'] = 'Login required - automation detected by McMaster'
                return result
            
            # Check if we got the homepage instead of product page
            if 'BROWSE CATALOG' in page_text and len(page_text) < 10000:
                if self.verbose:
                    print(f"  [DEBUG] ⚠️  Got homepage instead of product page - may be blocked")
                result['error'] = 'Redirected to homepage - may be blocked'
                return result
            
            # Extract title - try multiple strategies
            title_selectors = [
                'h1',
                'h1[class*="product"]',
                'h1[class*="title"]',
                '.product-title',
                '[data-product-title]',
                'h2',
                'h2[class*="product"]'
            ]
            
            for selector in title_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem and elem.is_displayed():
                        title = elem.text.strip()
                        # Reject login prompts, homepage, and other non-product titles
                        if (title and len(title) > 5 and 
                            'BROWSE CATALOG' not in title and
                            'log in' not in title.lower() and
                            'please log in' not in title.lower() and
                            'sign in' not in title.lower() and
                            'continue browsing' not in title.lower()):
                            result['title'] = title
                            if self.verbose:
                                print(f"  [DEBUG] Found title using '{selector}': {title[:60]}...")
                            break
                except (NoSuchElementException, Exception):
                    continue
            
            # If no title found, try getting first h1 or main heading
            if not result['title']:
                try:
                    h1_elements = driver.find_elements(By.TAG_NAME, "h1")
                    for h1 in h1_elements:
                        if h1.is_displayed():
                            title = h1.text.strip()
                            # Reject login prompts
                            if (title and len(title) > 5 and 
                                'BROWSE CATALOG' not in title and
                                'log in' not in title.lower() and
                                'please log in' not in title.lower() and
                                'sign in' not in title.lower() and
                                'continue browsing' not in title.lower()):
                                result['title'] = title
                                if self.verbose:
                                    print(f"  [DEBUG] Found title from first h1: {title[:60]}...")
                                break
                except:
                    pass
            
            # Extract price - try multiple strategies
            price_selectors = [
                '[class*="price"]',
                '[data-price]',
                '.price',
                '[class*="Price"]',
                '[id*="price"]',
                'span[class*="price"]',
                'div[class*="price"]'
            ]
            
            price_text = None
            for selector in price_selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        if elem.is_displayed():
                            text = elem.text.strip()
                            if '$' in text and len(text) < 50:  # Price should be short
                                price_text = text
                                if self.verbose:
                                    print(f"  [DEBUG] Found price using '{selector}': {price_text}")
                                break
                    if price_text:
                        break
                except (NoSuchElementException, Exception):
                    continue
            
            # Fallback: regex search in page text
            if not price_text:
                price_match = re.search(r'\$([\d,]+\.?\d*)', page_text.replace(',', ''))
                if price_match:
                    price_text = f"${price_match.group(1)}"
            
            if price_text:
                price_match = re.search(r'\$?([\d,]+\.?\d*)', price_text.replace(',', ''))
                if price_match:
                    price_value = float(price_match.group(1))
                    result['price'] = price_value
                    result['unit_price'] = price_value
                    result['cost_qty_5'] = price_value * 5
                    result['cost_qty_20'] = price_value * 20
            
            # Extract availability
            availability_patterns = [
                r'In\s+stock',
                r'Available',
                r'Ships\s+today',
                r'Usually\s+ships'
            ]
            for pattern in availability_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    result['availability'] = match.group(0)
                    break
            
            if self.verbose:
                print(f"  [DEBUG] Extracted - Title: {result['title']}, Price: {result['price']}")
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"  [DEBUG] Selenium extraction failed: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def mcmaster_extract(self, url: str) -> Dict:
        """Extract pricing from McMaster product page."""
        # Try Selenium first (real browser, better at bypassing detection)
        # Skip ScraperAPI when using Selenium - use pure Selenium
        selenium_result = self._extract_with_selenium(url)
        if selenium_result and selenium_result.get('title'):
            return selenium_result
        
        # If Selenium failed and ScraperAPI is enabled, try HTTP method
        if self.use_scraperapi:
            if self.verbose:
                print(f"  [DEBUG] Selenium failed, trying ScraperAPI HTTP...")
            http_result = self._extract_with_scraperapi_http(url)
            if http_result and http_result.get('title'):
                return http_result
            # Fall through to Playwright if HTTP method fails
        
        result = {
            'source': 'mcmaster',
            'url': url,
            'part_number': None,
            'title': None,
            'price': None,
            'unit_price': None,
            'selling_unit': None,
            'pack_qty': None,
            'cost_qty_5': None,
            'cost_qty_20': None,
            'availability': None
        }
        
        with sync_playwright() as p:
            # Enhanced stealth settings (same as search)
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials'
                ]
            )
            
            # Use persistent context to maintain cookies/session
            # BUT: Sometimes start fresh to avoid flagged sessions
            import os
            import random
            context_path = os.path.join(os.path.dirname(__file__), '.browser_context')
            os.makedirs(context_path, exist_ok=True)
            state_file = os.path.join(context_path, 'state.json')
            
            # Sometimes start fresh (30% chance) to avoid using flagged sessions
            use_old_state = os.path.exists(state_file) and random.random() > 0.3
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                # Store cookies/session (but sometimes start fresh)
                storage_state=state_file if use_old_state else None,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                    'Referer': self.base_url
                }
            )
            
            page = context.new_page()
            
            # Apply stealth plugin if available
            if HAS_STEALTH:
                if self.verbose:
                    print(f"  [DEBUG] Applying playwright-stealth...")
                stealth_sync(page)
            
            # Comprehensive stealth script
            page.add_init_script("""
                // Mask webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Add chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mask plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mask languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // WebGL vendor
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.call(this, parameter);
                };
                
                // Battery API
                Object.defineProperty(navigator, 'getBattery', {
                    get: () => {
                        return () => Promise.resolve({
                            charging: true,
                            chargingTime: 0,
                            dischargingTime: Infinity,
                            level: 1
                        });
                    }
                });
            """)
            
            try:
                # Skip login - pricing visible without login
                # (Login disabled - not needed)
                if False and self.email and self.password:
                    if self.verbose:
                        print(f"  [DEBUG] Logging in to McMaster...")
                    page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # Look for login button/link
                    login_selectors = [
                        'a:has-text("Sign In")',
                        'a:has-text("Login")',
                        'a[href*="login"]',
                        'a[href*="signin"]',
                        'button:has-text("Sign In")',
                        '[data-testid*="login"]',
                        '[class*="login"]'
                    ]
                    
                    login_clicked = False
                    for selector in login_selectors:
                        try:
                            login_btn = page.query_selector(selector)
                            if login_btn and login_btn.is_visible():
                                if self.verbose:
                                    print(f"  [DEBUG] Found login button, clicking...")
                                login_btn.click()
                                page.wait_for_timeout(2000)
                                login_clicked = True
                                break
                        except:
                            continue
                    
                    if login_clicked or 'login' in page.url.lower() or 'signin' in page.url.lower():
                        # Wait for login form to load
                        page.wait_for_timeout(2000)
                        
                        # Fill in email - try multiple approaches
                        email_filled = False
                        email_selectors = [
                            'input[type="email"]',
                            'input[name*="email" i]',
                            'input[id*="email" i]',
                            'input[name*="user" i]',
                            'input[id*="user" i]',
                            'input[name*="username" i]',
                            'input[id*="username" i]',
                            '#email',
                            '#username',
                            'input[placeholder*="email" i]',
                            'input[placeholder*="Email" i]',
                            'input[autocomplete="email"]',
                            'input[autocomplete="username"]'
                        ]
                        
                        for selector in email_selectors:
                            try:
                                email_field = page.query_selector(selector)
                                if email_field and email_field.is_visible():
                                    email_field.click()
                                    page.wait_for_timeout(300)
                                    email_field.fill(self.email)
                                    page.wait_for_timeout(300)
                                    if self.verbose:
                                        print(f"  [DEBUG] Entered email using: {selector}")
                                    email_filled = True
                                    break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Email selector {selector} failed: {e}")
                                continue
                        
                        if not email_filled:
                            # Try to find any text input that might be email field
                            try:
                                all_inputs = page.query_selector_all('input[type="text"], input:not([type])')
                                for inp in all_inputs:
                                    if inp.is_visible():
                                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                                        name = (inp.get_attribute('name') or '').lower()
                                        inp_id = (inp.get_attribute('id') or '').lower()
                                        if 'email' in placeholder or 'email' in name or 'email' in inp_id or 'user' in placeholder or 'user' in name:
                                            inp.click()
                                            page.wait_for_timeout(300)
                                            inp.fill(self.email)
                                            if self.verbose:
                                                print(f"  [DEBUG] Entered email in field: {placeholder or name or inp_id}")
                                            email_filled = True
                                            break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Fallback email search failed: {e}")
                        
                        page.wait_for_timeout(500)
                        
                        # Fill in password
                        password_filled = False
                        password_selectors = ['input[type="password"]', 'input[name*="password"]', 'input[id*="password"]', '#password']
                        for selector in password_selectors:
                            try:
                                password_field = page.query_selector(selector)
                                if password_field and password_field.is_visible():
                                    password_field.click()
                                    page.wait_for_timeout(300)
                                    password_field.fill(self.password)
                                    if self.verbose:
                                        print(f"  [DEBUG] Entered password using: {selector}")
                                    password_filled = True
                                    break
                            except Exception as e:
                                if self.verbose:
                                    print(f"  [DEBUG] Password selector {selector} failed: {e}")
                                continue
                        
                        page.wait_for_timeout(500)
                        
                        # Click submit/sign in button
                        submit_selectors = [
                            'button[type="submit"]',
                            'button:has-text("Sign In")',
                            'button:has-text("Log In")',
                            'input[type="submit"]',
                            'button[class*="submit"]'
                        ]
                        for selector in submit_selectors:
                            try:
                                submit_btn = page.query_selector(selector)
                                if submit_btn:
                                    submit_btn.click()
                                    if self.verbose:
                                        print(f"  [DEBUG] Clicked submit")
                                    break
                            except:
                                continue
                        
                        # Wait for login to complete
                        page.wait_for_timeout(3000)
                        page.wait_for_load_state("networkidle", timeout=10000)
                
                if self.verbose:
                    print(f"  [DEBUG] Loading product page: {url}")
                
                # Visit homepage first to establish session (like real user)
                try:
                    homepage_url = self._get_url(self.base_url) if self.use_scraperapi else self.base_url
                    page.goto(homepage_url, wait_until="domcontentloaded", timeout=60000 if self.use_scraperapi else 30000)
                    page.wait_for_timeout(1500)
                    page.mouse.move(400, 400)
                    page.wait_for_timeout(500)
                except:
                    pass
                
                # Navigate like a real user (use ScraperAPI if enabled)
                actual_url = self._get_url(url) if self.use_scraperapi else url
                if self.verbose:
                    print(f"  [DEBUG] Navigating to: {actual_url[:100]}...")
                page.goto(actual_url, wait_until="domcontentloaded", timeout=60000 if self.use_scraperapi else 30000)
                
                # Simulate human behavior
                page.mouse.move(400, 400)
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                page.wait_for_timeout(800)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)
                
                # Wait for full load
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                
                # Debug: Check what page we actually got
                if self.verbose:
                    page_title = page.title()
                    page_url = page.url
                    page_text_snippet = page.inner_text('body')[:200]
                    print(f"  [DEBUG] Page title: {page_title}")
                    print(f"  [DEBUG] Current URL: {page_url[:100]}...")
                    print(f"  [DEBUG] Page content snippet: {page_text_snippet}...")
                    
                    # Check for ScraperAPI errors
                    if 'scraperapi' in page_url.lower() or 'api.scraperapi.com' in page_url:
                        print(f"  [DEBUG] ⚠️  Still on ScraperAPI URL - may indicate redirect issue")
                    if 'error' in page_text_snippet.lower() or 'blocked' in page_text_snippet.lower() or 'access denied' in page_text_snippet.lower():
                        print(f"  [DEBUG] ⚠️  Possible error/block message detected in page")
                
                # Handle cookie banners if present
                try:
                    cookie_selectors = [
                        'button:has-text("Accept")',
                        'button:has-text("I Accept")',
                        'button:has-text("OK")',
                        '[id*="cookie"] button',
                        '[class*="cookie"] button',
                        'button[aria-label*="Accept" i]'
                    ]
                    for selector in cookie_selectors:
                        try:
                            cookie_btn = page.query_selector(selector)
                            if cookie_btn and cookie_btn.is_visible():
                                cookie_btn.click()
                                page.wait_for_timeout(500)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Extract part number from URL - McMaster URLs can be /products/123 or /123456/ or /97083A490/
                part_match = re.search(r'/products/(\d+)', url)
                if part_match:
                    result['part_number'] = part_match.group(1)
                else:
                    # Try format like /97083A490/ (alphanumeric at end of URL)
                    part_match2 = re.search(r'/([\dA-Z]+)/?$', url)
                    if part_match2:
                        result['part_number'] = part_match2.group(1)
                        if self.verbose:
                            print(f"  [DEBUG] Extracted part number from URL: {result['part_number']}")
                
                # Extract title
                title_selectors = ['h1', '.product-title', '[data-product-title]', 'h2']
                for selector in title_selectors:
                    try:
                        elem = page.query_selector(selector)
                        if elem:
                            title = elem.inner_text().strip()
                            if title and len(title) > 5:
                                result['title'] = title
                                break
                    except:
                        continue
                
                # Extract price - McMaster usually shows price clearly
                price_selectors = [
                    '[class*="price"]',
                    '[data-price]',
                    '.price',
                    r'text=/\$[\d,]+\.?\d*/'
                ]
                
                page_text = page.inner_text('body')
                price_text = None
                
                for selector in price_selectors:
                    try:
                        elem = page.query_selector(selector)
                        if elem:
                            price_text = elem.inner_text().strip()
                            if '$' in price_text:
                                break
                    except:
                        continue
                
                # Fallback: regex search in page text
                if not price_text:
                    price_match = re.search(r'\$([\d,]+\.?\d*)', page_text.replace(',', ''))
                    if price_match:
                        price_text = f"${price_match.group(1)}"
                
                if price_text:
                    price_match = re.search(r'\$?([\d,]+\.?\d*)', price_text.replace(',', ''))
                    if price_match:
                        price_value = float(price_match.group(1))
                        result['price'] = price_value
                        result['unit_price'] = price_value
                        result['selling_unit'] = 'each'  # McMaster usually sells as each
                        
                        # Compute costs
                        result['cost_qty_5'] = price_value * 5
                        result['cost_qty_20'] = price_value * 20
                
                # Extract availability
                availability_patterns = [
                    r'In\s+stock',
                    r'Available',
                    r'Ships\s+today',
                    r'Usually\s+ships'
                ]
                for pattern in availability_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        result['availability'] = match.group(0)
                        break
                
                # Save context state (cookies, session) for next time
                try:
                    import os
                    context_path = os.path.join(os.path.dirname(__file__), '.browser_context')
                    os.makedirs(context_path, exist_ok=True)
                    context.storage_state(path=os.path.join(context_path, 'state.json'))
                except:
                    pass
                
                context.close()
                browser.close()
                
            except Exception as e:
                if self.verbose:
                    print(f"  [DEBUG] Error: {e}")
                result['error'] = str(e)
                try:
                    context.close()
                    browser.close()
                except:
                    pass
        
        return result
    
    def search_and_extract(self, query: str, return_top_n: int = 3) -> Dict:
        """Search and extract pricing."""
        if self.verbose:
            print(f"Searching McMaster for: {query}")
        
        candidates = self.mcmaster_search(query, max_results=5)
        
        if not candidates:
            return {
                'query': query,
                'best_match': None,
                'alternatives': [],
                'error': 'No results found'
            }
        
        if self.verbose:
            print(f"Found {len(candidates)} candidates")
        
        # Extract from top candidates
        results = []
        for candidate in candidates[:return_top_n]:
            if self.verbose:
                print(f"Extracting from: {candidate['url']}")
            extracted = self.mcmaster_extract(candidate['url'])
            results.append(extracted)
        
        best_match = results[0] if results else None
        alternatives = results[1:] if len(results) > 1 else []
        
        return {
            'query': query,
            'best_match': best_match,
            'alternatives': alternatives
        }


if __name__ == "__main__":
    tool = McMasterPricingTool(headless=False, verbose=True)
    result = tool.search_and_extract("disposable gloves", return_top_n=2)
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(json.dumps(result, indent=2))

