#!/usr/bin/env python3
"""
BATTLE OF BYTES - PRODUCTION AUCTION PLATFORM v19 (Final Mentor List)
=====================================================================
- Uses PostgreSQL for persistent data on Render's free tier
- Serves static files (logo, images, videos) from the repo's 'static' folder
- Includes APScheduler to reset polls daily (meets bonus requirement)
- Seeding data UPDATED with the final, correct list of 10 teams and their mentors.
- UPDATED: api_place_bid function replaced with user-provided, more robust version.
"""

import os
import sys
import json
from datetime import datetime, timedelta
import threading
import gevent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Install dependencies
print('📦 Installing dependencies...')
os.system(f'{sys.executable} -m pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent sqlalchemy psycopg2-binary -q 2>/dev/null')

try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
    
    from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, scoped_session, relationship
    from sqlalchemy.exc import OperationalError
    
except ImportError:
    print("\n❌ ERROR: Failed to import libraries.")
    print("Please ensure: pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent sqlalchemy psycopg2-binary")
    sys.exit(1)

print('✅ Dependencies loaded!\n')

# ============================================================================
# APPLICATION SETUP
# ============================================================================

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("🔥 ERROR: DATABASE_URL environment variable not set.")
    print("This app is designed for a PostgreSQL database (e.g., on Render).")
    if not DATABASE_URL.startswith('sqlite'):
        sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"📁 Connecting to database...")
try:
    engine = create_engine(DATABASE_URL)
    Base = declarative_base()
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
except Exception as e:
    print(f"🔥 Failed to connect to database: {e}")
    sys.exit(1)
print("✅ Database connection initiated.")

STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
app = Flask(__name__, static_folder=STATIC_FOLDER) 

app.config['SECRET_KEY'] = 'auction-secret-2025'
CORS(app) 
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Player(Base):
    __tablename__ = 'players'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    nickname = Column(String)
    role = Column(String)
    base_price = Column(Integer)
    current_bid = Column(Integer)
    highest_bidder = Column(String)
    image_url = Column(String)
    bio = Column(Text)
    skills = Column(String)
    total_bids = Column(Integer, default=0)
    bids = relationship("Bid", back_populates="player", order_by="desc(Bid.timestamp)")

class Bid(Base):
    __tablename__ = 'bids'
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'))
    bidder_name = Column(String)
    bid_amount = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    player = relationship("Player", back_populates="bids")

class Enquiry(Base):
    __tablename__ = 'enquiries'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    email = Column(String)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Poll(Base):
    __tablename__ = 'poll'
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String, unique=True)
    votes = Column(Integer, default=0)

class Person(Base):
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    role = Column(String) # 'Head Coordinator', 'Bidding Team', 'Faculty Mentor'
    email = Column(String)
    bio = Column(Text)
    image_url = Column(String)
    social_handle = Column(String)
    video_url = Column(String)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String) # 'bid', 'poll', 'enquiry'
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    end_time = Column(String) # ISO format

# ============================================================================
# DATABASE SEEDING
# ============================================================================

def seed_data():
    session = Session()
    try:
        # Check if players table is empty
        if session.query(Player).count() == 0:
            print("🌱 Seeding Players...")
            players = [
                Player(id=1, name='Alex Chen', nickname='ByteMaster', role='Full Stack Dev', base_price=10000, current_bid=10000,
                       image_url='https://i.pravatar.cc/300?img=33', bio='Full-stack developer with 8+ years experience',
                       skills='React,Node.js,AWS,Docker', total_bids=0),
                Player(id=2, name='Sarah Kumar', nickname='CodeNinja', role='Frontend Dev', base_price=12000, current_bid=12000,
                       image_url='https://i.pravatar.cc/300?img=47', bio='Frontend expert creating beautiful interfaces',
                       skills='React,Vue.js,CSS3,Figma', total_bids=0),
                Player(id=3, name='Michael Brown', nickname='DataWizard', role='Backend Dev', base_price=15000, current_bid=15000,
                       image_url='https://i.pravatar.cc/300?img=12', bio='Backend architect with scalable solutions',
                       skills='Python,Django,PostgreSQL', total_bids=0),
                Player(id=4, name='Emma Davis', nickname='CloudQueen', role='DevOps', base_price=11000, current_bid=11000,
                       image_url='https://i.pravatar.cc/300?img=45', bio='DevOps engineer automating everything',
                       skills='AWS,Docker,Kubernetes', total_bids=0),
            ]
            session.add_all(players)
        
        if session.query(Poll).count() == 0:
            print("🌱 Seeding Poll Teams (10 teams)...")
            teams = [
                Poll(team_name='Java Jesters'), Poll(team_name='Quantum Coders'), Poll(team_name='Syntax Samurai'),
                Poll(team_name='Logic Luminaries'), Poll(team_name='Byte Busters'), Poll(team_name='Python Pioneers'),
                Poll(team_name='Code Commanders'), Poll(team_name='Ruby Renegades'), Poll(team_name='Data Mavericks'),
                Poll(team_name='Code Trail')
            ]
            session.add_all(teams)

        if session.query(Person).count() == 0:
            print("🌱 Seeding People (Coordinators, Teams, Faculty)...")
            
            people = [
                # HEAD COORDINATORS
                Person(name='Hiya Arya', role='Head Coordinator', email='hiya@battleofbytes.com', 
                       bio='Promotion & Operation Lead', image_url='/static/hiya_arya.png', 
                       social_handle='@hushhiya'),
                Person(name='Ashank Agrawal', role='Head Coordinator', email='ashank@battleofbytes.com',
                       bio='Co Tech Lead', image_url='/static/ashank_agrawal.png', 
                       social_handle='@ashankagrawal'),
                Person(name='Sarthak Sinha', role='Head Coordinator', email='sarthak@battleofbytes.com',
                       bio='Design & Social Media Lead', image_url='/static/sarthak_sinha.png', 
                       social_handle='@sarthak.sinhahaha'),
                Person(name='Manalika Agarwal', role='Head Coordinator', email='manalika@battleofbytes.com',
                       bio='Co Tech Lead', image_url='/static/manalika_agarwal.png', 
                       social_handle='@manalika__'),
                Person(name='Somya Upadhyay', role='Head Coordinator', email='somya@battleofbytes.com',
                       bio='Sponsorship Lead', image_url='/static/somya_upadhyay.png', 
                       social_handle='@__.somyaaaaa__'),
                
                # BIDDING TEAMS
                Person(name='Byte Busters', role='Bidding Team', email='contact@busters.org', 
                       bio='Mentored by Anju ma\'am. A crowd favorite, known for taking risks.', 
                       image_url='/static/byte_busters.jpg',
                       video_url='/static/byte_busters_video.mp4'),
                Person(name='Syntax Samurai', role='Bidding Team', email='master@samurai.io', 
                       bio='Mentored by Vivek Gaur Sir & Madan Sir. They strike with precision.', 
                       image_url='/static/syntax_samurai.jpg',
                       video_url='/static/syntax_samurai_video.mp4'),
                Person(name='Ruby Renegades', role='Bidding Team', email='hello@renegades.rb', 
                       bio='Mentored by Abhishek Sir & Santosh Kumar Agarwal Sir. The dark horse team.', 
                       image_url='/static/ruby_renegades.jpg',
                       video_url='/static/ruby_renegades_video.mp4'),
                Person(name='Java Jesters', role='Bidding Team', email='captains@jesters.com', 
                       bio='Mentored by Santosh Sharma Sir. Known for meticulous planning.', 
                       image_url='/static/java_jesters.jpg',
                       video_url='/static/java_jesters_video.mp4'),
                Person(name='Python Pioneers', role='Bidding Team', email='team@pioneers.py', 
                       bio='Mentored by Seema Mam & Archana Mam. Specialists in data science.', 
                       image_url='/static/python_pioneers.jpg',
                       video_url='/static/python_pioneers_video.mp4'),
                Person(name='Quantum Coders', role='Bidding Team', email='lead@quantum.dev', 
                       bio='Mentored by Pankaj Sir. A mysterious team with deep pockets.', 
                       image_url='/static/quantum_coder.jpg',
                       video_url='/static/quantum_coder_video.mp4'),
                Person(name='Code Trail', role='Bidding Team', email='lead@codetrail.com', 
                       bio='Mentored by Gurminder Sir. The newest team to join the battle.', 
                       image_url='/static/code_trail.jpg',
                       video_url='/static/code_trail_video.mp4'), 
                Person(name='Data Mavericks', role='Bidding Team', email='scouts@mavericks.db', 
                       bio='Mentored by B. Pathak Sir. Focused on backend superstars.', 
                       image_url='/static/data_mavericks.jpg',
                       video_url='/static/data_mavericks_video.mp4'),
                Person(name='Code Commanders', role='Bidding Team', email='hq@commanders.com', 
                       bio='Mentored by Puneet Sir. Strategic and disciplined budget management.', 
                       image_url='/static/code_commanders.jpg',
                       video_url='/static/code_commanders_video.mp4'),
                Person(name='Logic Luminaries', role='Bidding Team', email='info@luminaries.ai', 
                       bio='Mentored by Vishambhar Pathak Sir. Data-driven and analytical.', 
                       image_url='/static/logic_luminaries.jpg',
                       video_url='/static/logic_luminaries_video.mp4'),

                
                # FACULTY & MENTORS
                Person(name='Anju Ma\'am', role='Faculty Mentor', email='anju@college.edu',
                       bio='Mentor for Byte Busters.',
                       image_url='/static/anju_mam.png'),
                Person(name='Vivek Gaur Sir', role='Faculty Mentor', email='vivek@college.edu',
                       bio='Mentor for Syntax Samurai.',
                       image_url='/static/vivek_gaur_sir.png'),
                Person(name='Madan Sir', role='Faculty Mentor', email='madan@college.edu',
                       bio='Mentor for Syntax Samurai.',
                       image_url='/static/madan_sir.png'),
                Person(name='Abhishek Sir', role='Faculty Mentor', email='abhishek@college.edu',
                       bio='Mentor for Ruby Renegades.',
                       image_url='/static/abhishek_sir.png'),
                Person(name='Santosh Kumar Agarwal Sir', role='Faculty Mentor', email='santosh.ka@college.edu',
                       bio='Mentor for Ruby Renegades.',
                       image_url='/static/santosh_k_agarwal_sir.png'),
                Person(name='Santosh Sharma Sir', role='Faculty Mentor', email='santosh.s@college.edu',
                       bio='Mentor for Java Jesters.',
                       image_url='/static/santosh_sharma_sir.png'),
                Person(name='Seema Mam', role='Faculty Mentor', email='seema@college.edu',
                       bio='Mentor for Python Pioneers.',
                       image_url='/static/seema_mam.png'),
                Person(name='Archana Mam', role='Faculty Mentor', email='archana@college.edu',
                       bio='Mentor for Python Pioneers.',
                       image_url='/static/archana_mam.png'),
                Person(name='Pankaj Sir', role='Faculty Mentor', email='pankaj@college.edu',
                       bio='Mentor for Quantum Coders.',
                       image_url='/static/pankaj_sir.png'),
                Person(name='Gurminder Sir', role='Faculty Mentor', email='gurminder@college.edu',
                       bio='Mentor for Code Trail.',
                       image_url='/static/gurminder_sir.png'),
                Person(name='Dr. B. Pathak Sir', role='Faculty Mentor', email='bp@college.edu',
                       bio='Mentor for Data Mavericks.',
                       image_url='/static/b_pathak_sir.png'),
                Person(name='Puneet Sir', role='Faculty Mentor', email='puneet@college.edu',
                       bio='Mentor for Code Commanders.',
                       image_url='/static/puneet_sir.png'),
                Person(name='Dr. Vishambhar Pathak Sir', role='Faculty Mentor', email='vp@college.edu',
                       bio='Mentor for Logic Luminaries.',
                       image_url='/static/vishambhar_pathak_sir.png'),
            ]
            session.add_all(people)
        
        if session.query(Setting).count() == 0:
            print("🌱 Seeding Auction Timer...")
            end_time = (datetime.utcnow() + timedelta(hours=72)).isoformat()
            session.add(Setting(id=1, end_time=end_time))
            
        session.commit()
        print('✅ Database initialized successfully!')
    except Exception as e:
        print(f"🔥 ERROR seeding data: {e}")
        session.rollback()
    finally:
        Session.remove()

# ============================================================================
# DAILY POLL RESET FUNCTION
# ============================================================================
def reset_poll_votes():
    print("⏰ EXECUTING DAILY POLL RESET...")
    session = session_factory()
    try:
        session.query(Poll).update({Poll.votes: 0})
        session.commit()
        print("✅ Polls reset successfully.")
        socketio.emit('poll_update', {})
    except Exception as e:
        print(f"🔥 ERROR during poll reset: {e}")
        session.rollback()
    finally:
        session.close()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_activity(type, description):
    session = Session()
    try:
        new_activity = ActivityLog(type=type, description=description)
        session.add(new_activity)
        session.commit()
        session.refresh(new_activity) 
        activity_data = {
            'id': new_activity.id,
            'type': new_activity.type,
            'description': new_activity.description,
            'timestamp': new_activity.timestamp.isoformat()
        }
        socketio.emit('activity_update', activity_data)
    except Exception as e:
        print(f"🔥 ERROR in log_activity: {e}")
        session.rollback()
    finally:
        Session.remove()

def model_to_dict(model_instance):
    return {c.name: getattr(model_instance, c.name) for c in model_instance.__table__.columns}

# ============================================================================
# FLASK API ROUTES
# ============================================================================

@app.teardown_appcontext
def shutdown_session(exception=None):
    Session.remove()

@app.route('/api/players')
def api_players():
    players = Session.query(Player).order_by(Player.current_bid.desc()).all()
    return jsonify([model_to_dict(p) for p in players])

@app.route('/api/players/<int:player_id>')
def api_player_detail(player_id):
    player = Session.query(Player).filter_by(id=player_id).first()
    if not player:
        return jsonify({'error': 'Not found'}), 404
    player_data = model_to_dict(player)
    bids = Session.query(Bid).filter_by(player_id=player_id).order_by(Bid.timestamp.desc()).limit(10).all()
    player_data['bid_history'] = [
        {'bidder_name': b.bidder_name, 'bid_amount': b.bid_amount, 'timestamp': b.timestamp.isoformat()} 
        for b in bids
    ]
    return jsonify(player_data)

# --- THIS IS YOUR UPDATED FUNCTION ---
@app.route('/api/bid', methods=['POST'])
def api_place_bid():
    """Submits a new bid for a player."""
    session = Session()
    try:
        data = request.json
        player_id = data.get('player_id')
        bidder_name = data.get('bidder_name')
        bid_amount = int(data.get('bid_amount'))
        
        player = session.query(Player).filter_by(id=player_id).first()
        if not player:
            return jsonify({'error': 'Player not found'}), 404
        
        if bid_amount <= player.current_bid:
            return jsonify({'error': f'Bid must be higher than ${player.current_bid:,}'}), 400
        
        # Save the player's name before the commit (prevents detached-instance error)
        player_name = player.name
        
        player.current_bid = bid_amount
        player.highest_bidder = bidder_name
        player.total_bids += 1
        
        new_bid = Bid(player_id=player_id, bidder_name=bidder_name, bid_amount=bid_amount)
        session.add(new_bid)
        
        session.commit()
        
        # Use the saved variable (player_name)
        log_activity('bid', f'{bidder_name} bid ${bid_amount:,} on {player_name}')
        
        socketio.emit('bid_update', {
            'player_id': player_id,
            'player_name': player_name,
            'bidder_name': bidder_name,
            'bid_amount': bid_amount
        })
        
        return jsonify({'success': True, 'message': 'Bid placed successfully!'})
    
    except Exception as e:
        print(f"🔥 ERROR in api_place_bid: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()  # close the session you actually opened
# --- END OF YOUR UPDATED FUNCTION ---

@app.route('/api/enquiry', methods=['POST'])
def api_enquiry():
    session = Session()
    try:
        data = request.json
        new_enquiry = Enquiry(
            name=data.get('name'),
            email=data.get('email'),
            message=data.get('message')
        )
        session.add(new_enquiry)
        session.commit()
        log_activity('enquiry', f'New enquiry from {data.get("name")}')
        return jsonify({'success': True, 'message': 'Enquiry submitted successfully!'})
    except Exception as e:
        print(f"🔥 ERROR in api_enquiry: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        Session.remove()

@app.route('/api/poll')
def api_poll():
    teams = Session.query(Poll).order_by(Poll.votes.desc()).all()
    return jsonify([model_to_dict(t) for t in teams])

@app.route('/api/poll/vote', methods=['POST'])
def api_vote():
    session = Session()
    try:
        team_name = request.json.get('team_name')
        team = session.query(Poll).filter_by(team_name=team_name).first()
        if not team:
            return jsonify({'error': 'Team not found'}), 404
        team.votes = team.votes + 1
        session.commit()
        log_activity('poll', f'Vote cast for {team_name}')
        socketio.emit('poll_update', {})
        return jsonify({'success': True})
    except Exception as e:
        print(f"🔥 ERROR in api_vote: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        Session.remove()

@app.route('/api/people')
def api_people():
    response = {
        "coordinators": [model_to_dict(p) for p in Session.query(Person).filter(Person.role == 'Head Coordinator').order_by(Person.name).all()],
        "teams": [model_to_dict(p) for p in Session.query(Person).filter(Person.role == 'Bidding Team').order_by(Person.name).all()],
        "faculty": [model_to_dict(p) for p in Session.query(Person).filter(Person.role.like('%Faculty%')).order_by(Person.name).all()]
    }
    return jsonify(response)

@app.route('/api/activity')
def api_activity():
    activities = Session.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(30).all()
    return jsonify([model_to_dict(a) for a in activities])

@app.route('/api/status')
def api_status():
    session = Session()
    try:
        setting = session.query(Setting).filter_by(id=1).first()
        if not setting:
            print("⚠️ No settings found, reseeding data...")
            seed_data()
            setting = session.query(Setting).filter_by(id=1).first()
            if not setting:
                return jsonify({'error': 'Failed to initialize settings'}), 500

        end_time_str = setting.end_time
        end_time = datetime.fromisoformat(end_time_str)
        remaining = (end_time - datetime.utcnow()).total_seconds()
        
        total_bids = session.query(func.count(Bid.id)).scalar()
        total_value = session.query(func.sum(Player.current_bid)).scalar() or 0
        
        return jsonify({
            'end_time': end_time_str,
            'time_remaining': max(0, remaining),
            'total_bids': total_bids,
            'total_value': total_value
        })
    except Exception as e:
        print(f"🔥 ERROR in api_status: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        Session.remove()

@app.route('/health')
def health_check():
    """Health check for Render."""
    try:
        session = Session()
        session.execute('SELECT 1')
        Session.remove()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        print(f"💔 Health check failed: {e}")
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 500

# ============================================================================
# STATIC FILE ROUTE
# ============================================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """This route serves all files from your 'static' folder."""
    return send_from_directory(app.static_folder, filename)

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

def initialize_database():
    print("Initializing database...")
    retries = 5
    for i in range(retries):
        try:
            Base.metadata.create_all(engine)
            print("✅ Database tables created (if they didn't exist).")
            seed_data()
            break
        except OperationalError as e:
            print(f"🔥 Database connection failed (attempt {i+1}/{retries}): {e}")
            gevent.sleep(5) 
    else:
        print("🔥 CRITICAL: Could not connect to database after retries. Exiting.")
        sys.exit(1)


def start_server():
    print('\n' + '='*80)
    print('🏆 BATTLE OF BYTES 2.0 - PRODUCTION AUCTION (POSTGRESQL + STATIC FILES)')
    print('='*80)
    
    initialize_database()
    
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(reset_poll_votes, trigger=CronTrigger(hour=0, minute=0))
        scheduler.start()
        print("⏰ Daily poll reset job scheduled for midnight.")
    except Exception as e:
        print(f"🔥 FAILED to start scheduler: {e}")

    port = int(os.environ.get('PORT', 5000))
    
    print(f"\n🚀 Starting server on http://0.0.0.0:{port}")
    print(f"📁 Serving static files from: {STATIC_FOLDER}")
    print('='*80 + '\n')
    
    socketio.run(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    start_server()
