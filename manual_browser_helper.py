#!/usr/bin/env python3
"""
Manual Browser Helper - You navigate, script extracts.

This is the MOST RELIABLE method - you manually navigate to the product page,
then the script extracts the data from the page you're viewing.
"""

import re
import time
from typing import Dict
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

# Try undetected-chromedriver as fallback
try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

def extract_from_current_page(driver, url: str, verbose: bool = True) -> Dict:
    """Extract data from the page the browser is currently on."""
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
    
    # Extract part number
    part_match = re.search(r'/([\dA-Z]+)/?$', url)
    if part_match:
        result['part_number'] = part_match.group(1)
    
    try:
        # Get current page
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Extract title
        try:
            h1 = driver.find_element(By.TAG_NAME, "h1")
            title = h1.text.strip()
            if title and 'log in' not in title.lower() and 'please log' not in title.lower():
                result['title'] = title
        except:
            pass
        
        # Extract price - look for "per each", "each", or individual unit price
        # Try to find price that's clearly per unit, not per pack
        price_text = page_text
        
        # Look for patterns like "$X.XX / each" or "$X.XX each" or "each: $X.XX"
        each_price_patterns = [
            r'\$([\d,]+\.?\d*)\s*/\s*each',
            r'\$([\d,]+\.?\d*)\s+each',
            r'each[:\s]+\$([\d,]+\.?\d*)',
            r'per\s+each[:\s]+\$([\d,]+\.?\d*)',
        ]
        
        price_value = None
        for pattern in each_price_patterns:
            match = re.search(pattern, price_text, re.IGNORECASE)
            if match:
                price_value = float(match.group(1).replace(',', ''))
                if verbose:
                    print(f"  [DEBUG] Found per-unit price: ${price_value}")
                break
        
        # If no "each" price found, look for any price but check context
        if not price_value:
            # Find all prices
            all_prices = re.findall(r'\$([\d,]+\.?\d*)', price_text.replace(',', ''))
            if all_prices:
                # Take the first reasonable price (usually the main one)
                # Filter out very large prices (likely total/cart prices)
                for price_str in all_prices:
                    p = float(price_str)
                    if 0.01 <= p <= 10000:  # Reasonable price range
                        price_value = p
                        if verbose:
                            print(f"  [DEBUG] Using first reasonable price found: ${price_value}")
                        break
        
        if price_value:
            result['price'] = price_value
            result['unit_price'] = price_value
            result['cost_qty_5'] = price_value * 5
            result['cost_qty_20'] = price_value * 20
        
        return result
    except Exception as e:
        if verbose:
            print(f"  [DEBUG] Extraction failed: {e}")
        result['error'] = str(e)
        return result

def manual_extract(url: str, verbose: bool = True) -> Dict:
    """Open browser, wait for user to navigate manually, then extract."""
    if not HAS_SELENIUM:
        return {'error': 'selenium not installed. Run: pip install selenium'}
    
    driver = None
    try:
        if verbose:
            print("="*80)
            print("MANUAL BROWSER MODE")
            print("="*80)
            print("\n1. A Chrome window will open")
            print("2. Navigate to the McMaster product page manually")
            print("3. Make sure you can see the product and price")
            print("4. Come back here and press ENTER")
            print("\nWaiting for you to navigate...\n")
        
        # Try undetected-chromedriver first, fallback to regular Selenium
        if HAS_UC:
            if verbose:
                print("  [DEBUG] Using undetected-chromedriver...")
            options = uc.ChromeOptions()
            driver = uc.Chrome(options=options, version_main=None)
        else:
            if verbose:
                print("  [DEBUG] Using regular Selenium Chrome...")
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(options=options)
        
        # Start at homepage
        driver.get("https://www.mcmaster.com")
        
        # Wait for user
        input("\nPress ENTER when you're on the product page and ready to extract...\n")
        
        # Extract from current page
        current_url = driver.current_url
        if verbose:
            print(f"  [DEBUG] Extracting from: {current_url}")
        
        result = extract_from_current_page(driver, current_url, verbose)
        
        # Keep browser open for a moment so user can see
        if verbose:
            print("\n✅ Extraction complete! Browser will close in 5 seconds...")
        time.sleep(5)
        
        return result
        
    except Exception as e:
        if verbose:
            print(f"  [DEBUG] Error: {e}")
        return {'error': str(e)}
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.mcmaster.com/97105A040/"
    result = manual_extract(url, verbose=True)
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    if result.get('title'):
        print(f"✅ Title: {result['title']}")
        print(f"   Part #: {result.get('part_number', 'N/A')}")
        print(f"   Price: ${result.get('price', 0):.2f}")
        print(f"   Cost for 5: ${result.get('cost_qty_5', 0):.2f}")
        print(f"   Cost for 20: ${result.get('cost_qty_20', 0):.2f}")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")

