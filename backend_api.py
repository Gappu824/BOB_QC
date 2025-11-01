#!/usr/bin/env python3
"""
BATTLE OF BYTES - PRODUCTION AUCTION PLATFORM v17 (POSTGRESQL-READY)
=====================================================================
- Uses PostgreSQL for persistent data on Render's free tier
- Uses SQLAlchemy ORM instead of raw sqlite3
- All API endpoints and WebSocket logic are the same
- Includes APScheduler to reset polls daily (meets bonus requirement)
"""

import os
import sys
import json
from datetime import datetime, timedelta
import threading
import gevent  # For production server
from apscheduler.schedulers.background import BackgroundScheduler # For poll reset
from apscheduler.triggers.cron import CronTrigger # For poll reset

# Install dependencies
print('📦 Installing dependencies...')
# NEW: Added sqlalchemy and psycopg2-binary for PostgreSQL
os.system(f'{sys.executable} -m pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent sqlalchemy psycopg2-binary -q 2>/dev/null')

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
    
    # NEW: SQLAlchemy imports
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
# APPLICATION SETUP (NEW: POSTGRESQL)
# ============================================================================

# NEW: Database connection setup
# Render will provide this DATABASE_URL as an environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("🔥 ERROR: DATABASE_URL environment variable not set.")
    print("Please create a PostgreSQL database on Render and set this variable.")
    # Fallback to a local SQLite DB for testing if you want
    # DATABASE_URL = 'sqlite:///./local_auction.db' 
    # For now, we'll exit if it's not set for production
    sys.exit(1)

# Fix for Render's PostgreSQL URL if it starts with 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"📁 Connecting to database...")

try:
    engine = create_engine(DATABASE_URL)
    Base = declarative_base()
    # Use scoped_session for thread-safe session management in Flask
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
except Exception as e:
    print(f"🔥 Failed to connect to database: {e}")
    sys.exit(1)

print("✅ Database connection initiated.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'auction-secret-2025'
CORS(app) 
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ============================================================================
# DATABASE MODELS (NEW: SQLAlchemy ORM)
# ============================================================================

# This replaces all the 'CREATE TABLE' SQL commands
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
    role = Column(String) # 'Head Coordinator', 'Bidding Team', 'Faculty Advisor'
    email = Column(String)
    bio = Column(Text)
    image_url = Column(String)
    social_handle = Column(String)

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
# DATABASE SEEDING (NEW: SQLAlchemy)
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
            print("🌱 Seeding Poll Teams...")
            teams = [
                Poll(team_name='Java Jesters'), Poll(team_name='Quantum Coder'), Poll(team_name='Syntax Samurai'),
                Poll(team_name='Logic Luminaries'), Poll(team_name='Byte Busters'), Poll(team_name='Python Pioneers'),
                Poll(team_name='Code Commanders'), Poll(team_name='Ruby Renegades'), Poll(team_name='Data Mavericks'),
            ]
            session.add_all(teams)

        if session.query(Person).count() == 0:
            print("🌱 Seeding People (Coordinators, Teams, Faculty)...")
            people = [
                Person(name='Hiya Arya', role='Head Coordinator', email='hiya@battleofbytes.com', 
                       bio='Promotion & Operation Lead for Battle of Bytes 2.0', image_url='https://i.pravatar.cc/300?img=1', social_handle='@hushhiya'),
                Person(name='Ashank Agrawal', role='Head Coordinator', email='ashank@battleofbytes.com',
                       bio='Co Tech Lead orchestrating the technical aspects', image_url='https://i.pravatar.cc/300?img=2', social_handle='@ashankagrawal'),
                Person(name='Java Jesters', role='Bidding Team', email='captains@jesters.com', 
                       bio='Known for meticulous planning and aggressive bidding strategies.', 
                       image_url='https://i.pravatar.cc/300?img=5'),
                Person(name='Quantum Coder', role='Bidding Team', email='lead@quantum.dev', 
                       bio='A mysterious team with deep pockets.', 
                       image_url='https://i.pravatar.cc/300?img=6'),
                Person(name='Dr. Priya Sharma', role='Faculty Advisor', email='p.sharma@college.edu', 
                       bio='Head Faculty Coordinator overseeing all event logistics.', 
                       image_url='https://i.pravatar.cc/300?img=60'),
                Person(name='Prof. Rajesh Kumar', role='Faculty Judge', email='r.kumar@college.edu', 
                       bio='Lead judge and auction overseer ensuring fair play.', 
                       image_url='https://i.pravatar.cc/300?img=61'),
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
# DAILY POLL RESET FUNCTION (UPDATED FOR SQLAlchemy)
# ============================================================================
def reset_poll_votes():
    """
    Connects to the DB and resets all poll votes to 0.
    This meets the "Poll results should reset daily" requirement.
    """
    print("⏰ EXECUTING DAILY POLL RESET...")
    # Use a new session from the factory for the background thread
    session = session_factory()
    try:
        session.query(Poll).update({Poll.votes: 0})
        session.commit()
        print("✅ Polls reset successfully.")
        
        # Emit a socket event to all clients to refresh their poll data
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
    """Logs an event to the DB and emits it to all connected clients."""
    session = Session()
    try:
        new_activity = ActivityLog(type=type, description=description)
        session.add(new_activity)
        session.commit()
        
        # Re-fetch to get timestamp and ID
        session.refresh(new_activity) 
        
        # Convert to dict for JSON serialization
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

# Helper to convert SQLAlchemy model to dict
def model_to_dict(model_instance):
    return {c.name: getattr(model_instance, c.name) for c in model_instance.__table__.columns}

# ============================================================================
# FLASK API ROUTES (UPDATED FOR SQLAlchemy)
# ============================================================================

# This ensures the session is removed after each request
@app.teardown_appcontext
def shutdown_session(exception=None):
    Session.remove()

@app.route('/api/players')
def api_players():
    """Gets a list of all players."""
    players = Session.query(Player).order_by(Player.current_bid.desc()).all()
    return jsonify([model_to_dict(p) for p in players])

@app.route('/api/players/<int:player_id>')
def api_player_detail(player_id):
    """Gets detailed info for a single player, including bid history."""
    player = Session.query(Player).filter_by(id=player_id).first()
    
    if not player:
        return jsonify({'error': 'Not found'}), 404
    
    player_data = model_to_dict(player)
    # Get top 10 bids
    bids = Session.query(Bid).filter_by(player_id=player_id).order_by(Bid.timestamp.desc()).limit(10).all()
    player_data['bid_history'] = [
        {'bidder_name': b.bidder_name, 'bid_amount': b.bid_amount, 'timestamp': b.timestamp.isoformat()} 
        for b in bids
    ]
    
    return jsonify(player_data)

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
        
        # Update player
        player.current_bid = bid_amount
        player.highest_bidder = bidder_name
        player.total_bids = player.total_bids + 1
        
        # Add new bid record
        new_bid = Bid(player_id=player_id, bidder_name=bidder_name, bid_amount=bid_amount)
        session.add(new_bid)
        
        session.commit()
        
        log_activity('bid', f'{bidder_name} bid ${bid_amount:,} on {player.name}')
        
        socketio.emit('bid_update', {
            'player_id': player_id,
            'player_name': player.name,
            'bidder_name': bidder_name,
            'bid_amount': bid_amount
        })
        
        return jsonify({'success': True, 'message': 'Bid placed successfully!'})
    except Exception as e:
        print(f"🔥 ERROR in api_place_bid: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        Session.remove()

@app.route('/api/enquiry', methods=['POST'])
def api_enquiry():
    """Submits a contact form message."""
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
    """Gets the current poll results."""
    teams = Session.query(Poll).order_by(Poll.votes.desc()).all()
    return jsonify([model_to_dict(t) for t in teams])

@app.route('/api/poll/vote', methods=['POST'])
def api_vote():
    """Submits a vote for a team."""
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
    """Gets all coordinators, teams, and faculty."""
    response = {
        "coordinators": [model_to_dict(p) for p in Session.query(Person).filter(Person.role == 'Head Coordinator').order_by(Person.name).all()],
        "teams": [model_to_dict(p) for p in Session.query(Person).filter(Person.role == 'Bidding Team').order_by(Person.name).all()],
        "faculty": [model_to_dict(p) for p in Session.query(Person).filter(Person.role.like('%Faculty%')).order_by(Person.name).all()]
    }
    return jsonify(response)

@app.route('/api/activity')
def api_activity():
    """Gets the 30 most recent activity items."""
    activities = Session.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(30).all()
    return jsonify([model_to_dict(a) for a in activities])

@app.route('/api/status')
def api_status():
    """Gets auction stats (timer, total bids, total value)."""
    session = Session()
    try:
        setting = session.query(Setting).filter_by(id=1).first()
        if not setting:
            # This should only happen once
            print("⚠️ No settings found, reseeding data...")
            seed_data() # Re-run seed to create settings
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

# Simple health-check route for Render
@app.route('/health')
def health_check():
    # NEW: Check DB connection as part of health check
    try:
        session = Session()
        session.execute('SELECT 1')
        Session.remove()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        print(f"💔 Health check failed: {e}")
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 500

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
            # This command creates all the tables
            Base.metadata.create_all(engine)
            print("✅ Database tables created (if they didn't exist).")
            # Seed the database
            seed_data()
            break
        except OperationalError as e:
            print(f"🔥 Database connection failed (attempt {i+1}/{retries}): {e}")
            gevent.sleep(5) # Wait 5 seconds before retrying
    else:
        print("🔥 CRITICAL: Could not connect to database after retries. Exiting.")
        sys.exit(1)


def start_server():
    print('\n' + '='*80)
    print('🏆 BATTLE OF BYTES 2.0 - PRODUCTION AUCTION (POSTGRESQL API)')
    print('='*80)
    
    # NEW: Initialize DB *before* starting the scheduler or server
    initialize_database()
    
    # Initialize and start the scheduler for daily poll reset
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(reset_poll_votes, trigger=CronTrigger(hour=0, minute=0))
        scheduler.start()
        print("⏰ Daily poll reset job scheduled for midnight.")
    except Exception as e:
        print(f"🔥 FAILED to start scheduler: {e}")

    port = int(os.environ.get('PORT', 5000))
    
    print(f'\n🚀 Starting server on http://0.0.0.0:{port}')
    print('='*80 + '\n')
    
    socketio.run(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    start_server()