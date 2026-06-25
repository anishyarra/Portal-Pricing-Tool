# Portal Pricing Tool

An LLM-driven browser agent that autonomously navigates McMaster-Carr to find part numbers and extract live pricing, specs, and availability — turning a vague product description into clean structured data (CSV/JSON).

McMaster-Carr has no public API and aggressive bot detection. This tool drives a real Chrome browser with **GPT-4 Vision in the loop**: the model "sees" each page, decides what to search and where to click, and walks the catalog like a person until it lands on the right part — then extracts the pricing table.

## What it does

- **Name → part number** — give it `"shallow female-threaded anchors"`; it searches, reasons over the results, and returns the catalog part number(s).
- **Part number → pricing** — batch-extract unit price, price breaks (5 / 20 units), availability, and MPN for a list of parts.
- **Structured output** — every run is saved to CSV + JSON, with step-by-step screenshots.

## How it works

- **Vision agent loop** (`llm_guided_search.py`) — screenshots the page, GPT-4 Vision chooses the next action (search / click / scroll), iterating until it reaches the target product.
- **Resilient automation** — Selenium + `undetected-chromedriver` to operate a site that actively blocks bots.
- **Extraction layer** (`mcmaster_pricing.py`, `batch_extract.py`) — parses price tables and product data into normalized records.

**Stack:** Python · OpenAI GPT-4 Vision · Selenium · undetected-chromedriver

## Quick Start

### Option 1: AI-Guided Search (Recommended)

**Find part numbers from product names:**

```bash
# Single product
python3 llm_guided_search.py "shallow female-threaded anchors"

# Multiple products
python3 llm_batch_search.py products.txt
```

**Requirements:**
- OpenAI API key: `export OPENAI_API_KEY='your-key'`
- Install: `pip install openai selenium undetected-chromedriver`

### Option 2: Batch Extract Pricing

**If you already have part numbers:**

1. Create file with part numbers (one per line):
   ```
   97105A040
   97085A470
   1975A103
   ```

2. Extract pricing:
   ```bash
   python3 batch_extract.py part_numbers.txt
   ```

3. Results saved to CSV and JSON automatically!

## What You Get

- Product title
- Part number / Item number
- Price per unit
- Cost for 5 units
- Cost for 20 units
- Availability information
- Manufacturer part number (MPN)

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Files

**Main Tools:**
- `llm_guided_search.py` - AI-guided search (finds part numbers from product names)
- `llm_batch_search.py` - Batch AI search (multiple products)
- `batch_extract.py` - Extract pricing from part numbers
- `manual_browser_helper.py` - Manual navigation helper

**Core Logic:**
- `mcmaster_pricing.py` - McMaster extraction logic

## Complete Workflow

```bash
# Step 1: Create input file in inputs/ folder
# Edit: inputs/products.txt (one product name per line)

# Step 2: Find part numbers (AI-guided)
python3 llm_batch_search.py inputs/products.txt
# → Saves to: outputs/results/products_part_numbers.txt
# → Screenshots: outputs/screenshots/

# Step 3: Extract pricing
python3 batch_extract.py outputs/results/products_part_numbers.txt
# → Saves to: outputs/results/products_pricing_results.csv
```

## Folder Structure

```
Portal Pricing Tool/
├── inputs/              # Your input files (product names)
├── outputs/
│   ├── screenshots/     # Screenshots from AI search
│   └── results/         # Part numbers and pricing results
├── llm_guided_search.py
├── llm_batch_search.py
├── batch_extract.py
└── README.md
```

## Requirements

- Python 3.8+
- OpenAI API key
- Chrome browser (for Selenium)

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd "Portal Pricing Tool"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
export OPENAI_API_KEY='your-key'
```

## License

MIT License - See LICENSE file for details

