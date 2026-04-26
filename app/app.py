# app/app.py - نسخة مُصلحة بالكامل
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os
from dotenv import load_dotenv
from functools import wraps
from pathlib import Path
import json
import traceback

# ============================================
# تحميل .env
# ============================================
# البحث في كل الأماكن المحتملة
possible_env = [
    Path(__file__).parent.parent / '.env',  # مجلد المشروع
    Path(__file__).parent / '.env',          # مجلد app
    Path('.env'),                             # المجلد الحالي
]

for env_path in possible_env:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ .env loaded from: {env_path.absolute()}")
        break

app = Flask(__name__)
CORS(app)

# ============================================
# الإعدادات - مع strip() لإزالة أي مسافات
# ============================================
API_KEY   = (os.getenv('API_KEY')   or '').strip()
DB_HOST   = (os.getenv('DB_HOST')   or 'localhost').strip()
DB_PORT   = int((os.getenv('DB_PORT') or '3306').strip())
DB_USER   = (os.getenv('DB_USER')   or '').strip()
DB_PASSWORD = (os.getenv('DB_PASSWORD') or '').strip()
DB_NAME   = (os.getenv('DB_NAME')   or '').strip()

print(f"🔑 API_KEY  = [{API_KEY}]")
print(f"📊 DB_HOST  = [{DB_HOST}]")
print(f"📊 DB_USER  = [{DB_USER}]")
print(f"📊 DB_NAME  = [{DB_NAME}]")


# ============================================
# Error Handler - يمنع خطأ 500
# ============================================
@app.errorhandler(400)
def bad_request(e):
    return jsonify({'success': False, 'error': f'Bad Request: {str(e)}'}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Not Found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': f'Server Error: {str(e)}'}), 500


# ============================================
# قاعدة البيانات
# ============================================
def get_db():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connection_timeout=10
        )
        return conn
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        raise e


# ============================================
# قراءة البيانات - الأكثر مرونة
# ============================================
def get_data():
    """يقرأ البيانات من أي نوع طلب بدون أخطاء"""
    data = {}

    try:
        # الطريقة 1: JSON body
        raw_body = request.get_data(as_text=True)
        print(f"📥 Raw body: [{raw_body}]")
        print(f"📥 Content-Type: [{request.content_type}]")
        print(f"📥 Method: [{request.method}]")

        if raw_body and raw_body.strip():
            try:
                data = json.loads(raw_body.strip())
                print(f"✅ Parsed as JSON: {data}")
                return data
            except json.JSONDecodeError as je:
                print(f"⚠️ JSON parse failed: {je}")

        # الطريقة 2: Form data
        if request.form:
            data = dict(request.form)
            print(f"✅ Got form data: {data}")
            return data

        # الطريقة 3: Query string
        if request.args:
            data = dict(request.args)
            print(f"✅ Got query args: {data}")
            return data

    except Exception as e:
        print(f"⚠️ get_data error: {e}")

    print(f"📥 Returning empty data: {{}}")
    return {}


# ============================================
# تحويل البيانات لـ JSON آمن
# ============================================
def to_json_safe(rows):
    if not rows:
        return []
    result = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, bool):
                clean[k] = v
            elif isinstance(v, int):
                clean[k] = v
            elif isinstance(v, float):
                clean[k] = v
            elif isinstance(v, str):
                clean[k] = v
            else:
                # Decimal, datetime, date, etc.
                try:
                    clean[k] = float(v)
                except Exception:
                    clean[k] = str(v)
        result.append(clean)
    return result


# ============================================
# API Key Protection
# ============================================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '').strip()
        print(f"\n🔐 Auth Header: [{auth}]")

        # استخراج المفتاح
        if auth.lower().startswith('bearer '):
            key = auth[7:].strip()
        else:
            key = auth.strip()

        print(f"🔐 Key received : [{key}]")
        print(f"🔐 Key expected : [{API_KEY}]")
        print(f"🔐 Keys match   : [{key == API_KEY}]")

        if not API_KEY:
            print("⚠️ API_KEY not set in .env - allowing request")
            return f(*args, **kwargs)

        if key == API_KEY:
            return f(*args, **kwargs)

        return jsonify({
            'success': False,
            'error': 'مفتاح API غير صحيح',
            'debug': {
                'received_length': len(key),
                'expected_length': len(API_KEY),
                'received_preview': key[:10] if key else 'empty',
                'expected_preview': API_KEY[:10] if API_KEY else 'empty'
            }
        }), 401

    return decorated


# ============================================
# ROUTES
# ============================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'message': '🤖 Chatbot API يعمل!',
        'db_configured': bool(DB_NAME),
        'api_key_configured': bool(API_KEY),
        'endpoints': {
            'health'  : 'GET /api/health',
            'products': 'GET or POST /api/products/search',
            'faq'     : 'GET or POST /api/faq/search',
            'customer': 'POST /api/customers/lookup',
            'query'   : 'POST /api/query'
        }
    })


# ------------------------------------------
@app.route('/api/health', methods=['GET'])
def health():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        return jsonify({
            'status'          : 'healthy',
            'database'        : 'connected',
            'products_count'  : count,
            'api_key_set'     : bool(API_KEY),
            'api_key_length'  : len(API_KEY),
            'api_key_preview' : API_KEY[:10] + '...' if API_KEY else 'NOT SET'
        })
    except Exception as e:
        return jsonify({
            'status' : 'unhealthy',
            'error'  : str(e)
        }), 500


# ------------------------------------------
@app.route('/api/products/search', methods=['GET', 'POST'])
@require_api_key
def search_products():
    try:
        data     = get_data()
        query    = str(data.get('query', '')   or '').strip()
        category = str(data.get('category', '') or '').strip()

        print(f"🔍 Search: query=[{query}] category=[{category}]")

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        if query and category:
            cursor.execute("""
                SELECT * FROM products
                WHERE (name LIKE %s OR description LIKE %s)
                AND category = %s AND stock > 0
            """, (f'%{query}%', f'%{query}%', category))

        elif query:
            cursor.execute("""
                SELECT * FROM products
                WHERE (name LIKE %s OR description LIKE %s)
                AND stock > 0
            """, (f'%{query}%', f'%{query}%'))

        elif category:
            cursor.execute("""
                SELECT * FROM products
                WHERE category = %s AND stock > 0
            """, (category,))

        else:
            cursor.execute(
                "SELECT * FROM products WHERE stock > 0 LIMIT 10"
            )

        rows     = cursor.fetchall()
        products = to_json_safe(rows)
        cursor.close()
        conn.close()

        return jsonify({
            'success'      : True,
            'count'        : len(products),
            'products'     : products,
            'search_query' : query,
            'message'      : f'تم العثور على {len(products)} منتج'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------
@app.route('/api/faq/search', methods=['GET', 'POST'])
@require_api_key
def search_faq():
    try:
        data  = get_data()
        query = str(data.get('query', '') or '').strip()

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        if query:
            cursor.execute("""
                SELECT * FROM faq
                WHERE question LIKE %s OR answer LIKE %s
            """, (f'%{query}%', f'%{query}%'))
        else:
            cursor.execute("SELECT * FROM faq")

        faqs = to_json_safe(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'count'  : len(faqs),
            'faqs'   : faqs
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------
@app.route('/api/customers/lookup', methods=['GET', 'POST'])
@require_api_key
def lookup_customer():
    try:
        data  = get_data()
        email = str(data.get('email', '') or '').strip()
        phone = str(data.get('phone', '') or '').strip()

        if not email and not phone:
            return jsonify({
                'success': False,
                'message': 'أرسل email أو phone'
            }), 400

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        if email:
            cursor.execute(
                "SELECT * FROM customers WHERE email = %s", (email,)
            )
        else:
            cursor.execute(
                "SELECT * FROM customers WHERE phone = %s", (phone,)
            )

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return jsonify({
                'success' : True,
                'customer': to_json_safe([row])[0]
            })

        return jsonify({
            'success': False,
            'message': 'العميل غير موجود'
        }), 404

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------
@app.route('/api/query', methods=['GET', 'POST'])
@require_api_key
def general_query():
    try:
        data       = get_data()
        query_type = str(data.get('type', '') or '').strip()
        params     = data.get('params', {}) or {}

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        queries = {
            'low_stock': (
                "SELECT * FROM products WHERE stock < %s",
                [int(params.get('threshold', 10))]
            ),
            'price_range': (
                """SELECT * FROM products
                   WHERE price BETWEEN %s AND %s
                   AND stock > 0""",
                [
                    float(params.get('min_price', 0)),
                    float(params.get('max_price', 99999))
                ]
            ),
            'categories': (
                """SELECT category,
                          COUNT(*) as count,
                          AVG(price) as avg_price
                   FROM products GROUP BY category""",
                []
            ),
            'total_products': (
                "SELECT COUNT(*) as total FROM products",
                []
            ),
        }

        if query_type not in queries:
            return jsonify({
                'success'  : False,
                'message'  : f'نوع غير معروف: [{query_type}]',
                'available': list(queries.keys())
            }), 400

        sql, sql_params = queries[query_type]

        if sql_params:
            cursor.execute(sql, sql_params)
        else:
            cursor.execute(sql)

        results = to_json_safe(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({
            'success'   : True,
            'query_type': query_type,
            'count'     : len(results),
            'results'   : results
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('🤖 Chatbot API Server')
    print('=' * 50)
    print(f'📍 http://localhost:5000')
    print(f'📊 DB   : {DB_NAME} @ {DB_HOST}')
    print(f'🔑 Key  : {API_KEY[:15]}... ({len(API_KEY)} chars)')
    print('=' * 50 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=True)