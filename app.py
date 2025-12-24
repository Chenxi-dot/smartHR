from flask import Flask, render_template, request, jsonify
from src.matcher import SmartMatcher
import os

app = Flask(__name__)

# Initialize matcher globally to load data once; reinitialize when role changes.
matcher = SmartMatcher()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/match', methods=['POST'])
def match():
    jd_text = request.form.get('jd', '').strip()
    target_role = request.form.get('role', '').strip() or None

    if not jd_text:
        return render_template('index.html', error="Please provide a Job Description.", role=target_role)
    
    # Run matching with optional role filter
    candidates = matcher.match(jd_text, target_role=target_role)
    if matcher.last_error:
        return render_template('index.html', error=matcher.last_error, jd=jd_text, role=target_role, progress=matcher.last_progress)
    
    return render_template('index.html', candidates=candidates, jd=jd_text, role=target_role, progress=matcher.last_progress)


@app.route('/get_progress')
def get_progress():
    progress_data = {
        "percentage": getattr(matcher, 'current_percent', 0),
        "status": getattr(matcher, 'current_status', "Initializing..."),
        "logs": getattr(matcher, 'last_progress', []),
    }
    return jsonify(progress_data)

if __name__ == '__main__':
    # Ensure templates directory exists
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("Starting Flask app...")
    app.run(debug=True, port=5000)
