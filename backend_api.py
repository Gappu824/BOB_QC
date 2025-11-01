#!/usr/bin/env python3
"""
BATTLE OF BYTES - PRODUCTION BACKEND (GOOGLE DRIVE HOSTED)
==========================================================
✅ All images hosted on Google Drive (free)
✅ Using direct download links
✅ Works on Render free tier
"""

import os
import sys
from datetime import datetime, timedelta
import gevent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

print('📦 Installing dependencies...')
os.system(f'{sys.executable} -m pip install flask flask-cors flask-socketio simple-websocket apscheduler gevent sqlalchemy psycopg2-binary -q 2>/dev/null')

try:
    from flask import Flask, request, jsonify, send_from_directory, render_template_string
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
    from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func, text
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, scoped_session, relationship
    from sqlalchemy.exc import OperationalError, ProgrammingError
except ImportError:
    print("\n❌ ERROR: Failed to import libraries")
    sys.exit(1)

print('✅ Dependencies loaded!\n')

# DATABASE SETUP
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///auction.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"📁 Connecting to database...")
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base = declarative_base()
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
except Exception as e:
    print(f"🔥 Database connection failed: {e}")
    sys.exit(1)
print("✅ Database connected")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'auction-secret-2025'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Google Drive Base URL - Convert sharing links to direct download
# Format: https://drive.google.com/uc?export=view&id=FILE_ID
GDRIVE_BASE = "https://drive.google.com/uc?export=view&id="

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
    image_url = Column(String)
    video_url = Column(String)

class Person(Base):
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    role = Column(String)
    email = Column(String)
    bio = Column(Text)
    image_url = Column(String)
    social_handle = Column(String)
    video_url = Column(String)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    end_time = Column(String)

# ============================================================================
# DATABASE MIGRATION
# ============================================================================

def migrate_database():
    """Add image_url and video_url columns to poll table if they don't exist"""
    print("🔧 Checking database schema...")
    try:
        session = Session()
        result = session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='poll' AND column_name IN ('image_url', 'video_url')"))
        existing_columns = [row[0] for row in result]
        
        if 'image_url' not in existing_columns:
            print("  ➕ Adding image_url column...")
            session.execute(text("ALTER TABLE poll ADD COLUMN image_url VARCHAR"))
            session.commit()
            print("  ✅ Added image_url")
        
        if 'video_url' not in existing_columns:
            print("  ➕ Adding video_url column...")
            session.execute(text("ALTER TABLE poll ADD COLUMN video_url VARCHAR"))
            session.commit()
            print("  ✅ Added video_url")
        
        if 'image_url' in existing_columns and 'video_url' in existing_columns:
            print("  ✅ Schema up to date")
        
        Session.remove()
    except Exception as e:
        print(f"  ⚠️ Migration note: {e}")
        Session.remove()

# ============================================================================
# GOOGLE DRIVE FILE IDs (Extract from your shared folder)
# ============================================================================
# YOU NEED TO REPLACE THESE WITH ACTUAL FILE IDs FROM YOUR GOOGLE DRIVE

GDRIVE_FILES = {
    # Players (10)
    'abhinav_gupta': '1draCBk7T2CTGlipR79rKtoK5-SEE44b6',
    'manisha_parwani': '1nM9xCPEhY0KH-wlIBydyE_quZ6b-WnEh',
    'aviral_sharma': '1fNi8FjNvo8ZF6Hhi35je0a7vqncOI456',
    'shruti_khandelwal': '1bRRmCgBxCcaCVv7SJkhkGQedewFIac3k',
    'karan_parwani': '1wMBHbmzKKJ5wy2qstMxsVc5tBCNcLAGk',
    'naina_pancholi': '1f8GtGMuwKSjg7arm6prlG_o1mj7ubfYh',
    'hemang_bhabhra': '1o0pP18JIBF-FIpJlRTP7liJPbjTlhh2A',
    'yashika_sharma': '1tqK20-4gK3olRlO1iLMoZhqGCjKsow5w',
    'piyush_dhakad': '1i2vOrN3xiUKkdj84ZmO5FYd1Y3X1dp6G',
    'anuj_sharma': '1FX1e2iOgKU7iXORwxIqQqqq84kLigoZP',
    
    # Teams (10)
    'byte_busters': '1PxmHD0QVma-uFqh7ebPTb2LmADXCSHvM',
    'syntax_samurai': '1XCLlvzHbqJo_eFhSD4iE1bgKWVhnf9VF',
    'ruby_renegades': '1L7b8ntBK70uvUBHVBdmBYlDnrgJSYNg2',
    'java_jesters': '1-tUbPMMDuiY8bK1RQZiLiYJqHlVtUX2v',
    'python_pioneers': '185eEp_PCo0ZWrbIMyK6uG4Oup566pZ-1',
    'quantum_coder': '1FqLX_tW2M7W99WdykM3Ytr_u4fTlM0Kz',
    'code_trail': '1y4KOQPSIvZLtyLzJg5G6ezn0OsuStJJ9',
    'data_mavericks': '1fp0aAPfAHG_zQpZIajbqFu0h4Vucd65P',
    'code_commanders': '1y4KOQPSIvZLtyLzJg5G6ezn0OsuStJJ9',
    'logic_luminaries': '1ZIv-YBcSL0w0BgolFpDwsw0OSKZIgIhG',
    
    # Coordinators (5)
    'hiya_arya': '1PS3tvNFlRqHD7Bkk1j65aKS8E2HRDFsM',
    'ashank_agrawal': '1x9znzotyB5m_GtHXQksccn9e8otPuTzp',
    'sarthak_sinha': '19hBvipViWQppFZRhh14ZRxJ85ACXLWzn',
    'manalika_agarwal': '1xufWMXWBNqpN0QbfTV_lIUMQrJ5umYFX',
    'somya_upadhyay': '1um7e3fBVlqHDEsMpllpzQhGrh5yrHSv1',
    
    # Faculty (2)
    'shripal_sir': '1Z8gGZpv2zLgMe6slvlm5Qor1TX8DA_-M',
    'piyush_sir': '1VaCgOKu-OAXFZE-1_WxTuYER7Qfi-2hd',
}

def gdrive_url(key):
    """Generate Google Drive direct link"""
    file_id = GDRIVE_FILES.get(key, '')
    if file_id and file_id != 'YOUR_FILE_ID_HERE':
        return f"{GDRIVE_BASE}{file_id}"
    return f"https://via.placeholder.com/300x300/333/fff?text={key}"  # Fallback

# ============================================================================
# DATABASE SEEDING (WITH GOOGLE DRIVE URLS)
# ============================================================================

def seed_data():
    session = Session()
    try:
        # Clear existing data
        if session.query(Player).count() > 0:
            print("🗑️ Clearing old player data...")
            session.query(Bid).delete()
            session.query(Player).delete()
            session.commit()
        
        print("🌱 Seeding Players (10 participants with Google Drive URLs)...")
        players = [
            Player(id=1, name='Abhinav Gupta', nickname='The Strategist', role='BTECH/25006/23', 
                   base_price=10000, current_bid=10000,
                   image_url=gdrive_url('abhinav_gupta'),
                   bio='DBMS: ⭐⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=2, name='Manisha Parwani', nickname='Code Ninja', role='BTECH/25063/23',
                   base_price=12000, current_bid=12000,
                   image_url=gdrive_url('manisha_parwani'),
                   bio='DBMS: ⭐⭐⭐ | Python: ⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=3, name='Aviral Sharma', nickname='Data Wizard', role='BTECH/25150/23',
                   base_price=15000, current_bid=15000,
                   image_url=gdrive_url('aviral_sharma'),
                   bio='DBMS: ⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=4, name='Shruti Khandelwal', nickname='Cloud Queen', role='MCA/25015/25',
                   base_price=11000, current_bid=11000,
                   image_url=gdrive_url('shruti_khandelwal'),
                   bio='DBMS: ⭐⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=5, name='Karan Parwani', nickname='Full Stack Pro', role='MCA/25007/25',
                   base_price=13000, current_bid=13000,
                   image_url=gdrive_url('karan_parwani'),
                   bio='DBMS: ⭐⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=6, name='Naina V Pancholi', nickname='Backend Expert', role='BTECH/25030/22',
                   base_price=14000, current_bid=14000,
                   image_url=gdrive_url('naina_pancholi'),
                   bio='DBMS: ⭐⭐⭐ | Python: ⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=7, name='Hemang Bhabhra', nickname='Algorithm Master', role='BTECH/25027/22',
                   base_price=12500, current_bid=12500,
                   image_url=gdrive_url('hemang_bhabhra'),
                   bio='DBMS: ⭐⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=8, name='Yashika Sharma', nickname='Frontend Wizard', role='MSCAI/25002/25',
                   base_price=11500, current_bid=11500,
                   image_url=gdrive_url('yashika_sharma'),
                   bio='DBMS: ⭐⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=9, name='Piyush Singh Dhakad', nickname='DevOps Guru', role='MSCAI/25005/25',
                   base_price=13500, current_bid=13500,
                   image_url=gdrive_url('piyush_dhakad'),
                   bio='DBMS: ⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
            
            Player(id=10, name='Anuj Sharma', nickname='ML Engineer', role='MCA/25022/25',
                   base_price=12000, current_bid=12000,
                   image_url=gdrive_url('anuj_sharma'),
                   bio='DBMS: ⭐⭐⭐⭐ | Python: ⭐⭐⭐⭐ | C/C++: ⭐⭐⭐⭐ | Java: ⭐⭐⭐⭐⭐ | DSA: ⭐⭐⭐⭐',
                   skills='DBMS,Python,C/C++,Java,DSA', total_bids=0),
        ]
        session.add_all(players)
        
        if session.query(Poll).count() == 0:
            print("🌱 Seeding Poll Teams...")
            teams = [
                Poll(team_name='Byte Busters', image_url=gdrive_url('byte_busters'), video_url=''),
                Poll(team_name='Syntax Samurai', image_url=gdrive_url('syntax_samurai'), video_url=''),
                Poll(team_name='Ruby Renegades', image_url=gdrive_url('ruby_renegades'), video_url=''),
                Poll(team_name='Java Jesters', image_url=gdrive_url('java_jesters'), video_url=''),
                Poll(team_name='Python Pioneers', image_url=gdrive_url('python_pioneers'), video_url=''),
                Poll(team_name='Quantum Coders', image_url=gdrive_url('quantum_coder'), video_url=''),
                Poll(team_name='Code Trail', image_url=gdrive_url('code_trail'), video_url=''),
                Poll(team_name='Data Mavericks', image_url=gdrive_url('data_mavericks'), video_url=''),
                Poll(team_name='Code Commanders', image_url=gdrive_url('code_commanders'), video_url=''),
                Poll(team_name='Logic Luminaries', image_url=gdrive_url('logic_luminaries'), video_url=''),
            ]
            session.add_all(teams)

        if session.query(Person).count() > 0:
            print("🗑️ Clearing old people data...")
            session.query(Person).delete()
            session.commit()
        
        print("🌱 Seeding People...")
        people = [
            # HEAD COORDINATORS
            Person(name='Hiya Arya', role='Head Coordinator', email='hiya@bob.com', 
                   bio='Promotion & Operation Lead', 
                   image_url=gdrive_url('hiya_arya'), 
                   social_handle='@hushhiya'),
            Person(name='Ashank Agrawal', role='Head Coordinator', email='ashank@bob.com',
                   bio='Co Tech Lead', 
                   image_url=gdrive_url('ashank_agrawal'), 
                   social_handle='@ashankagrawal'),
            Person(name='Sarthak Sinha', role='Head Coordinator', email='sarthak@bob.com',
                   bio='Design & Social Media Lead', 
                   image_url=gdrive_url('sarthak_sinha'), 
                   social_handle='@sarthak.sinhahaha'),
            Person(name='Manalika Agarwal', role='Head Coordinator', email='manalika@bob.com',
                   bio='Co Tech Lead', 
                   image_url=gdrive_url('manalika_agarwal'), 
                   social_handle='@manalika__'),
            Person(name='Somya Upadhyay', role='Head Coordinator', email='somya@bob.com',
                   bio='Sponsorship Lead', 
                   image_url=gdrive_url('somya_upadhyay'), 
                   social_handle='@__.somyaaaaa__'),
            
            # BIDDING TEAMS
            Person(name='Byte Busters', role='Bidding Team', email='busters@team.com', 
                   bio='Mentored by Anju Ma\'am. Risk-takers and crowd favorites.',
                   image_url=gdrive_url('byte_busters'), video_url=''),
            Person(name='Syntax Samurai', role='Bidding Team', email='samurai@team.com', 
                   bio='Mentored by Vivek Gaur Sir & Madan Sir. Precision bidding experts.',
                   image_url=gdrive_url('syntax_samurai'), video_url=''),
            Person(name='Ruby Renegades', role='Bidding Team', email='renegades@team.com', 
                   bio='Mentored by Abhishek Sir & Santosh Kumar Agarwal Sir. The dark horse team.',
                   image_url=gdrive_url('ruby_renegades'), video_url=''),
            Person(name='Java Jesters', role='Bidding Team', email='jesters@team.com', 
                   bio='Mentored by Santosh Sharma Sir. Meticulous planners.',
                   image_url=gdrive_url('java_jesters'), video_url=''),
            Person(name='Python Pioneers', role='Bidding Team', email='pioneers@team.com', 
                   bio='Mentored by Seema Ma\'am & Archana Ma\'am. Data science specialists.',
                   image_url=gdrive_url('python_pioneers'), video_url=''),
            Person(name='Quantum Coders', role='Bidding Team', email='quantum@team.com', 
                   bio='Mentored by Pankaj Sir. Deep pockets, high potential focus.',
                   image_url=gdrive_url('quantum_coder'), video_url=''),
            Person(name='Code Trail', role='Bidding Team', email='trail@team.com', 
                   bio='Mentored by Gurminder Sir. Newest team with fresh tactics.',
                   image_url=gdrive_url('code_trail'), video_url=''),
            Person(name='Data Mavericks', role='Bidding Team', email='mavericks@team.com', 
                   bio='Mentored by B. Pathak Sir. Backend database experts.',
                   image_url=gdrive_url('data_mavericks'), video_url=''),
            Person(name='Code Commanders', role='Bidding Team', email='commanders@team.com', 
                   bio='Mentored by Puneet Sir. Strategic budget managers.',
                   image_url=gdrive_url('code_commanders'), video_url=''),
            Person(name='Logic Luminaries', role='Bidding Team', email='luminaries@team.com', 
                   bio='Mentored by Vishambhar Pathak Sir. Data-driven analysts.',
                   image_url=gdrive_url('logic_luminaries'), video_url=''),
            
            # FACULTY
            Person(name='Shripal Sir', role='Faculty Advisor', email='shripal@college.edu', 
                   bio='Senior faculty overseeing Battle of Bytes.', 
                   image_url=gdrive_url('shripal_sir')),
            Person(name='Piyush Sir', role='Faculty Advisor', email='piyush@college.edu', 
                   bio='Faculty coordinator managing logistics.', 
                   image_url=gdrive_url('piyush_sir')),
        ]
        session.add_all(people)
        
        if session.query(Setting).count() == 0:
            print("🌱 Seeding Auction Timer...")
            end_time = (datetime.utcnow() + timedelta(hours=72)).isoformat()
            session.add(Setting(id=1, end_time=end_time))
            
        session.commit()
        print('✅ Database seeded with Google Drive URLs!')
    except Exception as e:
        print(f"🔥 Seeding error: {e}")
        session.rollback()
    finally:
        Session.remove()

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
        socketio.emit('activity_update', {
            'id': new_activity.id,
            'type': new_activity.type,
            'description': new_activity.description,
            'timestamp': new_activity.timestamp.isoformat()
        })
    except Exception as e:
        print(f"⚠️ Activity log error: {e}")
        session.rollback()
    finally: 
        Session.remove()

def model_to_dict(model_instance):
    return {c.name: getattr(model_instance, c.name) for c in model_instance.__table__.columns}

def reset_poll_votes():
    print("⏰ Daily poll reset...")
    session = session_factory()
    try:
        session.query(Poll).update({Poll.votes: 0})
        session.commit()
        socketio.emit('poll_update', {})
        print("✅ Polls reset")
    except: 
        session.rollback()
    finally: 
        session.close()

# ============================================================================
# API ROUTES (Same as before)
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
    if not player: return jsonify({'error': 'Not found'}), 404
    player_data = model_to_dict(player)
    bids = Session.query(Bid).filter_by(player_id=player_id).order_by(Bid.timestamp.desc()).limit(10).all()
    player_data['bid_history'] = [
        {'bidder_name': b.bidder_name, 'bid_amount': b.bid_amount, 'timestamp': b.timestamp.isoformat()} 
        for b in bids
    ]
    return jsonify(player_data)

@app.route('/api/bid', methods=['POST'])
def api_place_bid():
    session = Session()
    try:
        data = request.json
        player_id = int(data['player_id'])
        bidder_name = data['bidder_name']
        bid_amount = int(data['bid_amount'])
        
        player = session.query(Player).filter_by(id=player_id).first()
        if not player: 
            return jsonify({'error': 'Player not found'}), 404
        
        if bid_amount <= player.current_bid:
            return jsonify({'error': f'Bid must be > ${player.current_bid:,}'}), 400
        
        player_name = player.name
        
        player.current_bid = bid_amount
        player.highest_bidder = bidder_name
        player.total_bids += 1
        
        new_bid = Bid(player_id=player_id, bidder_name=bidder_name, bid_amount=bid_amount)
        session.add(new_bid)
        session.commit()
        
        log_activity('bid', f"{bidder_name} bid ${bid_amount:,} on {player_name}")
        socketio.emit('bid_update', {
            'player_id': player_id,
            'player_name': player_name,
            'bidder_name': bidder_name,
            'bid_amount': bid_amount
        })
        return jsonify({'success': True, 'message': 'Bid placed!'})
    except Exception as e:
        print(f"🔥 BID ERROR: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally: 
        session.close()

@app.route('/api/enquiry', methods=['POST'])
def api_enquiry():
    session = Session()
    try:
        data = request.json
        session.add(Enquiry(name=data['name'], email=data['email'], message=data['message']))
        session.commit()
        log_activity('enquiry', f"Enquiry from {data['name']}")
        return jsonify({'success': True, 'message': 'Submitted!'})
    except: 
        session.rollback()
        return jsonify({'error': 'Failed'}), 500
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
        team = session.query(Poll).filter_by(team_name=request.json['team_name']).first()
        if not team: return jsonify({'error': 'Not found'}), 404
        team.votes += 1
        session.commit()
        log_activity('poll', f"Vote for {request.json['team_name']}")
        socketio.emit('poll_update', {})
        return jsonify({'success': True})
    except: 
        session.rollback()
        return jsonify({'error': 'Failed'}), 500
    finally: 
        Session.remove()

@app.route('/api/people')
def api_people():
    return jsonify({
        "coordinators": [model_to_dict(p) for p in Session.query(Person).filter_by(role='Head Coordinator').order_by(Person.name).all()],
        "teams": [model_to_dict(p) for p in Session.query(Person).filter_by(role='Bidding Team').order_by(Person.name).all()],
        "faculty": [model_to_dict(p) for p in Session.query(Person).filter_by(role='Faculty Advisor').order_by(Person.name).all()]
    })

@app.route('/api/activity')
def api_activity():
    activities = Session.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(30).all()
    return jsonify([model_to_dict(a) for a in activities])

@app.route('/api/status')
def api_status():
    try:
        session = Session()
        setting = session.query(Setting).filter_by(id=1).first()
        if not setting: 
            seed_data()
            setting = session.query(Setting).filter_by(id=1).first()
        end_time = datetime.fromisoformat(setting.end_time)
        remaining = (end_time - datetime.utcnow()).total_seconds()
        total_bids = session.query(func.count(Bid.id)).scalar()
        total_value = session.query(func.sum(Player.current_bid)).scalar() or 0
        return jsonify({
            'end_time': setting.end_time,
            'time_remaining': max(0, remaining),
            'total_bids': total_bids,
            'total_value': total_value
        })
    except Exception as e: 
        return jsonify({'error': str(e)}), 500
    finally: 
        Session.remove()

@app.route('/health')
def health_check():
    try:
        session = Session()
        session.execute(text('SELECT 1'))
        Session.remove()
        return jsonify({"status": "healthy"}), 200
    except: 
        return jsonify({"status": "unhealthy"}), 500

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>Battle of Bytes API</title></head>
    <body style="font-family:Arial;padding:40px;background:#0a0a0a;color:#fff;">
        <h1>🏆 Battle of Bytes API - Google Drive Hosted</h1>
        <p style="color:#ff6b6b;">⚠️ IMPORTANT: You need to add Google Drive file IDs to GDRIVE_FILES dictionary!</p>
        <h2>API Endpoints:</h2>
        <ul>
            <li><a href="/api/players" style="color:#0071e3;">/api/players</a></li>
            <li><a href="/api/poll" style="color:#0071e3;">/api/poll</a></li>
            <li><a href="/api/people" style="color:#0071e3;">/api/people</a></li>
        </ul>
    </body></html>
    """)

@socketio.on('connect')
def handle_connect(): 
    emit('connected', {'status': 'ok'})

@socketio.on('disconnect')
def handle_disconnect(): 
    pass

def initialize_database():
    print("🔧 Initializing database...")
    retries = 5
    for i in range(retries):
        try:
            Base.metadata.create_all(engine)
            print("✅ Tables created")
            migrate_database()
            seed_data()
            break
        except OperationalError as e:
            print(f"⚠️ Retry {i+1}/{retries}: {e}")
            gevent.sleep(5)
    else:
        print("🔥 CRITICAL: Database connection failed")
        sys.exit(1)

def start_server():
    print('\n' + '='*80)
    print('🏆 BATTLE OF BYTES 2.0 - GOOGLE DRIVE HOSTED')
    print('='*80)
    
    initialize_database()
    
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(reset_poll_votes, trigger=CronTrigger(hour=0, minute=0))
        scheduler.start()
        print("⏰ Daily poll reset scheduled")
    except: 
        pass

    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 Server: http://0.0.0.0:{port}")
    print(f"🌐 Images from: Google Drive")
    print(f"\n⚠️ Remember to add file IDs to GDRIVE_FILES!")
    print('='*80 + '\n')
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__': 
    start_server()
