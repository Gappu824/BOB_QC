#!/usr/bin/env python3
"""
BATTLE OF BYTES - PRODUCTION AUCTION PLATFORM v16 (PURE BACKEND API)
=====================================================================
- Serves all API endpoints (no static files)
- Manages the SQLite database on a persistent disk
- Handles real-time updates via WebSocket
- Includes APScheduler to reset polls daily (meets bonus requirement)
- Configured for Render deployment
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
import threading
import pathlib
import gevent  # For production server
from apscheduler.schedulers.background import BackgroundScheduler # For poll reset
from apscheduler.triggers.cron import CronTrigger # For poll reset

# Install dependencies
print('📦 Installing dependencies...')
os.system(f'{sys.executable} -m pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent -q 2>/dev/null')

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
except ImportError:
    print("\n❌ ERROR: Failed to import libraries.")
    print("Please ensure: pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent")
    sys.exit(1)

print('✅ Dependencies loaded!\n')

# ============================================================================
# APPLICATION SETUP (MODIFIED FOR RENDER)
# ============================================================================

# This is the key to working on Render.
# We check for an environment variable 'DATA_DIR'.
# On Render, we will set this to '/data' (the persistent disk).
# Locally, it will default to the current script's directory.
BASE_DATA_DIR = pathlib.Path(os.environ.get('DATA_DIR', pathlib.Path(__file__).parent.resolve()))
DB_PATH = BASE_DATA_DIR / 'auction.db'

print(f"📁 Using database at: {DB_PATH}")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'auction-secret-2025'
# Enable CORS for all routes, allowing your frontend to connect
CORS(app) 
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent') # Specify async_mode

# ============================================================================
# DATABASE HELPERS
# ============================================================================

def dict_from_row(row):
    """Converts a sqlite3.Row object to a dictionary."""
    return dict(row) if row else None

def dicts_from_rows(rows):
    """Converts a list of sqlite3.Row objects to a list of dictionaries."""
    return [dict_from_row(row) for row in rows]

# ============================================================================
# DATABASE SETUP
# ============================================================================

class AuctionDB:
    def __init__(self):
        # We must check if the DB file *and* tables exist before seeding
        db_existed = os.path.exists(DB_PATH)
        
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_tables()
        
        # Only seed data if the database file was just created
        if not db_existed:
            print("Database not found. Seeding fresh data...")
            self.seed_data()
        else:
            print("Existing database found. Skipping seed.")

    
    def init_tables(self):
        cursor = self.conn.cursor()
        
        # Players table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT, nickname TEXT, role TEXT,
                base_price INTEGER, current_bid INTEGER, highest_bidder TEXT,
                image_url TEXT, bio TEXT, skills TEXT,
                total_bids INTEGER DEFAULT 0
            )
        ''')
        
        # Bids table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER, bidder_name TEXT, bid_amount INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Enquiries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Poll table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS poll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT,
                votes INTEGER DEFAULT 0
            )
        ''')
        
        # People table (teams, faculty, coordinators)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                role TEXT,
                email TEXT,
                bio TEXT,
                image_url TEXT,
                social_handle TEXT
            )
        ''')
        
        # Activity log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                description TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                end_time TEXT
            )
        ''')
        
        self.conn.commit()
    
    def seed_data(self):
        cursor = self.conn.cursor()
        
        # Seed Players
        cursor.execute('SELECT COUNT(*) FROM players')
        if cursor.fetchone()[0] == 0:
            print("🌱 Seeding Players...")
            # Using external placeholder images
            players = [
                (1, 'Alex Chen', 'ByteMaster', 'Full Stack Dev', 10000, 10000, None, 
                 'https://i.pravatar.cc/300?img=33', 'Full-stack developer with 8+ years experience', 
                 'React,Node.js,AWS,Docker', 0),
                (2, 'Sarah Kumar', 'CodeNinja', 'Frontend Dev', 12000, 12000, None,
                 'https://i.pravatar.cc/300?img=47', 'Frontend expert creating beautiful interfaces',
                 'React,Vue.js,CSS3,Figma', 0),
                (3, 'Michael Brown', 'DataWizard', 'Backend Dev', 15000, 15000, None,
                 'https://i.pravatar.cc/300?img=12', 'Backend architect with scalable solutions',
                 'Python,Django,PostgreSQL', 0),
                (4, 'Emma Davis', 'CloudQueen', 'DevOps', 11000, 11000, None,
                 'https://i.pravatar.cc/300?img=45', 'DevOps engineer automating everything',
                 'AWS,Docker,Kubernetes', 0),
            ]
            cursor.executemany('INSERT INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?)', players)
        
        # Seed Poll Teams
        cursor.execute('SELECT COUNT(*) FROM poll')
        if cursor.fetchone()[0] == 0:
            print("🌱 Seeding Poll Teams...")
            teams = [
                ('Java Jesters',), ('Quantum Coder',), ('Syntax Samurai',),
                ('Logic Luminaries',), ('Byte Busters',), ('Python Pioneers',),
                ('Code Commanders',), ('Ruby Renegades',), ('Data Mavericks',),
            ]
            cursor.executemany('INSERT INTO poll (team_name) VALUES (?)', teams)
        
        # Seed People (Head Coordinators + Bidding Teams + Faculty)
        cursor.execute('SELECT COUNT(*) FROM people')
        if cursor.fetchone()[0] == 0:
            print("🌱 Seeding People (Coordinators, Teams, Faculty)...")
            # Using external placeholder images
            people = [
                # HEAD COORDINATORS
                ('Hiya Arya', 'Head Coordinator', 'hiya@battleofbytes.com', 
                 'Promotion & Operation Lead for Battle of Bytes 2.0', 'https://i.pravatar.cc/300?img=1', '@hushhiya'),
                ('Ashank Agrawal', 'Head Coordinator', 'ashank@battleofbytes.com',
                 'Co Tech Lead orchestrating the technical aspects', 'https://i.pravatar.cc/300?img=2', '@ashankagrawal'),
                ('Sarthak Sinha', 'Head Coordinator', 'sarthak@battleofbytes.com',
                 'Design & Social Media Lead crafting the visual identity', 'https://i.pravatar.cc/300?img=3', '@sarthak.sinhahaha'),
                ('Manalika Agarwal', 'Head Coordinator', 'manalika@battleofbytes.com',
                 'Co Tech Lead ensuring seamless execution', 'https://i.pravatar.cc/300?img=4', '@manalika__'),
                ('Somya Upadhyay', 'Head Coordinator', 'somya@battleofbytes.com',
                 'Sponsorship Lead securing partnerships', 'https://i.pravatar.cc/300?img=50', '@__.somyaaaaa__'),
                
                # BIDDING TEAMS
                ('Java Jesters', 'Bidding Team', 'captains@jesters.com', 
                 'Known for meticulous planning and aggressive bidding strategies.', 
                 'https://i.pravatar.cc/300?img=5', None),
                ('Quantum Coder', 'Bidding Team', 'lead@quantum.dev', 
                 'A mysterious team with deep pockets, focusing on high-potential talent.', 
                 'https://i.pravatar.cc/300?img=6', None),
                ('Syntax Samurai', 'Bidding Team', 'master@samurai.io', 
                 'They strike with precision, waiting for the perfect moment to bid.', 
                 'https://i.pravatar.cc/300?img=7', None),
                # ... (other teams)
                
                # FACULTY
                ('Dr. Priya Sharma', 'Faculty Advisor', 'p.sharma@college.edu', 
                 'Head Faculty Coordinator overseeing all event logistics.', 
                 'https://i.pravatar.cc/300?img=60', None),
                ('Prof. Rajesh Kumar', 'Faculty Judge', 'r.kumar@college.edu', 
                 'Lead judge and auction overseer ensuring fair play.', 
                 'https://i.pravatar.cc/300?img=61', None),
                ('Dr. Anjali Verma', 'Faculty Member', 'a.verma@college.edu', 
                 'Responsible for talent scouting and player vetting.', 
                 'https://i.pravatar.cc/300?img=31', None),
            ]
            cursor.executemany(
                'INSERT INTO people (name, role, email, bio, image_url, social_handle) VALUES (?,?,?,?,?,?)', 
                people
            )
        
        # Seed Settings
        cursor.execute('SELECT COUNT(*) FROM settings')
        if cursor.fetchone()[0] == 0:
            print("🌱 Seeding Auction Timer...")
            end_time = (datetime.now() + timedelta(hours=72)).isoformat()
            cursor.execute('INSERT INTO settings VALUES (1, ?)', (end_time,))
        
        self.conn.commit()
        print('✅ Database initialized successfully!')

# Initialize database
db = AuctionDB()

# ============================================================================
# DAILY POLL RESET FUNCTION (Bonus Requirement)
# ============================================================================
def reset_poll_votes():
    """
    Connects to the DB and resets all poll votes to 0.
    [cite_start]This meets the "Poll results should reset daily" requirement. [cite: 24]
    """
    print("⏰ EXECUTING DAILY POLL RESET...")
    try:
        # Need a new connection for the background thread
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE poll SET votes = 0')
        conn.commit()
        conn.close()
        print("✅ Polls reset successfully.")
        
        # Emit a socket event to all clients to refresh their poll data
        socketio.emit('poll_update', {})
    except Exception as e:
        print(f"🔥 ERROR during poll reset: {e}")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_activity(type, description):
    """Logs an event to the DB and emits it to all connected clients."""
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            'INSERT INTO activity_log (type, description) VALUES (?, ?)',
            (type, description)
        )
        db.conn.commit()
        
        log_id = cursor.lastrowid
        cursor.execute('SELECT * FROM activity_log WHERE id = ?', (log_id,))
        new_activity = dict_from_row(cursor.fetchone())
        
        socketio.emit('activity_update', new_activity)
        
    except Exception as e:
        print(f"🔥 ERROR in log_activity: {e}")

# ============================================================================
# FLASK API ROUTES
# ============================================================================

@app.route('/api/players')
def api_players():
    """Gets a list of all players."""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM players ORDER BY current_bid DESC')
    players = dicts_from_rows(cursor.fetchall())
    return jsonify(players)

@app.route('/api/players/<int:player_id>')
def api_player_detail(player_id):
    """Gets detailed info for a single player, including bid history."""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM players WHERE id = ?', (player_id,))
    player = dict_from_row(cursor.fetchone())
    
    if not player:
        return jsonify({'error': 'Not found'}), 404
    
    cursor.execute('''
        SELECT bidder_name, bid_amount, timestamp 
        FROM bids WHERE player_id = ? 
        ORDER BY timestamp DESC LIMIT 10
    ''', (player_id,))
    player['bid_history'] = dicts_from_rows(cursor.fetchall())
    
    return jsonify(player)

@app.route('/api/bid', methods=['POST'])
def api_place_bid():
    """
    [cite_start]Submits a new bid for a player. [cite: 18]
    Checks if the bid is higher than the current one.
    """
    try:
        data = request.json
        player_id = data.get('player_id')
        bidder_name = data.get('bidder_name')
        bid_amount = int(data.get('bid_amount'))
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT current_bid, name FROM players WHERE id = ?', (player_id,))
        result = dict_from_row(cursor.fetchone())
        
        if not result:
            return jsonify({'error': 'Player not found'}), 404
        
        current_bid = result['current_bid']
        player_name = result['name']
        
        if bid_amount <= current_bid:
            return jsonify({'error': f'Bid must be higher than ${current_bid:,}'}), 400
        
        cursor.execute('''
            UPDATE players 
            SET current_bid = ?, highest_bidder = ?, total_bids = total_bids + 1
            WHERE id = ?
        ''', (bid_amount, bidder_name, player_id))
        
        cursor.execute('''
            INSERT INTO bids (player_id, bidder_name, bid_amount)
            VALUES (?, ?, ?)
        ''', (player_id, bidder_name, bid_amount))
        
        db.conn.commit()
        
        log_activity('bid', f'{bidder_name} bid ${bid_amount:,} on {player_name}')
        
        # [cite_start]Emits bid update to all clients [cite: 19]
        socketio.emit('bid_update', {
            'player_id': player_id,
            'player_name': player_name,
            'bidder_name': bidder_name,
            'bid_amount': bid_amount
        })
        
        return jsonify({'success': True, 'message': 'Bid placed successfully!'})
    except Exception as e:
        print(f"🔥 ERROR in api_place_bid: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/enquiry', methods=['POST'])
def api_enquiry():
    """
    [cite_start]Submits a contact form message. [cite: 14]
    [cite_start]This is a mandatory feature. [cite: 14]
    """
    data = request.json
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')
    
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO enquiries (name, email, message)
        VALUES (?, ?, ?)
    ''', (name, email, message))
    db.conn.commit()
    
    log_activity('enquiry', f'New enquiry from {name}')
    
    return jsonify({'success': True, 'message': 'Enquiry submitted successfully!'})

@app.route('/api/poll')
def api_poll():
    [cite_start]"""Gets the current poll results. [cite: 23]"""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM poll ORDER BY votes DESC')
    teams = dicts_from_rows(cursor.fetchall())
    return jsonify(teams)

@app.route('/api/poll/vote', methods=['POST'])
def api_vote():
    [cite_start]"""Submits a vote for a team. [cite: 23]"""
    team_name = request.json.get('team_name')
    
    cursor = db.conn.cursor()
    cursor.execute('UPDATE poll SET votes = votes + 1 WHERE team_name = ?', (team_name,))
    db.conn.commit()
    
    log_activity('poll', f'Vote cast for {team_name}')
    
    socketio.emit('poll_update', {})
    
    return jsonify({'success': True})

@app.route('/api/people')
def api_people():
    """
    [cite_start]Gets all coordinators, teams, and faculty. [cite: 12, 13]
    Used to display info about bidders, coordinators, and faculty.
    """
    cursor = db.conn.cursor()
    response = {
        "coordinators": [],
        "teams": [],
        "faculty": []
    }
    
    cursor.execute("SELECT * FROM people WHERE role = 'Head Coordinator' ORDER BY name")
    response['coordinators'] = dicts_from_rows(cursor.fetchall())
    
    cursor.execute("SELECT * FROM people WHERE role = 'Bidding Team' ORDER BY name")
    response['teams'] = dicts_from_rows(cursor.fetchall())
    
    cursor.execute("SELECT * FROM people WHERE role LIKE '%Faculty%' OR role LIKE '%Judge%' ORDER BY name")
    response['faculty'] = dicts_from_rows(cursor.fetchall())
    
    return jsonify(response)

@app.route('/api/activity')
def api_activity():
    """Gets the 30 most recent activity items."""
    cursor = db.conn.cursor()
    cursor.execute('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 30')
    activities = dicts_from_rows(cursor.fetchall())
    return jsonify(activities)

@app.route('/api/status')
def api_status():
    """Gets auction stats (timer, total bids, total value)."""
    try:
        cursor = db.conn.cursor()
        cursor.execute('SELECT end_time FROM settings WHERE id = 1')
        result = dict_from_row(cursor.fetchone())
        
        if not result:
            db.seed_data() # This should only happen if DB is deleted
            cursor.execute('SELECT end_time FROM settings WHERE id = 1')
            result = dict_from_row(cursor.fetchone())

        end_time_str = result['end_time']
        end_time = datetime.fromisoformat(end_time_str)
        remaining = (end_time - datetime.now()).total_seconds()
        
        cursor.execute('SELECT COUNT(*) as total_bids FROM bids')
        total_bids = dict_from_row(cursor.fetchone())['total_bids']
        
        cursor.execute('SELECT SUM(current_bid) as total_value FROM players')
        total_value = dict_from_row(cursor.fetchone())['total_value'] or 0
        
        return jsonify({
            'end_time': end_time_str,
            [cite_start]'time_remaining': max(0, remaining), # [cite: 20]
            'total_bids': total_bids,
            'total_value': total_value
        })
    except Exception as e:
        print(f"🔥 ERROR in api_status: {e}")
        return jsonify({'error': str(e)}), 500

# Simple health-check route for Render
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('connected', {'status': 'ok'})

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')
    pass

# ============================================================================
# START SERVER
# ============================================================================

def start_server():
    print('\n' + '='*80)
    print('🏆 BATTLE OF BYTES 2.0 - PRODUCTION AUCTION (PURE BACKEND API)')
    print('='*80)
    
    print(f"\n📁 Database: {DB_PATH}")
    
    # [cite_start]Initialize and start the scheduler for daily poll reset [cite: 24]
    try:
        scheduler = BackgroundScheduler()
        # This cron trigger fires at 00:00 (midnight) every day
        scheduler.add_job(
            reset_poll_votes,
            trigger=CronTrigger(hour=0, minute=0)
        )
        scheduler.start()
        print("⏰ Daily poll reset job scheduled for midnight.")
    except Exception as e:
        print(f"🔥 FAILED to start scheduler: {e}")

    # Get port from Render's environment variable
    port = int(os.environ.get('PORT', 5000))
    
    print(f'\n🚀 Starting server on http://0.0.0.0:{port}')
    print('   Your frontend team can use this URL to make API requests.')
    print('='*80 + '\n')
    
    # Run with gevent for production
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port)

if __name__ == '__main__':
    start_server()