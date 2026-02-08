# GitHub Setup Instructions

## Step 1: Initialize Git (run these commands)

```bash
cd "/Users/anishyarra/Portal Pricing Tool"

# Initialize git repository
git init

# Add all files
git add .gitignore README.md requirements.txt setup_venv.sh *.py inputs/

# Make initial commit
git commit -m "Initial commit: Portal Pricing Tool with AI-guided search"
```

## Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository (name it something like `portal-pricing-tool`)
3. **Don't** initialize with README, .gitignore, or license (we already have these)

## Step 3: Push to GitHub

```bash
# Add remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## What's Included

✅ All Python scripts
✅ README.md
✅ requirements.txt
✅ .gitignore (excludes outputs/, venv/, etc.)
✅ Example input file (inputs/products.txt)

## What's Excluded (by .gitignore)

❌ outputs/ folder (screenshots and results)
❌ venv/ folder
❌ __pycache__/
❌ .DS_Store and other OS files

