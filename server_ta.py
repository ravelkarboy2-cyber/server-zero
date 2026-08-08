from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "online", "server": "Server Zero Active"}), 200

# 1. Endpoint HTTP POST (Node Pemantauan - Setor Data Sensor)
@app.route('/api/monitoring', methods=['POST'])
def receive_sensor():
    data = request.get_json()
    print("\n==================================================")
    print("[SERVER ZERO] Data Sensor Diterima:")
    print(f"  - pH         : {data.get('ph')}")
    print(f"  - TDS        : {data.get('tds')} ppm")
    print(f"  - Suhu Air   : {data.get('water_temp')} °C")
    print("==================================================")
    return jsonify({"status": "success", "message": "Data berhasil diterima Server Zero!"}), 200

# 2. Endpoint HTTP GET (Node Pengendalian - Jemput Komando)
@app.route('/api/controlling', methods=['GET'])
def send_setpoint():
    return jsonify({
        "status": "success",
        "setpoint_ph": 6.25,
        "setpoint_tds": 1100
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)