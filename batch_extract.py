#!/usr/bin/env python3
"""
Batch Processor - Extract pricing for multiple products automatically.

Usage:
    python3 batch_extract.py urls.txt
    python3 batch_extract.py part_numbers.txt
    
Input file can contain:
- Full URLs: https://www.mcmaster.com/97105A040/
- Part numbers: 97105A040
- Product names: (will try to construct URL or search)
"""

import sys
import re
import time
import csv
import json
from typing import List, Dict
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

def extract_from_page(driver, url: str, verbose: bool = True) -> Dict:
    """Extract pricing data from current page."""
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
        'availability': None,
        'extracted_at': datetime.now().isoformat()
    }
    
    try:
        # Extract part number from URL
        part_match = re.search(r'/([\dA-Z]+)/?$', url)
        if part_match:
            result['part_number'] = part_match.group(1)
        
        # Get page text
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Check for login requirement - only if it's clearly a login page
        # Don't flag if "log in" appears in product descriptions or other text
        page_lower = page_text.lower()
        login_indicators = [
            'please log in to continue',
            'sign in to view',
            'log in to access',
            'please sign in',
        ]
        
        # Only flag if we see clear login prompts AND no product content
        has_login_prompt = any(indicator in page_lower for indicator in login_indicators)
        has_product_content = ('price' in page_lower or '$' in page_text or 'add to cart' in page_lower)
        
        if has_login_prompt and not has_product_content:
            if verbose:
                print(f"  ⚠️  Login required - skipping")
            result['error'] = 'Login required'
            return result
        
        # Extract title
        try:
            h1 = driver.find_element(By.TAG_NAME, "h1")
            title = h1.text.strip()
            if title and 'log in' not in title.lower() and 'please log' not in title.lower():
                result['title'] = title
        except:
            pass
        
        # Extract price - look for per-unit price
        price_text = page_text
        
        # Look for "per each" or "each" prices
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
                break
        
        # Fallback: find first reasonable price
        if not price_value:
            all_prices = re.findall(r'\$([\d,]+\.?\d*)', price_text.replace(',', ''))
            for price_str in all_prices:
                p = float(price_str)
                if 0.01 <= p <= 10000:  # Reasonable range
                    price_value = p
                    break
        
        if price_value:
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
        
        return result
        
    except Exception as e:
        if verbose:
            print(f"  ⚠️  Extraction error: {e}")
        result['error'] = str(e)
        return result

def normalize_input(line: str) -> str:
    """Convert part number or name to URL."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Already a URL
    if line.startswith('http'):
        return line
    
    # Part number - construct URL (try both formats)
    if re.match(r'^[\dA-Z]+$', line):
        # McMaster URLs can be /97105A040/ or /products/123456
        # Try the simpler format first
        if re.match(r'^\d+$', line):
            # All digits - might be /products/ format
            return f"https://www.mcmaster.com/products/{line}"
        else:
            # Alphanumeric - use /PARTNUMBER/ format
            return f"https://www.mcmaster.com/{line}/"
    
    # Product name - return as-is (should use llm_guided_search instead)
    return line

def batch_extract(input_file: str, output_file: str = None, verbose: bool = True) -> List[Dict]:
    """Process multiple products from a file."""
    if not HAS_SELENIUM:
        print("❌ Error: selenium not installed. Run: pip install selenium")
        return []
    
    # Read input file
    try:
        with open(input_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except FileNotFoundError:
        print(f"❌ Error: File not found: {input_file}")
        return []
    
    if not lines:
        print("❌ Error: No valid entries in file")
        return []
    
    print("="*80)
    print("BATCH EXTRACTION")
    print("="*80)
    print(f"\nProcessing {len(lines)} items from: {input_file}")
    print("\nThe browser will open and navigate to each product automatically.")
    print("You can watch it work, or minimize the browser.\n")
    
    # Normalize inputs to URLs
    urls = []
    for line in lines:
        url = normalize_input(line)
        if url:
            urls.append(url)
    
    if not urls:
        print("❌ No valid URLs found")
        return []
    
    print(f"Will process {len(urls)} products\n")
    input("Press ENTER to start (browser will open)...\n")
    
    # Open browser
    driver = None
    results = []
    
    try:
        # Launch browser
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
            driver = webdriver.Chrome(options=options)
        
        # Visit homepage first
        if verbose:
            print("  [DEBUG] Establishing session on homepage...")
        driver.get("https://www.mcmaster.com")
        time.sleep(2)
        
        # Process each URL
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Processing: {url}")
            
            try:
                # Navigate to product
                driver.get(url)
                time.sleep(3)  # Wait for page load
                
                # Check if we got a 404 or error page - try alternative URL format
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                current_url = driver.current_url
                
                if ('not found' in page_text or '404' in page_text or 
                    'error' in page_text or current_url.endswith('/404')):
                    # Try alternative URL format
                    if '/products/' in url:
                        # Try simple format
                        part_num = url.split('/products/')[-1].rstrip('/')
                        alt_url = f"https://www.mcmaster.com/{part_num}/"
                    else:
                        # Try /products/ format
                        part_num = url.rstrip('/').split('/')[-1]
                        alt_url = f"https://www.mcmaster.com/products/{part_num}"
                    
                    if verbose:
                        print(f"  ⚠️  First URL failed, trying alternative: {alt_url}")
                    
                    driver.get(alt_url)
                    time.sleep(3)
                    url = alt_url  # Update url for result
                
                # Human-like behavior
                driver.execute_script("window.scrollTo(0, 300)")
                time.sleep(0.5)
                driver.execute_script("window.scrollTo(0, 0)")
                time.sleep(0.5)
                
                # Extract
                result = extract_from_page(driver, url, verbose)
                
                if result.get('title'):
                    print(f"  ✅ {result['title'][:60]}...")
                    print(f"     Price: ${result.get('price', 0):.2f}")
                else:
                    print(f"  ❌ Failed: {result.get('error', 'No title found')}")
                
                results.append(result)
                
                # Delay between requests (human-like)
                if i < len(urls):
                    delay = 2 + (i % 3)  # 2-4 seconds
                    if verbose:
                        print(f"  Waiting {delay}s before next product...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"  ❌ Error processing {url}: {e}")
                results.append({
                    'url': url,
                    'error': str(e),
                    'extracted_at': datetime.now().isoformat()
                })
        
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        
        # Summary
        successful = sum(1 for r in results if r.get('title'))
        print(f"\n✅ Successfully extracted: {successful}/{len(results)}")
        print(f"❌ Failed: {len(results) - successful}/{len(results)}")
        
        # Save results to organized folder
        import os
        results_dir = os.path.join(os.path.dirname(__file__), 'outputs', 'results')
        os.makedirs(results_dir, exist_ok=True)
        
        if not output_file:
            base_name = os.path.basename(input_file).replace('.txt', '').replace('_part_numbers', '')
            output_file = os.path.join(results_dir, f"{base_name}_pricing_results.csv")
        else:
            output_file = os.path.join(results_dir, os.path.basename(output_file))
        
        # Save as CSV
        csv_file = output_file.replace('.json', '.csv')
        with open(csv_file, 'w', newline='') as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        print(f"\n💾 Results saved to: {csv_file}")
        
        # Also save as JSON
        json_file = output_file.replace('.csv', '.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to: {json_file}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        return results
    finally:
        if driver:
            print("\nClosing browser in 3 seconds...")
            time.sleep(3)
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 batch_extract.py <input_file.txt> [output_file.csv]")
        print("\nInput file format (one per line):")
        print("  https://www.mcmaster.com/97105A040/")
        print("  97105A040")
        print("  https://www.mcmaster.com/products/1234567")
        print("\nExample:")
        print("  python3 batch_extract.py part_numbers.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    batch_extract(input_file, output_file, verbose=True)

