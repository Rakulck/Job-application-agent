@echo off
cd /d "C:\Users\Asus\OneDrive\Desktop\job application agent"
echo [scheduler] Starting job application agent...
"C:\Program Files\Python313\python.exe" scheduler.py >> "C:\Users\Asus\OneDrive\Desktop\job application agent\output\scheduler.log" 2>&1
