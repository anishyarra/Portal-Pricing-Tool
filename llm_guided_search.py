#!/usr/bin/env python3
"""
LLM-Guided Search - Uses AI vision to analyze pages and navigate intelligently.

Takes a product name, uses LLM to analyze screenshots of McMaster pages,
decides which product to click, navigates there, and extracts part numbers.
"""

import sys
import re
import time
import base64
import json
from typing import List, Dict, Optional
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

def take_screenshot(driver, filename: str = "screenshot.png") -> str:
    """Take screenshot and return base64 encoded image."""
    import os
    # Save to organized folder
    screenshot_dir = os.path.join(os.path.dirname(__file__), 'outputs', 'screenshots')
    os.makedirs(screenshot_dir, exist_ok=True)
    filepath = os.path.join(screenshot_dir, filename)
    driver.save_screenshot(filepath)
    
    # Read and encode
    with open(filepath, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_page_text_summary(driver) -> str:
    """Get a text summary of the current page."""
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        # Get first 2000 chars
        return page_text[:2000]
    except:
        return ""

def analyze_page_with_llm(query: str, screenshot_b64: str, page_text: str, current_url: str, api_key: str) -> Dict:
    """Use LLM to analyze the page and decide what to click."""
    if not HAS_OPENAI:
        return {'error': 'OpenAI not installed. Run: pip install openai'}
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""You are analyzing a McMaster-Carr product search page.

User is searching for: "{query}"
Current URL: {current_url}

Page text summary:
{page_text[:1000]}

Look at the screenshot and page text. Your job is to:
1. Identify the page type:
   - "category": Multiple product categories/cards
   - "table": Product listing table with part numbers and prices in columns
   - "product": Individual product detail page

2. Based on page type:
   - If "category": Find the product category/card that BEST matches "{query}"
   - If "table": 
     * Look at the PRODUCT TABLE ROWS (not headers, not popups)
     * Find the row that BEST matches "{query}" based on:
       - Product description/specifications in that row
       - Part numbers in "Pkg." and "Each" columns
       - Prices shown
     * Extract the part number from the "Each" column (individual unit price) - this is usually the main product part number
     * If "Each" column has no part number, use the "Pkg." column part number
     * DO NOT extract part numbers from popups or overlays - only from the table rows
   - If "product": Extract the part number and pricing

3. IMPORTANT RULES for table pages:
   - Only look at the main product table (left side, background)
   - Ignore popup widgets, overlays, or side panels
   - Part numbers are in columns labeled "Pkg." and "Each"
   - Pick the row that best matches the search query "{query}"
   - Extract the part number from that specific row
   - Format: alphanumeric like 97083A490, 97077A160, etc.

Return JSON with:
- "page_type": "category", "table", or "product"
- "action": "click" or "extract"
- "target_text": Text to find (product name, part number, or price cell text)
- "part_number": Part number from the matching table row (from "Each" column if available, else "Pkg." column)
- "price": Price from that row if visible
- "reasoning": Why you chose this specific row and part number
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # or "gpt-4-vision-preview" if available
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800
        )
        
        result_text = response.choices[0].message.content
        
        # Try to extract JSON
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            # Fallback: parse text response
            return {
                'page_type': 'category' if 'category' in result_text.lower() else 'product',
                'action': 'click' if 'click' in result_text.lower() else 'extract',
                'reasoning': result_text
            }
    except Exception as e:
        return {'error': str(e)}

def find_element_by_text(driver, target_text: str, verbose: bool = True) -> Optional:
    """Find clickable element containing the target text."""
    try:
        # Try multiple strategies
        strategies = [
            (By.XPATH, f"//a[contains(text(), '{target_text}')]"),
            (By.XPATH, f"//*[contains(text(), '{target_text}')]/ancestor::a"),
            (By.CSS_SELECTOR, f'a:contains("{target_text}")'),
        ]
        
        for by, selector in strategies:
            try:
                elements = driver.find_elements(by, selector)
                for elem in elements:
                    if target_text.lower() in elem.text.lower():
                        if verbose:
                            print(f"    ✅ Found element: {elem.text[:60]}...")
                        return elem
            except:
                continue
        
        # Fallback: search all links
        all_links = driver.find_elements(By.TAG_NAME, "a")
        for link in all_links:
            if target_text.lower() in link.text.lower():
                if verbose:
                    print(f"    ✅ Found link: {link.text[:60]}...")
                return link
        
        return None
    except Exception as e:
        if verbose:
            print(f"    ⚠️  Error finding element: {e}")
        return None

def llm_guided_search(query: str, driver, api_key: str, max_depth: int = 3, verbose: bool = True) -> List[Dict]:
    """Use LLM to intelligently navigate and find products."""
    if not HAS_OPENAI:
        print("❌ Error: OpenAI not installed. Run: pip install openai")
        return []
    
    results = []
    visited_urls = set()
    depth = 0
    
    try:
        # Step 1: Search McMaster
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.mcmaster.com/{encoded_query}"
        
        if verbose:
            print(f"\n🔍 Searching for: {query}")
            print(f"   URL: {search_url}")
        
        driver.get(search_url)
        time.sleep(4)
        
        while depth < max_depth:
            depth += 1
            current_url = driver.current_url
            
            # Normalize URL (remove query params, fragments, trailing slashes)
            normalized_url = current_url.split('?')[0].split('#')[0].rstrip('/')
            
            if normalized_url in visited_urls:
                if verbose:
                    print(f"  ⚠️  Already visited this URL, extracting from current page...")
                # Try to extract from current page before stopping
                try:
                    page_text_full = driver.find_element(By.TAG_NAME, "body").text
                    # Look for part numbers in table
                    part_numbers = re.findall(r'\b([\d]{4,}[A-Z]+[\d]*|[A-Z]+[\d]{4,})\b', page_text_full)
                    for pn in part_numbers:
                        if len(pn) >= 6 and pn not in [r.get('part_number') for r in results]:
                            results.append({
                                'part_number': pn,
                                'url': current_url,
                                'title': 'N/A',
                                'query': query
                            })
                            if verbose:
                                print(f"  ✅ Extracted part number: {pn}")
                            break
                except:
                    pass
                break
            
            visited_urls.add(normalized_url)
            
            if verbose:
                print(f"\n  [Depth {depth}] Analyzing page: {current_url[:80]}...")
            
            # Take screenshot (saved to outputs/screenshots/)
            timestamp = int(time.time())
            safe_query = query.replace(' ', '_').replace('/', '_')[:30]
            screenshot_b64 = take_screenshot(driver, f"{safe_query}_depth_{depth}_{timestamp}.png")
            page_text = get_page_text_summary(driver)
            
            # Analyze with LLM
            if verbose:
                print("  🤖 Asking LLM to analyze page...")
            
            analysis = analyze_page_with_llm(query, screenshot_b64, page_text, current_url, api_key)
            
            if 'error' in analysis:
                if verbose:
                    print(f"  ❌ LLM error: {analysis['error']}")
                break
            
            if verbose:
                print(f"  📊 LLM says: {analysis.get('reasoning', 'No reasoning provided')}")
            
            # Act on LLM's decision
            if analysis.get('page_type') == 'product' and analysis.get('action') == 'extract':
                # Extract part number
                part_number = analysis.get('part_number')
                price = analysis.get('price')
                
                if not part_number:
                    # Try to extract from URL
                    part_match = re.search(r'/([\dA-Z]+)/?$', current_url)
                    if part_match:
                        part_number = part_match.group(1)
                
                if not part_number:
                    # Try to extract from page
                    try:
                        page_text_full = driver.find_element(By.TAG_NAME, "body").text
                        # Look for "Part #" or part number patterns
                        part_match = re.search(r'Part\s*#\s*:?\s*([\dA-Z]+)', page_text_full, re.IGNORECASE)
                        if part_match:
                            part_number = part_match.group(1)
                        # Also try finding part numbers in the page
                        if not part_number:
                            part_match = re.search(r'\b([\d]{4,}[A-Z]+[\d]*|[A-Z]+[\d]{4,})\b', page_text_full)
                            if part_match:
                                potential = part_match.group(1)
                                if len(potential) >= 6:  # McMaster part numbers are usually 6+ chars
                                    part_number = potential
                    except:
                        pass
                
                # Extract price if not already found
                if not price:
                    try:
                        page_text_full = driver.find_element(By.TAG_NAME, "body").text
                        price_match = re.search(r'\$([\d,]+\.?\d*)', page_text_full.replace(',', ''))
                        if price_match:
                            price = float(price_match.group(1))
                    except:
                        pass
                
                if part_number:
                    # Get title
                    title = None
                    try:
                        h1 = driver.find_element(By.TAG_NAME, "h1")
                        title = h1.text.strip()
                    except:
                        pass
                    
                    results.append({
                        'part_number': part_number,
                        'url': current_url,
                        'title': title or 'N/A',
                        'price': price,
                        'query': query
                    })
                    
                    if verbose:
                        print(f"  ✅ Found product!")
                        print(f"     Part #: {part_number}")
                        print(f"     Title: {title[:60] if title else 'N/A'}...")
                        if price:
                            print(f"     Price: ${price}")
                    
                    # Found a product, can stop or continue to find more
                    break
                else:
                    if verbose:
                        print(f"  ⚠️  Could not extract part number")
            
            elif analysis.get('page_type') == 'table':
                # On a product table - LLM should have identified a part number
                part_number = analysis.get('part_number')
                price = analysis.get('price')
                
                if part_number:
                    if verbose:
                        print(f"  📊 LLM found part number: {part_number}")
                        print(f"  🔍 Verifying it's in the table...")
                    
                    # Verify the part number is actually in a table row (not popup/overlay)
                    part_number_valid = False
                    title = None
                    try:
                        # Find row containing the part number - must be in a <tr> (table row)
                        part_elem = driver.find_element(By.XPATH, f"//*[contains(text(), '{part_number}')]")
                        row = part_elem.find_element(By.XPATH, './ancestor::tr')
                        
                        # Verify it's actually in the main table (not a popup)
                        # Check if the row is in a table (not in a popup/modal)
                        table = row.find_element(By.XPATH, './ancestor::table')
                        row_text = row.text
                        
                        # Make sure part number appears in the row text
                        if part_number in row_text:
                            part_number_valid = True
                            if verbose:
                                print(f"  ✅ Verified part number is in table row")
                        
                            # Get row text for title/description
                            # Try to extract product description from row
                            if row_text:
                                # Get first meaningful text (skip part number, prices)
                                parts = row_text.split()
                                for i, part in enumerate(parts):
                                    if part == part_number and i > 0:
                                        # Get text before part number as description
                                        title = ' '.join(parts[:i])[:100]
                                        break
                            
                            # Extract price from row if not already found
                            if not price:
                                try:
                                    price_cells = row.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                                    for price_cell in price_cells:
                                        price_text = price_cell.text
                                        price_match = re.search(r'\$([\d,]+\.?\d*)', price_text.replace(',', ''))
                                        if price_match:
                                            price = float(price_match.group(1))
                                            break
                                except:
                                    pass
                    except Exception as e:
                        if verbose:
                            print(f"  ⚠️  Could not verify part number in table: {e}")
                        part_number_valid = False
                    
                    if part_number_valid:
                        # Save the part number directly from table (no need to click)
                        results.append({
                            'part_number': part_number,
                            'url': current_url,
                            'title': title or 'N/A',
                            'price': price,
                            'query': query
                        })
                        
                        if verbose:
                            print(f"  ✅ Extracted from table!")
                            print(f"     Part #: {part_number}")
                            if price:
                                print(f"     Price: ${price}")
                        
                        # Found a product, can stop or continue to find more
                        break
                    else:
                        if verbose:
                            print(f"  ⚠️  Part number {part_number} not found in table - LLM may have extracted from popup")
                        # Try to extract from table directly as fallback
                        try:
                            page_text_full = driver.find_element(By.TAG_NAME, "body").text
                            # Look for part numbers in table format
                            # McMaster tables usually have part numbers in specific columns
                            table_rows = driver.find_elements(By.CSS_SELECTOR, 'table tr, [class*="table"] tr')
                            for tr in table_rows[:20]:  # Check first 20 rows
                                row_text = tr.text
                                # Look for part number patterns in row
                                part_numbers = re.findall(r'\b([\d]{4,}[A-Z]+[\d]*|[A-Z]+[\d]{4,})\b', row_text)
                                for pn in part_numbers:
                                    if len(pn) >= 6 and pn not in [r.get('part_number') for r in results]:
                                        # Check if this row matches the query better
                                        if any(word.lower() in row_text.lower() for word in query.split()):
                                            results.append({
                                                'part_number': pn,
                                                'url': current_url,
                                                'title': row_text[:100],
                                                'query': query
                                            })
                                            if verbose:
                                                print(f"  ✅ Extracted alternative part number from table: {pn}")
                                            break
                                if results:
                                    break
                        except:
                            pass
                        break
                else:
                    if verbose:
                        print(f"  ⚠️  LLM found table but no part number")
                    # Try to extract part numbers from table directly
                    try:
                        page_text_full = driver.find_element(By.TAG_NAME, "body").text
                        # Look for part number patterns in table
                        part_numbers = re.findall(r'\b([\d]{4,}[A-Z]+[\d]*|[A-Z]+[\d]{4,})\b', page_text_full)
                        if part_numbers:
                            # Take first reasonable part number
                            for pn in part_numbers:
                                if len(pn) >= 6:  # McMaster part numbers are usually 6+ chars
                                    results.append({
                                        'part_number': pn,
                                        'url': current_url,
                                        'title': 'N/A',
                                        'query': query
                                    })
                                    if verbose:
                                        print(f"  ✅ Extracted part number: {pn}")
                                    break
                    except:
                        pass
                    break
            
            elif analysis.get('page_type') in ['category', 'table'] and analysis.get('action') == 'click':
                # Find and click the recommended product
                target_text = analysis.get('target_text', '')
                
                if not target_text:
                    if verbose:
                        print(f"  ⚠️  LLM didn't specify what to click")
                    break
                
                if verbose:
                    print(f"  🖱️  Looking for: '{target_text}'")
                
                element = find_element_by_text(driver, target_text, verbose)
                
                if element:
                    try:
                        # Get the URL before clicking
                        href = element.get_attribute('href')
                        if href:
                            if verbose:
                                print(f"  🔗 Clicking: {href}")
                            
                            # Navigate to the link
                            if href.startswith('http'):
                                driver.get(href)
                            elif href.startswith('/'):
                                driver.get(f"https://www.mcmaster.com{href}")
                            else:
                                element.click()
                            
                            time.sleep(3)
                            continue
                        else:
                            # Try clicking the element directly
                            driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.5)
                            element.click()
                            time.sleep(3)
                            continue
                    except Exception as e:
                        if verbose:
                            print(f"  ❌ Error clicking: {e}")
                        # Try alternative: look for price cells or "view description" links near the target
                        try:
                            if verbose:
                                print(f"  🔄 Trying alternative click method...")
                            # Look for price cells ($) or links near the target text
                            price_cells = driver.find_elements(By.XPATH, 
                                f"//*[contains(text(), '{target_text}')]/ancestor::tr//*[contains(text(), '$')]")
                            if price_cells:
                                price_cells[0].click()
                                time.sleep(3)
                                continue
                        except:
                            pass
                        break
                else:
                    if verbose:
                        print(f"  ⚠️  Could not find element to click")
                    break
            else:
                if verbose:
                    print(f"  ⚠️  Unknown action from LLM")
                break
        
        return results
        
    except Exception as e:
        if verbose:
            print(f"  ❌ Error: {e}")
        return results

def main():
    if not HAS_SELENIUM:
        print("❌ Error: selenium not installed. Run: pip install selenium")
        return
    
    if not HAS_OPENAI:
        print("❌ Error: OpenAI not installed. Run: pip install openai")
        print("   Then set your API key: export OPENAI_API_KEY='your-key'")
        return
    
    import os
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        print("   Set it: export OPENAI_API_KEY='your-key'")
        return
    
    if len(sys.argv) < 2:
        print("Usage: python3 llm_guided_search.py '<product name>'")
        print("\nExample:")
        print("  python3 llm_guided_search.py 'shallow female-threaded anchors'")
        print("\nRequirements:")
        print("  1. OpenAI API key: export OPENAI_API_KEY='your-key'")
        print("  2. OpenAI package: pip install openai")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    print("="*80)
    print("LLM-GUIDED SEARCH")
    print("="*80)
    print(f"\nSearching for: {query}")
    print("\nThis uses AI vision to:")
    print("  1. Analyze the page screenshot")
    print("  2. Decide which product to click")
    print("  3. Navigate intelligently")
    print("  4. Extract part numbers")
    print("\nThe browser will open and AI will guide navigation.\n")
    
    input("Press ENTER to start (browser will open)...\n")
    
    driver = None
    try:
        # Launch browser
        if HAS_UC:
            print("  [DEBUG] Using undetected-chromedriver...")
            options = uc.ChromeOptions()
            driver = uc.Chrome(options=options, version_main=None)
        else:
            print("  [DEBUG] Using regular Selenium Chrome...")
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            driver = webdriver.Chrome(options=options)
        
        # Visit homepage first
        print("  [DEBUG] Visiting McMaster homepage...")
        driver.get("https://www.mcmaster.com")
        time.sleep(2)
        
        # LLM-guided search
        results = llm_guided_search(query, driver, api_key, max_depth=3, verbose=True)
        
        if results:
            # Save results to organized folder
            import os
            results_dir = os.path.join(os.path.dirname(__file__), 'outputs', 'results')
            os.makedirs(results_dir, exist_ok=True)
            output_file = os.path.join(results_dir, f"llm_search_{query.replace(' ', '_')[:30]}.txt")
            
            with open(output_file, 'w') as f:
                for r in results:
                    f.write(f"{r['part_number']}\n")
            
            print("\n" + "="*80)
            print("RESULTS")
            print("="*80)
            for i, r in enumerate(results, 1):
                print(f"{i}. Part #: {r['part_number']}")
                print(f"   Title: {r['title'][:70]}...")
                print(f"   URL: {r['url']}")
                print()
            
            print(f"💾 Part numbers saved to: {output_file}")
            print(f"   You can now run: python3 batch_extract.py {output_file}")
        else:
            print("\n❌ No products found")
        
        # Keep browser open
        print("\nBrowser will close in 5 seconds...")
        time.sleep(5)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    main()

