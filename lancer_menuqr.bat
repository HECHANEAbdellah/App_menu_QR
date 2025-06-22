@echo off
REM filepath: c:\Users\HECHANE Abdellah\projet_PFE\menu_qr\lancer_menuqr.bat

REM Active l'environnement virtuel (adapte le chemin si besoin)
call venv\Scripts\activate

REM Lance le serveur Django en arrière-plan
start cmd /k python manage.py runserver

REM Attend quelques secondes que le serveur démarre
timeout /t 3 >nul

REM Ouvre la page d'accueil dans le navigateur par défaut
start http://127.0.0.1:8000/