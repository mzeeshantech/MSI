@echo off
echo Navigating to D:\MSI
cd D:\MSI
echo Activating virtual environment
call venv\Scripts\activate
echo Pulling latest changes from Git
git pull origin master
echo Starting Django development server
python manage.py runserver
