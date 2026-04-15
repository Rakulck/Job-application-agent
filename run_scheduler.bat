@echo off
cd /d "C:\Users\Asus\OneDrive\Desktop\job application agent"
if not exist logs mkdir logs
start "Job Application Agent" /MIN "C:\Program Files\Python313\python.exe" scheduler.py 1>> "C:\Users\Asus\OneDrive\Desktop\job application agent\logs\scheduler.log" 2>&1
