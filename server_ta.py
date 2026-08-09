import os
from flask import Flask, jsonify, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)

# Konfigurasi Database (Membaca DATABASE_URL dari Render Environment)
db_uri = os.environ.get('DATABASE_URL', 'sqlite:///local_sensor.db')
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Model Tabel Database
class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    ph = db.Column(db.Float, nullable=False)
    tds = db.Column(db.Float, nullable=False)
    water_temp = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'ph': self.ph,
            'tds': self.tds,
            'water_temp': self.water_temp,
            'timestamp': (self.timestamp + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S') # Convert UTC ke WIB (+7)
        }

# Otomatis buat tabel jika belum ada
with app.app_context():
    db.create_all()

# Template Dashboard HTML (Chart.js Auto-Refresh)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HYDRA-S3 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { text-align: center; color: #00e676; margin-bottom: 20px; }
        .cards { display: flex; gap: 15px; margin-bottom: 20px; justify-content: center; }
        .card { background: #1e1e1e; padding: 15px 25px; border-radius: 8px; text-align: center; border: 1px solid #333; min-width: 180px; }
        .card h3 { margin: 0; color: #aaa; font-size: 0.8rem; }
        .card .value { font-size: 1.8rem; font-weight: bold; margin-top: 5px; }
        .chart-box { background: #1e1e1e; padding: 20px; border-radius: 8px; border: 1px solid #333; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>HYDRA-S3 Real-Time Dashboard</h2>
        </div>
        <div class="cards">
            <div class="card"><h3>pH LEVEL</h3><div class="value" id="v-ph" style="color:#00e676;">--</div></div>
            <div class="card"><h3>TDS (PPM)</h3><div class="value" id="v-tds" style="color:#29b6f6;">--</div></div>
            <div class="card"><h3>SUHU AIR (°C)</h3><div class="value" id="v-temp" style="color:#ffb74d;">--</div></div>
        </div>
        <div class="chart-box">
            <canvas id="myChart"></canvas>
        </div>
    </div>
    <script>
        let chart;
        async function updateData() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                if (data.length > 0) {
                    const last = data[data.length - 1];
                    document.getElementById('v-ph').innerText = last.ph.toFixed(2);
                    document.getElementById('v-tds').innerText = Math.round(last.tds);
                    document.getElementById('v-temp').innerText = last.water_temp.toFixed(1);

                    const labels = data.map(d => d.timestamp.split(' ')[1]);
                    const phs = data.map(d => d.ph);
                    const tdss = data.map(d => d.tds);

                    if (!chart) {
                        const ctx = document.getElementById('myChart').getContext('2d');
                        chart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [
                                    { label: 'pH', data: phs, borderColor: '#00e676', yAxisID: 'y' },
                                    { label: 'TDS (PPM)', data: tdss, borderColor: '#29b6f6', yAxisID: 'y1' }
                                ]
                            },
                            options: {
                                responsive: true,
                                scales: {
                                    y: { type: 'linear', position: 'left' },
                                    y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } }
                                }
                            }
                        });
                    } else {
                        chart.data.labels = labels;
                        chart.data.datasets[0].data = phs;
                        chart.data.datasets[1].data = tdss;
                        chart.update();
                    }
                }
            } catch (e) { console.error(e); }
        }
        updateData();
        setInterval(updateData, 10000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/monitoring', methods=['POST'])
def receive_monitoring():
    data = request.get_json()
    if not data or not all(k in data for k in ('ph', 'tds', 'water_temp')):
        return jsonify({'status': 'error', 'message': 'Payload invalid'}), 400
    
    # 1. Simpan Data Baru
    new_data = SensorData(
        ph=float(data['ph']),
        tds=float(data['tds']),
        water_temp=float(data['water_temp'])
    )
    db.session.add(new_data)
    
    # 2. AUTO-PRUNING: Hapus otomatis data yang berumur lebih dari 30 hari
    cutoff = datetime.utcnow() - timedelta(days=30)
    SensorData.query.filter(SensorData.timestamp < cutoff).delete()
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Data tersimpan di Neon PostgreSQL'}), 201

@app.route('/api/history', methods=['GET'])
def get_history():
    # Ambil 20 sampel data terakhir untuk grafik UI
    records = SensorData.query.order_by(SensorData.id.desc()).limit(20).all()
    records.reverse()
    return jsonify([r.to_dict() for r in records])

@app.route('/api/controlling', methods=['GET'])
def get_controlling():
    return jsonify({
        'setpoint_ph_min': 6.0,
        'setpoint_ph_max': 6.5,
        'setpoint_tds_min': 400.0,
        'setpoint_tds_max': 600.0
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
