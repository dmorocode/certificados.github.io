# wsgi.py
from src.app_backend import app as application # 'app' é a instância do Flask no seu app.py
# Se seu app.py estiver dentro de uma subpasta, tipo 'src/app.py',
# seria 'from src.app import app as application'