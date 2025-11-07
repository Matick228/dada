# rab.py

import sys
import uuid
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel,
                             QListWidget, QComboBox, QSpinBox, QDialog,
                             QDialogButtonBox, QStackedWidget, QFrame, QScrollArea,
                             QListWidgetItem)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QMargins, QEvent
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
from db import init_db, register_user, authenticate_user, get_user_role, set_user_role, log_token_usage, \
    get_balance_and_info, add_message, get_message_history, create_new_chat, get_user_chats, \
    support_send_user_message, support_send_admin_reply, support_get_thread, support_mark_user_read, \
    support_mark_admin_read, support_get_inbox, simulate_payment, get_db_connection_by_role
import os
from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_BASE = "https://gigachat.devices.sberbank.ru"
CHAT_PATH = "/api/v1/chat/completions"


class ModernAuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Авторизация")
        self.setFixedSize(440, 720)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #111827;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 15px;
            }
            QLineEdit:focus {
                border: 1px solid #60a5fa;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QLabel {
                color: #111827;
                font-size: 15px;
            }
            QStackedWidget {
                background-color: #ffffff;
            }
        """)

        self.stacked_widget = QStackedWidget()
        self.setup_login_form()
        self.setup_register_form()

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)
        self.setWindowIcon(QIcon("LogoDa.png"))

        self.user_id = None
        self.username = None
        self.role = None

    def setup_login_form(self):
        login_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        title = QLabel("Вход в систему")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Введите логин")

        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Введите пароль")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = QPushButton("Войти")
        login_btn.clicked.connect(self.handle_login)

        register_switch_btn = QPushButton("Нет аккаунта? Зарегистрироваться")
        register_switch_btn.setStyleSheet("background-color: transparent; color: #0088cc;")

        register_switch_btn.clicked.connect(self.show_register_form)

        layout.addWidget(title)
        layout.addWidget(QLabel("Логин:"))
        layout.addWidget(self.login_input)
        layout.addWidget(QLabel("Пароль:"))
        layout.addWidget(self.login_password)
        layout.addWidget(login_btn)
        layout.addWidget(register_switch_btn)
        layout.addStretch()

        login_widget.setLayout(layout)
        self.stacked_widget.addWidget(login_widget)

    def setup_register_form(self):
        register_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        title = QLabel("Регистрация")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")

        self.register_login = QLineEdit()
        self.register_login.setPlaceholderText("Придумайте логин")

        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("Отображаемое имя (необязательно)")

        self.register_password = QLineEdit()
        self.register_password.setPlaceholderText("Придумайте пароль")
        self.register_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.register_confirm_password = QLineEdit()
        self.register_confirm_password.setPlaceholderText("Подтвердите пароль")
        self.register_confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.register_email = QLineEdit()
        self.register_email.setPlaceholderText("Email (необязательно)")

        register_btn = QPushButton("Зарегистрироваться")
        register_btn.clicked.connect(self.handle_register)

        login_switch_btn = QPushButton("Уже есть аккаунт? Войти")
        login_switch_btn.setStyleSheet("background-color: transparent; color: #0088cc;")
        login_switch_btn.clicked.connect(self.show_login_form)

        layout.addWidget(title)
        layout.addWidget(QLabel("Логин*:"))
        layout.addWidget(self.register_login)
        layout.addWidget(QLabel("Отображаемое имя:"))
        layout.addWidget(self.register_username)
        layout.addWidget(QLabel("Пароль*:"))
        layout.addWidget(self.register_password)
        layout.addWidget(QLabel("Подтверждение пароля*:"))
        layout.addWidget(self.register_confirm_password)
        layout.addWidget(QLabel("Email:"))
        layout.addWidget(self.register_email)
        layout.addWidget(register_btn)
        layout.addWidget(login_switch_btn)
        layout.addStretch()

        register_widget.setLayout(layout)
        self.stacked_widget.addWidget(register_widget)

    def show_register_form(self):
        self.stacked_widget.setCurrentIndex(1)

    def show_login_form(self):
        self.stacked_widget.setCurrentIndex(0)

    def handle_login(self):
        login = self.login_input.text().strip()
        password = self.login_password.text().strip()

        if not login or not password:
            return

        success, result = authenticate_user(login, password)

        if success:
            self.user_id, self.username, self.role = result
            self.accept()

    def handle_register(self):
        login = self.register_login.text().strip()
        username = self.register_username.text().strip() or None
        password = self.register_password.text().strip()
        confirm_password = self.register_confirm_password.text().strip()
        email = self.register_email.text().strip() or None

        if not login or not password:
            return

        if password != confirm_password:
            return

        if len(password) < 4:
            return

        success, message = register_user(login, password, email)

        if success:
            self.show_login_form()
            self.login_input.setText(login)
            self.login_password.clear()

    def get_user_data(self):
        return self.user_id, self.username, self.role


class GigaChatThread(QThread):
    response_received = pyqtSignal(str, int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, messages_list, access_token):
        super().__init__()
        self.messages_list = messages_list
        self.access_token = access_token

    def run(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
        }
        body = {
            "model": "GigaChat",
            "messages": self.messages_list,
            "temperature": 0.7,
            "max_tokens": 512
        }
        resp = requests.post(API_BASE + CHAT_PATH, headers=headers, json=body, timeout=30, verify=False)
        resp.raise_for_status()
        j = resp.json()
        answer = j.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = j.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        response_tokens = usage.get("completion_tokens", 0)
        self.response_received.emit(answer, prompt_tokens, response_tokens)


class ModernMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user_id = None
        self.username = None
        self.role = None
        self.current_chat_id = None

        # Обновленный глобальный стиль: однородно светлый с добавлением цветов
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f9fafb;  /* Мягкий светло-серый фон */
                color: #1f2937;  /* Темно-серый текст */
            }
            QTabWidget::pane {
                border: none;
                background-color: #f3f4f6;
            }
            QTabBar::tab {
                background-color: #e5e7eb;
                color: #4b5563;
                padding: 12px 20px;
                margin: 2px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #bfdbfe;  /* Светло-синий для выбранной вкладки */
                color: #1e40af;  /* Темно-синий текст */
            }
            QTabBar::tab:hover {
                background-color: #d1d5db;
            }
            QTextEdit, QLineEdit {
                background-color: #ffffff;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 15px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border: 1px solid #3b82f6;  /* Синий фокус */
            }
            QPushButton {
                background-color: #3b82f6;  /* Синий для кнопок */
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #94a3b8;
            }
            QListWidget {
                background-color: #ffffff;
                color: #1f2937;
                border: none;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #e5e7eb;
            }
            QListWidget::item:selected {
                background-color: #bfdbfe;  /* Светло-синий */
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QSpinBox, QComboBox {
                background-color: #ffffff;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 15px;
            }
            QLabel {
                color: #1f2937;
                font-size: 15px;
            }
            QScrollBar:vertical {
                background-color: #f1f5f9;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QFrame.card {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);  /* Легкая тень для объема */
            }
        """)

        self.setWindowTitle("RAB Bot")

        # Auth dialog
        auth_dialog = ModernAuthDialog(self)
        if auth_dialog.exec() == QDialog.DialogCode.Accepted:
            self.user_id, self.username, self.role = auth_dialog.get_user_data()
            self.setWindowTitle(f"RAB Bot - {self.username} ({self.role})")
        else:
            sys.exit(0)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_chat_tab()
        self.tabs.addTab(self.chat_widget, "Чат")

        self.setup_balance_tab()
        self.tabs.addTab(self.balance_widget, "Баланс")

        self.setup_support_tab()
        self.tabs.addTab(self.support_widget, "Поддержка")

        if self.role == 'admin':
            self.setup_admin_tab()
            self.tabs.addTab(self.admin_widget, "Админ")

        self.load_chats_list()
        self.update_balance_info()
        # Загружаем поддержку только если пользователь не забанен
        if self.role != 'banned':
            self.load_support_thread_for_user()
        if self.role == 'admin':
            self.load_users_list()
            self.load_support_inbox()

        self.chat_display.installEventFilter(self)

    def setup_chat_tab(self):
        self.chat_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar for chats list
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("background-color: #f8fafc; border-right: 1px solid #e2e8f0;")

        chats_label = QLabel("Чаты")
        chats_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        sidebar_layout.addWidget(chats_label)

        self.chats_list = QListWidget()
        self.chats_list.setStyleSheet("border: none;")
        self.chats_list.itemClicked.connect(self.on_chat_selected)
        sidebar_layout.addWidget(self.chats_list)

        new_chat_btn = QPushButton("Новый чат")
        new_chat_btn.clicked.connect(self.start_new_chat)
        new_chat_btn.setStyleSheet("background-color: #3b82f6; color: white;")
        sidebar_layout.addWidget(new_chat_btn)

        sidebar.setLayout(sidebar_layout)

        # Main chat area
        chat_area = QWidget()
        chat_layout = QVBoxLayout()
        chat_layout.setContentsMargins(20, 20, 20, 20)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;")


        chat_layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setFixedHeight(60)
        input_layout.addWidget(self.message_input)

        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedWidth(60)
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)

        chat_layout.addLayout(input_layout)
        chat_area.setLayout(chat_layout)

        # Main horizontal layout
        main_layout = QHBoxLayout()
        main_layout.addWidget(sidebar)
        main_layout.addWidget(chat_area)
        self.chat_widget.setLayout(main_layout)

    def setup_balance_tab(self):
        balance_widget = QWidget()
        layout = QHBoxLayout()  # Изменяем на горизонтальный layout
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # ===== ЛЕВАЯ ЧАСТЬ - Баланс и правила скидки =====
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(16)

        # Блок баланса и статистики
        balance_card = QFrame()
        balance_card.setObjectName("card")
        card_layout = QVBoxLayout()
        card_layout.setSpacing(12)

        title_label = QLabel("Баланс и статистика")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e40af;")
        card_layout.addWidget(title_label)

        self.balance_label = QLabel()
        self.balance_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #16a34a;")

        self.discount_label = QLabel()
        self.discount_label.setStyleSheet("font-size: 16px; color: #3b82f6;")

        self.tokens_label = QLabel()
        self.tokens_label.setStyleSheet("font-size: 16px; color: #4b5563;")

        card_layout.addWidget(self.balance_label)
        card_layout.addWidget(self.discount_label)
        card_layout.addWidget(self.tokens_label)

        balance_card.setLayout(card_layout)
        left_layout.addWidget(balance_card)

        # Блок правил получения скидки
        rules_card = QFrame()
        rules_card.setObjectName("card")
        rules_layout = QVBoxLayout()
        rules_layout.setSpacing(12)

        rules_title = QLabel("Правила получения скидки")
        rules_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        rules_layout.addWidget(rules_title)

        rules_text = QLabel(
            " <b>Система скидок за активность:</b><br><br>"
            " <b>0-1,000 токенов:</b> Без скидки (0%)<br>"
            " <b>1,000-10,000 токенов:</b> Скидка 5%<br>"
            " <b>10,000-50,000 токенов:</b> Скидка 12%<br>"
            " <b>50,000-100,000 токенов:</b> Скидка 20%<br>"
            " <b>100,000+ токенов:</b> Максимальная скидка 30%<br><br>"
            " <b>Бонусы за активность:</b><br>"
            " При достижении 10,000 токенов: +50 руб<br>"
            " При достижении 50,000 токенов: +150 руб<br><br>"
            " <b>Текущие цены:</b><br>"
            " Входные токены: 0.02 руб/1K<br>"
            " Выходные токены: 0.09 руб/1K</b><br>"
            " <b>Средняя стоимость одного запроса составляет около 0.08-0.10 руб"
        )
        rules_text.setStyleSheet("font-size: 14px; color: #4b5563; line-height: 1.4;")
        rules_text.setWordWrap(True)
        rules_layout.addWidget(rules_text)

        rules_card.setLayout(rules_layout)
        left_layout.addWidget(rules_card)

        left_layout.addStretch()
        left_widget.setLayout(left_layout)

        # ===== ПРАВАЯ ЧАСТЬ - Пополнение баланса =====
        right_widget = QWidget()
        right_widget.setFixedWidth(300)  # Фиксированная ширина для правой колонки
        right_layout = QVBoxLayout()
        right_layout.setSpacing(16)

        # Блок пополнения баланса
        payment_card = QFrame()
        payment_card.setObjectName("card")
        payment_layout = QVBoxLayout()
        payment_layout.setSpacing(16)

        payment_title = QLabel("Пополнение баланса")
        payment_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e40af; text-align: center;")
        payment_layout.addWidget(payment_title)

        # Поле ввода суммы
        amount_widget = QWidget()
        amount_layout = QVBoxLayout()
        amount_layout.setSpacing(8)

        amount_label = QLabel("Сумма оплаты (руб):")
        amount_label.setStyleSheet("color: #4b5563; font-size: 14px; font-weight: 500;")
        amount_layout.addWidget(amount_label)

        self.amount_input = QSpinBox()
        self.amount_input.setMinimum(10)
        self.amount_input.setMaximum(100000)
        self.amount_input.setValue(100)
        self.amount_input.setStyleSheet("""
            QSpinBox {
                font-size: 16px; 
                border: 1px solid #d1d5db; 
                border-radius: 8px; 
                padding: 12px;
                background-color: white;
            }
            QSpinBox:focus {
                border: 1px solid #3b82f6;
            }
        """)
        amount_layout.addWidget(self.amount_input)

        amount_widget.setLayout(amount_layout)
        payment_layout.addWidget(amount_widget)

        # Кнопка оплаты
        self.payment_btn = QPushButton("Пополнить баланс")
        self.payment_btn.setIcon(QIcon.fromTheme("wallet"))
        self.payment_btn.clicked.connect(self.process_payment)
        self.payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e; 
                color: white; 
                font-size: 16px; 
                font-weight: 600;
                border: none;
                border-radius: 10px;
                padding: 16px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:pressed {
                background-color: #15803d;
            }
        """)
        self.payment_btn.setFixedHeight(60)
        payment_layout.addWidget(self.payment_btn)

        # Информация о минимальной сумме
        info_label = QLabel("Минимальная сумма пополнения: 10 руб")
        info_label.setStyleSheet("color: #6b7280; font-size: 12px; text-align: center; margin-top: 10px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        payment_layout.addWidget(info_label)

        payment_card.setLayout(payment_layout)
        right_layout.addWidget(payment_card)

        right_layout.addStretch()
        right_widget.setLayout(right_layout)

        # Добавляем левую и правую части в основной layout
        layout.addWidget(left_widget)
        layout.addWidget(right_widget)

        # Устанавливаем соотношение ширины (левая часть растягивается, правая фиксирована)
        layout.setStretchFactor(left_widget, 1)
        layout.setStretchFactor(right_widget, 0)

        balance_widget.setLayout(layout)
        self.balance_widget = balance_widget

    def setup_support_tab(self):
        self.support_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        thread_label = QLabel("Переписка с поддержкой")
        thread_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(thread_label)

        self.support_thread_view = QTextEdit()
        self.support_thread_view.setReadOnly(True)
        layout.addWidget(self.support_thread_view)

        input_layout = QHBoxLayout()
        self.support_message = QTextEdit()
        self.support_message.setFixedHeight(60)
        input_layout.addWidget(self.support_message)

        send_support_btn = QPushButton("Отправить")
        send_support_btn.clicked.connect(self.send_support_message)
        input_layout.addWidget(send_support_btn)

        layout.addLayout(input_layout)
        self.support_widget.setLayout(layout)

    def setup_admin_tab(self):
        self.admin_widget = QWidget()
        admin_tabs = QTabWidget()

        # Users tab
        users_widget = QWidget()
        users_layout = QVBoxLayout()
        self.users_list = QTextEdit()
        self.users_list.setReadOnly(True)
        users_layout.addWidget(self.users_list)

        # Role change
        role_layout = QHBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username пользователя")
        role_layout.addWidget(self.username_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(['user', 'admin', 'banned'])
        role_layout.addWidget(self.role_combo)

        set_role_btn = QPushButton("Установить роль")
        set_role_btn.clicked.connect(self.set_user_role)
        role_layout.addWidget(set_role_btn)

        users_layout.addLayout(role_layout)
        users_widget.setLayout(users_layout)
        admin_tabs.addTab(users_widget, "Пользователи")

        # Support admin tab
        support_admin_widget = QWidget()
        support_admin_layout = QVBoxLayout()

        inbox_label = QLabel("Входящие от пользователей")
        inbox_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        support_admin_layout.addWidget(inbox_label)

        self.support_inbox_list = QListWidget()
        self.support_inbox_list.itemClicked.connect(self.on_select_support_user)
        support_admin_layout.addWidget(self.support_inbox_list)

        thread_label = QLabel("Переписка")
        thread_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        support_admin_layout.addWidget(thread_label)

        self.support_admin_thread_view = QTextEdit()
        self.support_admin_thread_view.setReadOnly(True)
        support_admin_layout.addWidget(self.support_admin_thread_view)

        input_layout = QHBoxLayout()
        self.support_admin_input = QTextEdit()
        self.support_admin_input.setFixedHeight(60)
        input_layout.addWidget(self.support_admin_input)

        send_reply_btn = QPushButton("Ответить")
        send_reply_btn.clicked.connect(self.send_admin_support_reply)
        input_layout.addWidget(send_reply_btn)

        support_admin_layout.addLayout(input_layout)
        support_admin_widget.setLayout(support_admin_layout)
        admin_tabs.addTab(support_admin_widget, "Поддержка")

        self.admin_widget.setLayout(QVBoxLayout())
        self.admin_widget.layout().addWidget(admin_tabs)

    def load_chats_list(self):
        self.chats_list.clear()
        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        chats = get_user_chats(self.user_id, conn)
        conn.close()

        for chat_id, title, last_activity, last_message in chats:
            preview = last_message[:50] + '...' if last_message else "Нет сообщений"
            item = QListWidgetItem(f"{title}\n{preview}")
            item.setData(Qt.ItemDataRole.UserRole, chat_id)
            self.chats_list.addItem(item)

    def on_chat_selected(self, item):
        if item:
            self.current_chat_id = item.data(Qt.ItemDataRole.UserRole)
            self.load_chat_history()

    def load_chat_history(self):
        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        history = get_message_history(self.current_chat_id, conn)
        conn.close()

        html = ""
        for sender, content in history:
            if sender == 'user':
                html += f"<div style='margin: 10px; padding: 12px; background: #87CEEB ; border-radius: 12px; max-width: 70%; margin-left: auto;'>"
                html += f"<b>Вы:</b><br>{content}</div>"
            else:
                html += f"<div style='margin: 10px; padding: 12px; background: #f1f5f9; border: 1px solid #e5e7eb; color: #0f172a; border-radius: 12px; max-width: 70%;'>"
                html += f"<b>Бот:</b><br>{content}</div>"
        self.chat_display.setHtml(html)

        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def start_new_chat(self):
        # Забаненные пользователи не могут создавать новые чаты
        if self.role == 'banned':
            return

        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        chat_id = create_new_chat(self.user_id, conn)
        conn.close()

        self.current_chat_id = chat_id
        self.chat_display.clear()
        self.message_input.clear()

        # Обновляем список чатов
        self.load_chats_list()

        # Находим и выбираем новый чат в списке
        for i in range(self.chats_list.count()):
            item = self.chats_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == chat_id:
                self.chats_list.setCurrentItem(item)
                break

        # Если чат не найден в списке (что не должно происходить), загружаем его историю напрямую
        if self.current_chat_id:
            self.load_chat_history()

    def get_access_token(self):
        if not GIGACHAT_AUTH_KEY:
            raise RuntimeError("GIGACHAT_AUTH_KEY не задан в окружении")
        headers = {
            "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
        }
        data = {"scope": GIGACHAT_SCOPE}
        resp = requests.post(OAUTH_URL, headers=headers, data=data, timeout=20, verify=False)
        resp.raise_for_status()
        j = resp.json()
        if "access_token" not in j:
            raise RuntimeError("Не удалось получить access_token")
        return j["access_token"]

    def send_message(self):
        # Забаненные пользователи не могут отправлять сообщения
        if self.role == 'banned':
            return

        # Если нет активного чата, создаем новый
        if not self.current_chat_id:
            self.start_new_chat()

        message = self.message_input.toPlainText().strip()
        if not message:
            return

        # Добавляем сообщение пользователя в чат сразу
        user_message_html = f"<div style='margin: 10px; padding: 12px; background: #87CEEB; border-radius: 12px; max-width: 70%; margin-left: auto;'>"
        user_message_html += f"<b>Вы:</b><br>{message}</div>"
        current_html = self.chat_display.toHtml()
        self.chat_display.setHtml(current_html + user_message_html)
        self.message_input.clear()

        # Прокрутка вниз
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)

        add_message(self.current_chat_id, self.user_id, 'user', message, conn)
        history = get_message_history(self.current_chat_id, conn)

        messages_list = [{"role": "user" if sender == 'user' else "assistant", "content": content}
                         for sender, content in history]

        token = self.get_access_token()
        self.chat_thread = GigaChatThread(messages_list, token)
        self.chat_thread.response_received.connect(self.on_gigachat_response)
        self.chat_thread.error_occurred.connect(self.on_gigachat_error)
        self.chat_thread.start()

        self.send_btn.setEnabled(False)
        self.send_btn.setText("⏳")
        conn.close()

    def on_gigachat_response(self, answer, prompt_tokens, response_tokens):
        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)

        add_message(self.current_chat_id, self.user_id, 'bot', answer, conn)
        log_token_usage(self.user_id, prompt_tokens, response_tokens, self.current_chat_id, conn)
        conn.close()

        # Добавляем ответ бота в чат
        bot_message_html = f"<div style='margin: 10px; padding: 12px; background: #f1f5f9; border: 1px solid #e5e7eb; color: #0f172a; border-radius: 12px; max-width: 70%;'>"
        bot_message_html += f"<b>Бот:</b><br>{answer}</div>"
        current_html = self.chat_display.toHtml()
        self.chat_display.setHtml(current_html + bot_message_html)

        # Прокрутка вниз
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

        self.send_btn.setEnabled(True)
        self.send_btn.setText("➤")

        # Обновляем список чатов для отображения последнего сообщения
        self.load_chats_list()

    def on_gigachat_error(self, error_msg):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("➤")

    def eventFilter(self, obj, event):
        # Глушим любые события показа tooltip в зоне чата
        if event.type() == QEvent.Type.ToolTip:
            return True
        return super().eventFilter(obj, event)

    def update_balance_info(self):
        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        balance, current_discount, total_tokens = get_balance_and_info(self.user_id, conn)
        conn.close()

        # Обновление лейблов с эмодзи
        self.balance_label.setText(f"Баланс: {balance:.2f} руб")
        self.discount_label.setText(f"Текущая скидка: {current_discount}%")
        self.tokens_label.setText(f"Общее использованных токенов: {total_tokens:,}")

    def process_payment(self):
        # Забаненные пользователи не могут совершать платежи
        if self.role == 'banned':
            return

        amount = self.amount_input.value()
        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        simulate_payment(self.user_id, amount, conn)
        conn.close()

        self.update_balance_info()

    def send_support_message(self):
        # Забаненные пользователи не могут отправлять сообщения в поддержку
        if self.role == 'banned':
            return

        message = self.support_message.toPlainText().strip()
        if not message:
            return

        conn = get_db_connection_by_role(self.get_user_sql_role())
        support_send_user_message(self.user_id, message, conn)
        conn.close()
        self.support_message.clear()
        self.load_support_thread_for_user()

    def load_support_thread_for_user(self):
        # Забаненные пользователи не имеют доступа к поддержке
        if self.role == 'banned':
            return

        sql_role = self.get_user_sql_role()
        conn = get_db_connection_by_role(sql_role)
        # Читаем всю переписку
        rows = support_get_thread(self.user_id, conn)
        # Помечаем ответы админа как прочитанные
        support_mark_user_read(self.user_id, conn)
        conn.close()

        html = ""
        for author, content, created_at in rows:
            if author == 'user':
                html += f"<div style='margin: 8px; padding: 10px; background: #87CEEB; border-radius: 10px; max-width: 75%; margin-left:auto;'><b>Вы</b><br>{content}</div>"
            else:
                html += f"<div style='margin: 8px; padding: 10px; background: #90EE90; border-radius: 10px; max-width: 75%;'><b>Админ</b><br>{content}</div>"
        self.support_thread_view.setHtml(html)

    def set_user_role(self):
        target_username = self.username_input.text().strip()
        new_role = self.role_combo.currentText()

        if not target_username:
            return

        conn = get_db_connection_by_role('admin')
        success, msg = set_user_role(target_username, new_role, self.user_id, conn)
        conn.close()

        self.load_users_list()

    def load_users_list(self):
        conn = get_db_connection_by_role('admin')
        cur = conn.cursor()
        cur.execute("""
            SELECT u.user_id, u.username, u.role, 
                   COALESCE(ub.total_tokens, 0) as tokens,
                   COALESCE(ub.current_discount, 0) as discount
            FROM users u
            LEFT JOIN user_balance ub ON u.user_id = ub.user_id
            ORDER BY u.user_id;
        """)
        users = cur.fetchall()

        message_text = "<h3>👥 Зарегистрированные пользователи:</h3><br>"
        for user in users:
            user_id, username, role, tokens, discount = user
            username_display = f"@{username}" if username else f"ID {user_id}"
            message_text += f"<div style='margin: 10px 0; padding: 10px; background: #87CEEB; border-radius: 8px;'>"
            message_text += f"<b>{username_display}</b><br>"
            message_text += f"ID: {user_id}<br>"
            message_text += f"Роль: {role} | Токены: {tokens:,}<br>"
            message_text += f"Скидка: {discount}%"
            message_text += "</div>"

        cur.execute("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN role = 'admin' THEN 1 END) as admins,
                COUNT(CASE WHEN role = 'banned' THEN 1 END) as banned
            FROM users;
        """)
        stats = cur.fetchone()
        stats_text = f"<br><h3> Статистика:</h3>"
        stats_text += f"Всего пользователей: <b>{stats[0]}</b><br>"
        stats_text += f"Админов: <b>{stats[1]}</b><br>"
        stats_text += f"Заблокированных: <b>{stats[2]}</b><br>"

        self.users_list.setHtml(message_text + stats_text)
        cur.close()
        conn.close()

    # ===== Админ: работа с поддержкой =====
    def load_support_inbox(self):
        conn = get_db_connection_by_role('admin')
        rows = support_get_inbox(conn)
        conn.close()
        self.support_inbox_list.clear()
        for user_id, username, last_message, unread in rows:
            name = f"@{username}" if username else f"ID {user_id}"
            badge = f" ({unread})" if unread else ""
            self.support_inbox_list.addItem(f"{user_id}: {name}{badge}")

    def on_select_support_user(self):
        items = self.support_inbox_list.selectedItems()
        if not items:
            return
        text = items[0].text()
        target_user_id = int(text.split(":")[0])
        self.load_support_thread_for_admin(target_user_id)

    def load_support_thread_for_admin(self, target_user_id: int):
        conn = get_db_connection_by_role('admin')
        rows = support_get_thread(target_user_id, conn)
        # Помечаем непрочитанные от пользователя как прочитанные для админа
        support_mark_admin_read(target_user_id, conn)
        conn.close()

        html = ""
        for author, content, created_at in rows:
            if author == 'user':
                html += f"<div style='margin: 8px; padding: 10px; background: #87CEEB; border-radius: 10px; max-width: 75%;'><b>Пользователь</b><br>{content}</div>"
            else:
                html += f"<div style='margin: 8px; padding: 10px; background: #90EE90; border-radius: 10px; max-width: 75%; margin-left:auto;'><b>Вы</b><br>{content}</div>"
        self.support_admin_thread_view.setHtml(html)
        # Сохраняем текущего выбранного пользователя для ответа
        self._support_target_user_id = target_user_id

    def send_admin_support_reply(self):
        content = self.support_admin_input.toPlainText().strip()
        if not content:
            return
        target_user_id = getattr(self, '_support_target_user_id', None)
        if not target_user_id:
            return
        conn = get_db_connection_by_role('admin')
        ok, msg = support_send_admin_reply(self.user_id, target_user_id, content, conn)
        conn.close()
        if not ok:
            return
        self.support_admin_input.clear()
        self.load_support_thread_for_admin(target_user_id)
        self.load_support_inbox()

    def get_user_sql_role(self):
        return self.role if self.role in ['admin', 'banned'] else 'user'


if __name__ == "__main__":
    import faulthandler, traceback

    faulthandler.enable(all_threads=True)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    init_db()
    window = ModernMainWindow()
    if window.user_id:
        window.show()
    sys.exit(app.exec())
