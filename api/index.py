import sys
import os

# Add root folder to python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
