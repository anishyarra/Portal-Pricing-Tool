#!/usr/bin/env python3
"""
LLM Batch Search - Process multiple product names with AI guidance.

Takes a file with product names, uses LLM to find part numbers for each,
then saves all part numbers for batch pricing extraction.
"""

import sys
import os
import time
from llm_guided_search import llm_guided_search, HAS_SELENIUM, HAS_UC, HAS_OPENAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
try:
    import undetected_chromedriver as uc
except:
    pass

def batch_llm_search(input_file: str, output_file: str = None, verbose: bool = True):
    """Process multiple product names with LLM guidance."""
    if not HAS_SELENIUM:
        print("❌ Error: selenium not installed. Run: pip install selenium")
        return
    
    if not HAS_OPENAI:
        print("❌ Error: OpenAI not installed. Run: pip install openai")
        return
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        print("   Set it: export OPENAI_API_KEY='your-key'")
        return
    
    # Read input file
    try:
        with open(input_file, 'r') as f:
            product_names = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except FileNotFoundError:
        print(f"❌ Error: File not found: {input_file}")
        return
    
    if not product_names:
        print("❌ Error: No product names in file")
        return
    
    print("="*80)
    print("LLM BATCH SEARCH")
    print("="*80)
    print(f"\nProcessing {len(product_names)} products")
    print("This will use AI to find part numbers for each product.\n")
    
    input("Press ENTER to start (browser will open)...\n")
    
    driver = None
    all_results = []
    
    try:
        # Launch browser once
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
        print("  [DEBUG] Visiting McMaster homepage...")
        driver.get("https://www.mcmaster.com")
        time.sleep(2)
        
        # Process each product
        for i, product_name in enumerate(product_names, 1):
            print(f"\n{'='*80}")
            print(f"[{i}/{len(product_names)}] Processing: {product_name}")
            print('='*80)
            
            results = llm_guided_search(product_name, driver, api_key, max_depth=3, verbose=verbose)
            
            if results:
                all_results.extend(results)
                print(f"  ✅ Found {len(results)} product(s)")
            else:
                print(f"  ⚠️  No products found for: {product_name}")
            
            # Small delay between searches
            if i < len(product_names):
                time.sleep(2)
        
        # Save all results to organized folder
        results_dir = os.path.join(os.path.dirname(__file__), 'outputs', 'results')
        os.makedirs(results_dir, exist_ok=True)
        
        if not output_file:
            base_name = os.path.basename(input_file).replace('.txt', '')
            output_file = os.path.join(results_dir, f"{base_name}_part_numbers.txt")
        else:
            output_file = os.path.join(results_dir, os.path.basename(output_file))
        
        if all_results:
            with open(output_file, 'w') as f:
                for r in all_results:
                    f.write(f"{r['part_number']}\n")
            
            print("\n" + "="*80)
            print("BATCH SEARCH COMPLETE")
            print("="*80)
            print(f"\n✅ Found {len(all_results)} products total")
            print(f"💾 Part numbers saved to: {output_file}")
            print(f"\nNext step: Extract pricing")
            print(f"   python3 batch_extract.py {output_file}")
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
    if len(sys.argv) < 2:
        print("Usage: python3 llm_batch_search.py <product_names.txt> [output_file.txt]")
        print("\nInput file format (one product name per line):")
        print("  shallow female-threaded anchors")
        print("  disposable gloves food grade")
        print("  steel anchor concrete")
        print("\nExample:")
        print("  python3 llm_batch_search.py products.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    batch_llm_search(input_file, output_file, verbose=True)

