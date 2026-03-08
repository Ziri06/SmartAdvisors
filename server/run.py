import os
from dotenv import load_dotenv

# 1. Get the path to the .env file (it's one folder up, in the root)
basedir = os.path.abspath(os.path.dirname(__file__))
root_path = os.path.join(basedir, '..')
dotenv_path = os.path.join(root_path, '.env')

# 2. Load the variables BEFORE creating the app
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded .env from: {dotenv_path}")
else:
    print("No .env file found, using defaults.")

# 3. Auto-set professors.db path if not configured (works on any machine)
if not os.environ.get('SQLALCHEMY_DATABASE_URI') and not os.environ.get('DATABASE_URL'):
    db_path = os.path.join(basedir, 'data', 'professors.db')
    os.environ['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"Using professors.db at: {db_path}")

from app import create_app

# 3. Now it's safe to create the app
app = create_app()

if __name__ == "__main__":
    # debug True for local development
    # Note: You are running on port 8000 here
    app.run(host="127.0.0.1", port=8000, debug=True)