@echo off
echo Navigating to D:\MSI
cd D:\MSI
echo Activating virtual environment
call venv\Scripts\activate
echo Pulling latest changes from Git
git pull origin master
echo running migration
python manage.py migrate
echo Starting Django development server
python manage.py runserver
pause
explorer "http://localhost:8000"
