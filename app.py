from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/logs', methods=['GET'])
def get_logs():
    try:
        with open('/root/B/net.log', 'r') as file:
            logs = file.readlines()
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
