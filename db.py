import os
from decimal import Decimal
import psycopg2
from psycopg2 import sql
import hashlib
from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

BOT_ADMIN_USER = os.getenv("BOT_ADMIN_USER")
BOT_ADMIN_PASSWORD = os.getenv("BOT_ADMIN_PASSWORD")
BOT_USER_USER = os.getenv("BOT_USER_USER")
BOT_USER_PASSWORD = os.getenv("BOT_USER_PASSWORD")
BOT_BANNED_USER = os.getenv("BOT_BANNED_USER")
BOT_BANNED_PASSWORD = os.getenv("BOT_BANNED_PASSWORD")


def get_db_connection():
    dsn = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    conn = psycopg2.connect(dsn)
    return conn


def get_db_connection_by_role(role):
    if role == 'admin':
        user = BOT_ADMIN_USER
        password = BOT_ADMIN_PASSWORD
    elif role == 'banned':
        user = BOT_BANNED_USER
        password = BOT_BANNED_PASSWORD
    else:
        user = BOT_USER_USER
        password = BOT_USER_PASSWORD

    dsn = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={user} password={password}"
    conn = psycopg2.connect(dsn)
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            role VARCHAR(12) DEFAULT 'user' CHECK (role IN ('user', 'admin', 'banned')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_balance (
            user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            balance DECIMAL(10,2) DEFAULT 0.00 CHECK (balance >= 0),
            total_tokens BIGINT DEFAULT 0 CHECK (total_tokens >= 0),
            current_discount DECIMAL(5,2) DEFAULT 0.00 CHECK (current_discount >= 0 AND current_discount <= 30)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_history (
            payment_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
            status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'pending')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            title VARCHAR(255),
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            usage_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            chat_id INTEGER REFERENCES chats(chat_id) ON DELETE SET NULL,
            prompt_tokens INTEGER NOT NULL CHECK (prompt_tokens >= 0),
            response_tokens INTEGER NOT NULL CHECK (response_tokens >= 0),
            base_cost DECIMAL(10,4) NOT NULL CHECK (base_cost >= 0),
            discount_applied DECIMAL(5,2) DEFAULT 0 CHECK (discount_applied >= 0 AND discount_applied <= 30),
            final_cost DECIMAL(10,4) NOT NULL CHECK (final_cost >= 0),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id SERIAL PRIMARY KEY,
            chat_id INTEGER NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            sender VARCHAR(10) NOT NULL CHECK (sender IN ('user', 'bot')),
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            author VARCHAR(10) NOT NULL CHECK (author IN ('user', 'admin')),
            content TEXT NOT NULL,
            is_read_admin BOOLEAN DEFAULT FALSE,
            is_read_user BOOLEAN DEFAULT FALSE,
            priority INTEGER DEFAULT 1 CHECK (priority >= 0 AND priority <= 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION validate_email(email TEXT) RETURNS BOOLEAN AS $$
        BEGIN
            IF email IS NULL OR email = '' THEN
                RETURN TRUE; 
            END IF;
            RETURN email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$';
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION calculate_discount(total_tokens BIGINT) RETURNS DECIMAL(5,2) AS $$
        BEGIN
            RETURN CASE
                WHEN total_tokens < 1000 THEN 0.00
                WHEN total_tokens < 10000 THEN 5.00
                WHEN total_tokens < 50000 THEN 12.00
                WHEN total_tokens < 100000 THEN 20.00
                ELSE 30.00
            END;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION calculate_token_cost(
            prompt_tokens INTEGER,
            response_tokens INTEGER,
            discount DECIMAL
        ) RETURNS DECIMAL(10,4) AS $$
        DECLARE
            base_cost DECIMAL(10,4);
        BEGIN
            base_cost := (prompt_tokens::DECIMAL / 1000.0 * 0.02) + (response_tokens::DECIMAL / 1000.0 * 0.09);
            RETURN base_cost * (1 - COALESCE(discount, 0) / 100.0);
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION auto_create_balance() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        BEGIN

            INSERT INTO user_balance(user_id, balance, total_tokens, current_discount)
            VALUES (NEW.user_id, 300.00, 0, 0.00);


            INSERT INTO payment_history(user_id, amount, status)
            VALUES (NEW.user_id, 300.00, 'success');

            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION validate_user_email() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT validate_email(NEW.email) THEN
                RAISE EXCEPTION 'Некорректный email адрес: %', NEW.email;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION auto_recalculate_discount() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE
            new_discount DECIMAL(5,2);
        BEGIN
            new_discount := calculate_discount(NEW.total_tokens);
            IF NEW.current_discount IS DISTINCT FROM new_discount THEN
                NEW.current_discount := new_discount;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION check_balance_before_usage() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE
            bal DECIMAL(10,2);
            disc DECIMAL(5,2);
            calculated_cost DECIMAL(10,4);
        BEGIN

            SELECT balance, current_discount INTO bal, disc
            FROM user_balance WHERE user_id = NEW.user_id;

            IF bal IS NULL THEN
                RAISE EXCEPTION 'Баланс не найден для пользователя %', NEW.user_id;
            END IF;


            calculated_cost := calculate_token_cost(NEW.prompt_tokens, NEW.response_tokens, disc);


            IF bal < calculated_cost THEN
                RAISE EXCEPTION 'Недостаточно средств: баланс=%, стоимость=%', bal, calculated_cost;
            END IF;


            NEW.base_cost := (NEW.prompt_tokens::DECIMAL / 1000.0 * 0.02) + (NEW.response_tokens::DECIMAL / 1000.0 * 0.09);
            NEW.discount_applied := disc;
            NEW.final_cost := calculated_cost;

            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION auto_deduct_on_usage() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE
            new_total_tokens BIGINT;
            new_discount DECIMAL(5,2);
            new_balance DECIMAL(10,2);
        BEGIN

            UPDATE user_balance
            SET balance = balance - NEW.final_cost,
                total_tokens = total_tokens + NEW.prompt_tokens + NEW.response_tokens
            WHERE user_id = NEW.user_id
            RETURNING total_tokens, current_discount, balance INTO new_total_tokens, new_discount, new_balance;




            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION award_milestone_bonus() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE
            bonus DECIMAL(10,2) := 0;
        BEGIN

            IF NEW.total_tokens >= 10000 AND (OLD.total_tokens IS NULL OR OLD.total_tokens < 10000) THEN
                bonus := 50.00;

            ELSIF NEW.total_tokens >= 50000 AND (OLD.total_tokens IS NULL OR OLD.total_tokens < 50000) THEN
                bonus := 150.00;
            END IF;

            IF bonus > 0 THEN

                UPDATE user_balance SET balance = balance + bonus WHERE user_id = NEW.user_id;


                INSERT INTO payment_history(user_id, amount, status)
                VALUES (NEW.user_id, bonus, 'success');


                INSERT INTO support_tickets(user_id, author, content, is_read_user)
                VALUES (NEW.user_id, 'admin', ' Бонус ' || bonus || ' руб за активность!', FALSE);
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION notify_low_balance() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        BEGIN
            IF NEW.balance < 10 AND (OLD.balance IS NULL OR OLD.balance >= 10) THEN
                INSERT INTO support_tickets(user_id, author, content, is_read_user)
                VALUES (NEW.user_id, 'admin', ' Низкий баланс. Пополните счёт для продолжения работы.', FALSE);
            END IF;
            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION auto_support_handling() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE
            user_tokens BIGINT := 0;
            priority_level INTEGER := 1;
        BEGIN

            SELECT COALESCE(total_tokens, 0) INTO user_tokens
            FROM user_balance WHERE user_id = NEW.user_id;

            IF user_tokens > 50000 THEN
                priority_level := 3;
            ELSIF user_tokens > 10000 THEN
                priority_level := 2;
            ELSE
                priority_level := 1;
            END IF;


            UPDATE support_tickets
            SET priority = priority_level
            WHERE ticket_id = NEW.ticket_id;


            IF NEW.author = 'user' THEN
                IF NEW.content ILIKE '%цена%' OR NEW.content ILIKE '%стоимост%' OR NEW.content ILIKE '%стоит%' THEN
                    INSERT INTO support_tickets(user_id, author, content, is_read_user)
                    VALUES (NEW.user_id, 'admin', ' Базовая цена: 0.12 руб за 1000 токенов. Скидка зависит от активности: 0-5-12-20-30%', FALSE);
                ELSIF NEW.content ILIKE '%баланс%' OR NEW.content ILIKE '%пополни%' OR NEW.content ILIKE '%оплат%' THEN
                    INSERT INTO support_tickets(user_id, author, content, is_read_user)
                    VALUES (NEW.user_id, 'admin', ' Пополнить баланс можно на вкладке Оплата. При низком балансе (<10 руб) придёт уведомление.', FALSE);
                ELSIF NEW.content ILIKE '%скидк%' OR NEW.content ILIKE '%бонус%' THEN
                    INSERT INTO support_tickets(user_id, author, content, is_read_user)
                    VALUES (NEW.user_id, 'admin', ' Скидка начисляется автоматически: 1к-10к токенов = 5%, 10к-50к = 12%, 50к-100к = 20%, 100к+ = 30%', FALSE);
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE FUNCTION update_chat_activity() RETURNS TRIGGER
        LANGUAGE plpgsql SECURITY DEFINER AS $$
        BEGIN

            UPDATE chats SET last_activity = CURRENT_TIMESTAMP WHERE chat_id = NEW.chat_id;


            IF NEW.sender = 'user' THEN
                UPDATE chats
                SET title = LEFT(NEW.content, 50)
                WHERE chat_id = NEW.chat_id
                  AND (title IS NULL OR title = '');
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_auto_create_balance
        AFTER INSERT ON users
        FOR EACH ROW EXECUTE FUNCTION auto_create_balance();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_validate_user_email
        BEFORE INSERT OR UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION validate_user_email();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_auto_recalculate_discount
        BEFORE UPDATE OF total_tokens ON user_balance
        FOR EACH ROW EXECUTE FUNCTION auto_recalculate_discount();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_check_balance_before_usage
        BEFORE INSERT ON token_usage
        FOR EACH ROW EXECUTE FUNCTION check_balance_before_usage();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_auto_deduct_on_usage
        AFTER INSERT ON token_usage
        FOR EACH ROW EXECUTE FUNCTION auto_deduct_on_usage();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_award_milestone_bonus
        AFTER UPDATE OF total_tokens ON user_balance
        FOR EACH ROW EXECUTE FUNCTION award_milestone_bonus();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_notify_low_balance
        AFTER UPDATE OF balance ON user_balance
        FOR EACH ROW EXECUTE FUNCTION notify_low_balance();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_update_chat_activity
        AFTER INSERT ON messages
        FOR EACH ROW EXECUTE FUNCTION update_chat_activity();
    """)

    cur.execute("""
        CREATE OR REPLACE TRIGGER trg_auto_support_handling
        AFTER INSERT ON support_tickets
        FOR EACH ROW EXECUTE FUNCTION auto_support_handling();
    """)

    for role_name, role_password in [
        (BOT_ADMIN_USER, BOT_ADMIN_PASSWORD),
        (BOT_USER_USER, BOT_USER_PASSWORD),
        (BOT_BANNED_USER, BOT_BANNED_PASSWORD)
    ]:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))  #Так не надо было (((( но лучше единый стиль
        if not cur.fetchone():
            cur.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(role_name)),
                (role_password,)
            )

    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}, {}").format(
        sql.Identifier(DB_NAME),
        sql.Identifier(BOT_ADMIN_USER),
        sql.Identifier(BOT_USER_USER),
        sql.Identifier(BOT_BANNED_USER)
    ))

    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}, {}").format(
        sql.Identifier(BOT_ADMIN_USER),
        sql.Identifier(BOT_USER_USER),
        sql.Identifier(BOT_BANNED_USER)
    ))

    cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
        sql.Identifier(BOT_ADMIN_USER)
    ))

    cur.execute(sql.SQL(
        "GRANT SELECT, INSERT, UPDATE ON users, user_balance, token_usage, "
        "chats, messages, payment_history, support_tickets TO {}"
    ).format(sql.Identifier(BOT_USER_USER)))

    cur.execute(
        sql.SQL("GRANT SELECT ON users, user_balance, chats, messages TO {}").format(sql.Identifier(BOT_BANNED_USER)))

    cur.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {}, {}").format(
        sql.Identifier(BOT_ADMIN_USER),
        sql.Identifier(BOT_USER_USER)
    ))

    cur.execute("SELECT user_id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        admin_password_hash = hash_password('admin123')
        cur.execute("""
            INSERT INTO users (username, password_hash, email, role)
            VALUES ('admin', %s, 'admin@example.com', 'admin')
            RETURNING user_id;
        """, (admin_password_hash,))
        admin_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()


def register_user(username, password, email=None, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    password_hash = hash_password(password)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, email, role) VALUES (%s, %s, %s, %s) RETURNING user_id;",
        (username, password_hash, email, 'user')
    )
    result = cur.fetchone()
    if result:
        user_id = result[0]
        conn.commit()
        cur.close()
        if should_close:
            conn.close()
        return True, "Регистрация успешна! Вам начислен бонус 300 руб."
    else:
        conn.commit()
        cur.close()
        if should_close:
            conn.close()
        return False, "Ошибка при регистрации"


def authenticate_user(username, password, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    password_hash = hash_password(password)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, role FROM users WHERE username = %s AND password_hash = %s;",
        (username, password_hash)
    )
    result = cur.fetchone()
    cur.close()

    if should_close:
        conn.close()

    if result:
        return True, result
    else:
        return False, "Неверный логин или пароль"


def get_user_role(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE user_id = %s;", (user_id,))
    result = cur.fetchone()
    cur.close()

    if should_close:
        conn.close()

    return result[0] if result else 'user'


def set_user_role(target_username, new_role, admin_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    if get_user_role(admin_id, conn) != 'admin':
        if should_close:
            conn.close()
        return False, "У вас нет прав на изменение ролей."

    cur = conn.cursor()

    cur.execute("SELECT user_id, role FROM users WHERE username = %s;", (target_username,))
    target_info = cur.fetchone()
    if not target_info:
        cur.close()
        if should_close:
            conn.close()
        return False, f"Пользователь {target_username} не найден."

    target_user_id, target_role = target_info

    if target_role == 'admin' and target_user_id != admin_id:
        cur.close()
        if should_close:
            conn.close()
        return False, "Вы не можете изменить роль другого администратора."

    cur.execute("UPDATE users SET role = %s WHERE username = %s RETURNING user_id;", (new_role, target_username))
    result = cur.fetchone()
    conn.commit()
    cur.close()

    if should_close:
        conn.close()

    if result:
        return True, f"Роль для {target_username} изменена на {new_role}."
    else:
        return False, f"Пользователь {target_username} не найден."


def log_token_usage(user_id, prompt_tokens, response_tokens, chat_id=None, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()

    cur.execute("SELECT balance, current_discount FROM user_balance WHERE user_id = %s;", (user_id,))
    balance_info = cur.fetchone()
    if not balance_info:
        cur.close()
        if should_close:
            conn.close()
        raise ValueError("Баланс не найден для пользователя")

    current_balance, current_discount = balance_info

    base_cost = (Decimal(prompt_tokens) / Decimal(1000) * Decimal('0.02')) + (
            Decimal(response_tokens) / Decimal(1000) * Decimal('0.09'))
    cd = Decimal(current_discount)
    final_cost = base_cost * (Decimal(1) - cd / Decimal(100))

    if chat_id:
        cur.execute(
            "INSERT INTO token_usage (user_id, chat_id, prompt_tokens, response_tokens, base_cost, discount_applied, final_cost) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s);",
            (user_id, chat_id, int(prompt_tokens), int(response_tokens), base_cost, cd, final_cost)
        )
    else:
        cur.execute(
            "INSERT INTO token_usage (user_id, prompt_tokens, response_tokens, base_cost, discount_applied, final_cost) "
            "VALUES (%s, %s, %s, %s, %s, %s);",
            (user_id, int(prompt_tokens), int(response_tokens), base_cost, cd, final_cost)
        )
    conn.commit()
    cur.close()

    if should_close:
        conn.close()


def get_balance_and_info(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute(
        "SELECT balance, current_discount, total_tokens FROM user_balance WHERE user_id = %s;",
        (user_id,)
    )
    result = cur.fetchone()
    cur.close()

    if should_close:
        conn.close()

    if result:
        return result
    else:
        return (0.00, 0.00, 0)


def create_new_chat(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute("INSERT INTO chats (user_id) VALUES (%s) RETURNING chat_id;", (user_id,))
    chat_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    if should_close:
        conn.close()

    return chat_id


def get_user_chats(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            c.chat_id,
            COALESCE(c.title, 'Новый чат') as title,
            c.last_activity,
            COALESCE((
                SELECT m.content 
                FROM messages m 
                WHERE m.chat_id = c.chat_id 
                ORDER BY m.timestamp DESC 
                LIMIT 1
            ), '') as last_message
        FROM chats c
        WHERE c.user_id = %s
        ORDER BY c.last_activity DESC;
    """, (user_id,))
    result = cur.fetchall()
    cur.close()

    if should_close:
        conn.close()

    return result


def add_message(chat_id, user_id, sender, content, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute("INSERT INTO messages (chat_id, user_id, sender, content) VALUES (%s, %s, %s, %s);",
                (chat_id, user_id, sender, content))
    conn.commit()
    cur.close()

    if should_close:
        conn.close()


def get_message_history(chat_id, conn=None):
    if conn is None:
        conn = get_db_connection()
    #     should_close = True
    # else:
    #     should_close = False

    cur = conn.cursor()
    cur.execute("SELECT sender, content FROM messages WHERE chat_id = %s ORDER BY timestamp;", (chat_id,))
    result = cur.fetchall()
    cur.close()

    # if should_close:
    conn.close()

    return result


def simulate_payment(user_id, amount, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()

    cur.execute(
        "INSERT INTO payment_history (user_id, amount, status) VALUES (%s, %s, %s);",
        (user_id, amount, 'success')
    )

    cur.execute(
        "UPDATE user_balance SET balance = balance + %s WHERE user_id = %s;",
        (amount, user_id)
    )
    conn.commit()
    cur.close()

    if should_close:
        conn.close()


def support_send_user_message(user_id, content, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO support_tickets (user_id, author, content, is_read_admin, is_read_user) VALUES (%s, 'user', %s, FALSE, TRUE);",
        (user_id, content)
    )
    conn.commit()
    cur.close()
    if should_close:
        conn.close()


def support_send_admin_reply(admin_id, target_user_id, content, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    if get_user_role(admin_id, conn) != 'admin':
        if should_close:
            conn.close()
        return False, "Недостаточно прав"

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO support_tickets (user_id, author, content, is_read_admin, is_read_user) VALUES (%s, 'admin', %s, TRUE, FALSE);",
        (target_user_id, content)
    )
    conn.commit()
    cur.close()
    if should_close:
        conn.close()
    return True, "Отправлено"


def support_get_thread(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute(
        "SELECT author, content, created_at FROM support_tickets WHERE user_id = %s ORDER BY created_at ASC;",
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close()

    if should_close:
        conn.close()

    return rows


def support_mark_admin_read(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False
    cur = conn.cursor()
    cur.execute(
        "UPDATE support_tickets SET is_read_admin = TRUE WHERE user_id = %s AND author = 'user' AND is_read_admin = FALSE;",
        (user_id,))
    conn.commit()
    cur.close()
    if should_close:
        conn.close()


def support_mark_user_read(user_id, conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False
    cur = conn.cursor()
    cur.execute(
        "UPDATE support_tickets SET is_read_user = TRUE WHERE user_id = %s AND author = 'admin' AND is_read_user = FALSE;",
        (user_id,))
    conn.commit()
    cur.close()
    if should_close:
        conn.close()


def support_get_inbox(conn=None):
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.user_id,
               u.username,
               COALESCE((SELECT st2.content FROM support_tickets st2 WHERE st2.user_id = u.user_id ORDER BY st2.created_at DESC LIMIT 1), '') AS last_message,
               COALESCE((SELECT COUNT(*) FROM support_tickets st3 WHERE st3.user_id = u.user_id AND st3.author = 'user' AND st3.is_read_admin = FALSE), 0) AS unread_for_admin
        FROM users u
        WHERE EXISTS (SELECT 1 FROM support_tickets st WHERE st.user_id = u.user_id)
        ORDER BY unread_for_admin DESC, u.user_id ASC;
        """
    )
    rows = cur.fetchall()
    cur.close()
    if should_close:
        conn.close()
    return rows


def fix_banned_user_permissions():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(sql.SQL("GRANT SELECT ON user_balance TO {}").format(sql.Identifier(BOT_BANNED_USER)))
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    fix_banned_user_permissions()
