from app import app

# Vercel requires the WSGI application callable to be exposed
app = app

if __name__ == "__main__":
    app.run()
