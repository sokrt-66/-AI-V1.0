@echo off
chcp 65001 >nul

echo Step 1/5: Initialize git repo...
git init

echo Step 2/5: Configure git user...
git config user.email "sokr-66@users.noreply.github.com"
git config user.name "sokr-66"

echo Step 3/5: Add all files...
git add -A

echo Step 4/5: Create commit...
git commit -m "Initial commit - Light Enterprise AI Office System V1.0"

echo Step 5/5: Push to GitHub...
git remote add origin https://github.com/sokr-66/light-enterprise-ai-office-v1.git
git branch -M main
git push -u origin main

echo.
echo Done! Check: https://github.com/sokr-66/light-enterprise-ai-office-v1
pause