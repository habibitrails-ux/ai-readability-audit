import os
import sys

# Add root directory to path to allow importing app module cleanly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel Serverless Function Handler
if __name__ == '__main__':
    app.run()
