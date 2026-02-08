#!/bin/bash
# Setup script with virtual environment for Grainger Pricing Tool

echo "🚀 Setting up Grainger Pricing Tool with Virtual Environment..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

echo "✅ Virtual environment created"
echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install Python packages
echo "📦 Installing Python packages..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Python packages"
    exit 1
fi

echo "✅ Python packages installed"
echo ""

# Install Playwright browser
echo "🌐 Installing Playwright Chromium browser..."
playwright install chromium

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Playwright browser"
    exit 1
fi

echo "✅ Playwright browser installed"
echo ""
echo "🎉 Setup complete!"
echo ""
echo "📝 IMPORTANT: To use the tool, you need to activate the virtual environment first:"
echo "   source venv/bin/activate"
echo ""
echo "Then you can run:"
echo "   python3 run.py"
echo "   python3 grainger_pricing.py"
echo "   python3 example_usage.py"
echo ""
echo "To deactivate the virtual environment when done:"
echo "   deactivate"

