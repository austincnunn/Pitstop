import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Debug mode should only be enabled explicitly via environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5151)
