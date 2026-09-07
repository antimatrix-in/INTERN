import os
from app import create_app
from flask import jsonify
from datetime import datetime

app = create_app()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'OK',
        'message': 'Your API is running',
        'timestamp': datetime.utcnow().isoformat()
    })

#run code
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
