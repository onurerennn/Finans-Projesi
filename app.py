from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pyodbc
import yfinance as yf
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Veritabanı bağlantı bilgileri
SERVER = 'DESKTOP-6HEB27D\\SQLEXPRESS'
DATABASE = 'StockDB'

# Veritabanı bağlantı fonksiyonu
def get_db_connection():
    try:
        conn = pyodbc.connect('DRIVER={SQL Server};SERVER='+SERVER+';DATABASE='+DATABASE+';Trusted_Connection=yes;')
        return conn
    except Exception as e:
        print(f"Veritabanı bağlantı hatası: {e}")
        return None

# Veritabanı tablolarını oluştur
def init_db():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Users tablosu
            cursor.execute('''
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
                CREATE TABLE users (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    username VARCHAR(50) UNIQUE,
                    password VARCHAR(50)
                )
            ''')
            
            # Favorites tablosu
            cursor.execute('''
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='favorites' AND xtype='U')
                CREATE TABLE favorites (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    user_id INT,
                    symbol VARCHAR(10),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # History tablosu
            cursor.execute('''
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='history' AND xtype='U')
                CREATE TABLE history (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    user_id INT,
                    symbol VARCHAR(10),
                    price FLOAT,
                    date DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            conn.commit()
            conn.close()
            print("Veritabanı tabloları başarıyla oluşturuldu")
    except Exception as e:
        print(f"Veritabanı başlatma hatası: {e}")

# Hisse senetleri listesi
STOCKS = [
    'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NFLX', 'META', 'NVDA', 'IBM', 'ORCL',
    'V', 'INTC', 'BA', 'DIS', 'GM', 'GE', 'PEP', 'KO', 'COST', 'PFE', 'JNJ',
    'CSCO', 'PYPL', 'AMD', 'WMT', 'INTU', 'SQ', 'MU', 'MDT', 'ABT', 'LMT',
    'MMM', 'CAT', 'RTX', 'T', 'MA', 'NVDA', 'BABA', 'NVAX', 'SPGI', 'ISRG',
    'MELI', 'FISV', 'TMUS', 'ACN', 'ZS', 'AMT', 'RBLX', 'XOM', 'CVX', 'TSM'
]

# Hisse senedi kategorileri
STOCK_CATEGORIES = {
    'Teknoloji': ['AAPL', 'GOOGL', 'MSFT', 'META', 'NVDA', 'IBM', 'ORCL', 'INTC', 'CSCO', 'AMD'],
    'E-ticaret': ['AMZN', 'BABA', 'WMT', 'MELI'],
    'Otomotiv': ['TSLA', 'GM'],
    'Medya': ['NFLX', 'DIS'],
    'Finans': ['V', 'MA', 'PYPL', 'SQ'],
    'Sağlık': ['PFE', 'JNJ', 'MDT', 'ABT', 'ISRG'],
    'Sanayi': ['GE', 'MMM', 'CAT', 'RTX', 'LMT'],
    'Tüketici': ['PEP', 'KO', 'COST'],
    'Telekomünikasyon': ['T', 'TMUS'],
    'Enerji': ['XOM', 'CVX'],
    'Diğer': ['NVAX', 'SPGI', 'FISV', 'ACN', 'ZS', 'AMT', 'RBLX', 'TSM']
}

# Login kontrolü için decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Favori hisseleri getir
def get_user_favorites():
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT symbol FROM favorites 
            WHERE user_id = ? 
            ORDER BY symbol
        """, (session['user_id'],))
        favorites = cursor.fetchall()
        return [{'symbol': row[0]} for row in favorites]
    except Exception as e:
        print(f"Favorileri getirme hatası: {e}")
        return []
    finally:
        conn.close()

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('stocks'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gereklidir', 'error')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        if not conn:
            flash('Veritabanı bağlantı hatası', 'error')
            return redirect(url_for('register'))
        
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                         (username, password))
            conn.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Kullanıcı adı zaten kullanımda!', 'error')
            return redirect(url_for('register'))
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gereklidir', 'error')
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        if not conn:
            flash('Veritabanı bağlantı hatası', 'error')
            return redirect(url_for('login'))
        
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", 
                         (username, password))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash('Başarıyla giriş yaptınız!', 'success')
                return redirect(url_for('stocks'))
            else:
                flash('Hatalı kullanıcı adı veya şifre!', 'error')
                return redirect(url_for('login'))
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Başarıyla çıkış yaptınız', 'success')
    return redirect(url_for('login'))

@app.route('/stocks')
@login_required
def stocks():
    conn = get_db_connection()
    if not conn:
        flash('Veritabanı bağlantı hatası', 'error')
        return redirect(url_for('login'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT symbol FROM favorites WHERE user_id = ?", (session['user_id'],))
        favorites = [(row[0],) for row in cursor.fetchall()]
        
        search = request.args.get('search', '').upper()
        category = request.args.get('category', '')
        
        if category and category in STOCK_CATEGORIES:
            filtered_stocks = STOCK_CATEGORIES[category]
        else:
            filtered_stocks = STOCKS
        
        if search:
            filtered_stocks = [stock for stock in filtered_stocks if search in stock]
        
        return render_template('stocks.html', 
                             stocks=filtered_stocks, 
                             favorites=favorites,
                             categories=STOCK_CATEGORIES.keys(),
                             current_category=category,
                             search=search,
                             STOCK_CATEGORIES=STOCK_CATEGORIES)
    finally:
        conn.close()

@app.route('/stock/<symbol>')
@login_required
def stock_detail(symbol):
    if not symbol:
        flash('Geçersiz hisse senedi sembolü!', 'error')
        return redirect(url_for('stocks'))

    try:
        # Yahoo Finance API'den veri çekme
        stock = yf.Ticker(symbol)
        
        # Güncel veri
        info = stock.info
        if not info:
            flash('Hisse senedi verisi bulunamadı!', 'error')
            return redirect(url_for('stocks'))
            
        # Son 30 günlük veri
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        history = stock.history(start=start_date, end=end_date)
        
        if history.empty:
            flash('Geçmiş veriler bulunamadı!', 'error')
            return redirect(url_for('stocks'))

        # Günlük değişim hesaplama
        current_price = info.get('currentPrice', 0)
        previous_close = info.get('previousClose', 0)
        price_change = current_price - previous_close
        price_change_percent = (price_change / previous_close * 100) if previous_close else 0

        # Güncel veriyi düzenle
        stock_data = {
            '01. symbol': symbol,
            '02. open': info.get('regularMarketOpen', 'N/A'),
            '03. high': info.get('dayHigh', 'N/A'),
            '04. low': info.get('dayLow', 'N/A'),
            '05. price': current_price,
            '06. volume': info.get('volume', 'N/A'),
            '07. change': f"{price_change:.2f}",
            '08. change percent': f"{price_change_percent:.2f}%"
        }

        # Geçmiş verileri düzenle
        historical_data = []
        dates = []
        prices = []
        volumes = []
        
        for date, row in history.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            historical_data.append({
                'date': date_str,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })
            dates.append(date_str)
            prices.append(float(row['Close']))
            volumes.append(int(row['Volume']))

        # Favori kontrolü
        conn = get_db_connection()
        is_favorite = False
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM favorites WHERE user_id = ? AND symbol = ?", 
                         (session['user_id'], symbol))
            is_favorite = cursor.fetchone() is not None
            conn.close()

        # Kullanıcının tüm favorilerini al
        favorites = get_user_favorites()

        # İşlem geçmişine kaydet
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history (user_id, symbol, price, date)
                    VALUES (?, ?, ?, ?)
                """, (session['user_id'], symbol, current_price, datetime.now()))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Geçmiş kaydı hatası: {e}")

        return render_template('stock_detail.html', 
                             symbol=symbol, 
                             data=stock_data,
                             historical_data=historical_data,
                             dates=dates,
                             prices=prices,
                             volumes=volumes,
                             is_favorite=is_favorite,
                             favorites=favorites)

    except Exception as e:
        flash(f'Veri alınırken bir hata oluştu: {str(e)}', 'error')
        return redirect(url_for('stocks'))

@app.route('/history')
@login_required
def history():
    conn = get_db_connection()
    if not conn:
        flash('Veritabanı bağlantı hatası', 'error')
        return redirect(url_for('stocks'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT symbol, price, date
            FROM history
            WHERE user_id = ?
            ORDER BY date DESC
        """, (session['user_id'],))
        
        history = cursor.fetchall()
        favorites = get_user_favorites()
        return render_template('history.html', history=history, favorites=favorites)
    finally:
        conn.close()

@app.route('/add_favorite/<symbol>')
@login_required
def add_favorite(symbol):
    conn = get_db_connection()
    if not conn:
        flash('Veritabanı bağlantı hatası', 'error')
        return redirect(url_for('stocks'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM favorites WHERE user_id = ? AND symbol = ?", 
                      (session['user_id'], symbol))
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute("INSERT INTO favorites (user_id, symbol) VALUES (?, ?)", 
                         (session['user_id'], symbol))
            conn.commit()
            flash(f'{symbol} favorilere eklendi', 'success')
        else:
            flash(f'{symbol} zaten favorilerinizde', 'info')
    except Exception as e:
        flash(f'Bir hata oluştu: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(request.referrer or url_for('stocks'))

@app.route('/remove_favorite/<symbol>')
@login_required
def remove_favorite(symbol):
    conn = get_db_connection()
    if not conn:
        flash('Veritabanı bağlantı hatası', 'error')
        return redirect(url_for('stocks'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM favorites WHERE user_id = ? AND symbol = ?", 
                      (session['user_id'], symbol))
        conn.commit()
        flash(f'{symbol} favorilerden kaldırıldı', 'success')
    except Exception as e:
        flash(f'Bir hata oluştu: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(request.referrer or url_for('stocks'))

# Uygulama başlatıldığında veritabanını hazırla
init_db()

if __name__ == '__main__':
    app.run(debug=True)
