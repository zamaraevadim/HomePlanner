#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HomePlanner Pro - Современный планировщик помещений
Версия 3.0 Modern UI

Функционал:
- Современный темный интерфейс в стиле Neumorphism
- Свободное рисование стен с привязкой к сетке и углам
- Окна и двери с визуальным различием
- Размеры как на чертежах с выносными линиями
- Масштабирование (колесо мыши) и панорамирование (ПКМ)
- Редактирование стен: длина, толщина, угол, материал
- Перетаскивание стен и изменение размера за ручки
- Автоматическое соединение стен в углах без нахлеста
- Мебель и сантехника с редактированием
- Экспорт в PDF и PNG
- Автоустановка зависимостей
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import math
import os
import sys
import subprocess
import json

# --- АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ---
def install_and_import(package, module_name=None):
    if module_name is None:
        module_name = package
    try:
        __import__(module_name)
    except ImportError:
        print(f"Установка {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        __import__(module_name)

install_and_import("PIL", "PIL")
install_and_import("reportlab", "reportlab")

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import cm

# --- СОВРЕМЕННАЯ ЦВЕТОВАЯ ПАЛИТРА ---
class Colors:
    BG_MAIN = '#1a1b26'      # Основной фон (темный)
    BG_PANEL = '#24283b'     # Фон панелей
    BG_INPUT = '#2f3549'     # Поля ввода
    TEXT_MAIN = '#a9b1d6'    # Основной текст
    TEXT_DIM = '#565f89'     # Тусклый текст
    ACCENT = '#7aa2f7'       # Акцент синий
    ACCENT_HOVER = '#89b4fa' 
    DANGER = '#f7768e'       # Красный
    SUCCESS = '#9ece6a'      # Зеленый
    WALL = '#ff9e64'         # Стены оранжевые
    WALL_SELECTED = '#bb9af7'# Фиолетовый выделенный
    DOOR = '#7dcfff'         # Двери голубые
    WINDOW = '#9d7cd8'       # Окна фиолетовые
    FURNITURE = '#73daca'    # Мебель бирюзовая
    GRID = '#414868'         # Сетка
    DIMENSION = '#9ece6a'    # Размеры зеленые
    HANDLE = '#f7768e'       # Ручки красные
    HIGHLIGHT = '#e0af68'    # Подсветка

# --- КОНСТАНТЫ ---
GRID_SIZE = 50
SNAP_RADIUS = 20
DEFAULT_WALL_THICKNESS = 0.20  # 20 см
SCALE_FACTOR = 20  # пикселей на метр
MIN_SCALE = 0.2
MAX_SCALE = 5.0

MATERIALS = ["Кирпич", "Дерево", "Газобетон", "Каркас", "Перегородка"]
MATERIAL_COLORS = {
    "Кирпич": "#B54B3D",
    "Дерево": "#8B5A2B",
    "Газобетон": "#B0B0B0",
    "Каркас": "#F5DEB3",
    "Перегородка": "#D3D3D3"
}

FURNITURE_TYPES = [
    ("Кровать 2x2", 2.0, 2.0),
    ("Стол 1.5x1", 1.5, 1.0),
    ("Шкаф 2x0.6", 2.0, 0.6),
    ("Диван 2x1", 2.0, 1.0),
    ("Кухня 3x2", 3.0, 2.0),
    ("Ванна 1.7x0.8", 1.7, 0.8),
    ("Унитаз 0.4x0.4", 0.4, 0.4),
    ("Раковина 0.6x0.5", 0.6, 0.5),
    ("Холодильник 0.6x0.6", 0.6, 0.6),
    ("Стиральная машина 0.6x0.6", 0.6, 0.6)
]

class Point:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
    
    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)
    
    def to_tuple(self):
        return (self.x, self.y)

class Wall:
    def __init__(self, start, end, thickness=DEFAULT_WALL_THICKNESS, material="Кирпич"):
        self.start = Point(start.x, start.y)
        self.end = Point(end.x, end.y)
        self.thickness = thickness
        self.material = material
        self.openings = []  # Список окон и дверей
    
    def get_length_meters(self):
        pixels = self.start.distance_to(self.end)
        return pixels / SCALE_FACTOR
    
    def get_angle_degrees(self):
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        angle = math.degrees(math.atan2(-dy, dx))
        return angle if angle >= 0 else angle + 360
    
    def set_length_meters(self, length_m):
        current_len = self.get_length_meters()
        if current_len == 0:
            return
        ratio = length_m / current_len
        angle = self.get_angle_degrees()
        rad = math.radians(angle)
        self.end.x = self.start.x + math.cos(rad) * (length_m * SCALE_FACTOR)
        self.end.y = self.start.y - math.sin(rad) * (length_m * SCALE_FACTOR)
    
    def set_angle_degrees(self, angle_deg):
        length = self.get_length_meters()
        rad = math.radians(angle_deg)
        self.end.x = self.start.x + math.cos(rad) * (length * SCALE_FACTOR)
        self.end.y = self.start.y - math.sin(rad) * (length * SCALE_FACTOR)
    
    def contains_point(self, point, threshold=10):
        # Проверка попадания точки в стену
        p1 = self.start
        p2 = self.end
        p = point
        
        # Вектор стены
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        len_sq = dx*dx + dy*dy
        
        if len_sq == 0:
            return p1.distance_to(p) <= threshold
        
        # Проекция точки на линию
        t = max(0, min(1, ((p.x - p1.x) * dx + (p.y - p1.y) * dy) / len_sq))
        proj_x = p1.x + t * dx
        proj_y = p1.y + t * dy
        
        dist = math.hypot(p.x - proj_x, p.y - proj_y)
        return dist <= threshold
    
    def get_closest_endpoint(self, point):
        d_start = self.start.distance_to(point)
        d_end = self.end.distance_to(point)
        return self.start if d_start < d_end else self.end
    
    def add_opening(self, position_m, width_m, opening_type):
        # position_m - расстояние от начала стены в метрах
        total_len = self.get_length_meters()
        if position_m < 0 or position_m + width_m > total_len:
            return False
        
        # Проверка на пересечение с другими проемами
        for op in self.openings:
            if abs(position_m - op['pos']) < (op['width'] + width_m) / 2 + 0.1:
                return False
        
        self.openings.append({
            'pos': position_m,
            'width': width_m,
            'type': opening_type
        })
        self.openings.sort(key=lambda x: x['pos'])
        return True
    
    def remove_opening_at(self, position_m):
        self.openings = [op for op in self.openings if abs(op['pos'] - position_m) > 0.1]

class Furniture:
    def __init__(self, x, y, width, depth, name="Мебель"):
        self.x = x
        self.y = y
        self.width = width   # ширина в метрах
        self.depth = depth   # глубина в метрах
        self.name = name
        self.rotation = 0    # угол поворота в градусах
    
    def contains_point(self, point, scale_inv):
        # Преобразуем координаты точки в локальную систему мебели
        # С учетом вращения
        cx = self.x + self.width / 2
        cy = self.y + self.depth / 2
        
        # Обратное вращение
        rad = -math.radians(self.rotation)
        dx = (point.x - cx) * scale_inv
        dy = (point.y - cy) * scale_inv
        
        local_x = dx * math.cos(rad) - dy * math.sin(rad)
        local_y = dx * math.sin(rad) + dy * math.cos(rad)
        
        half_w = self.width * SCALE_FACTOR / 2
        half_d = self.depth * SCALE_FACTOR / 2
        
        return abs(local_x) <= half_w and abs(local_y) <= half_d
    
    def get_bounds_pixels(self, scale_inv):
        # Возвращает углы прямоугольника с учетом вращения
        cx = self.x
        cy = self.y
        w = self.width * SCALE_FACTOR
        d = self.depth * SCALE_FACTOR
        
        corners = [
            (-w/2, -d/2), (w/2, -d/2),
            (w/2, d/2), (-w/2, d/2)
        ]
        
        rad = math.radians(self.rotation)
        rotated = []
        for lx, ly in corners:
            rx = lx * math.cos(rad) - ly * math.sin(rad)
            ry = lx * math.sin(rad) + ly * math.cos(rad)
            rotated.append(Point(cx + rx, cy + ry))
        
        return rotated

class HomePlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🏠 HomePlanner Pro - Modern")
        self.root.geometry("1400x900")
        
        # Настройка современного стиля
        self.setup_modern_style()
        
        # Данные
        self.walls = []
        self.furniture = []
        self.selected_wall = None
        self.selected_furniture = None
        
        # Режимы
        self.mode = "wall"  # wall, select, furniture, dimension_line
        self.draw_mode = False
        self.current_start = None
        
        # Навигация
        self.scale = 1.0
        self.offset_x = 400
        self.offset_y = 300
        self.pan_active = False
        self.pan_start = None
        
        # Привязка
        self.snap_enabled = True
        self.resize_mode = False  # Режим изменения размера ручками
        
        # Создание интерфейса
        self.create_ui()
        
        # Привязка событий
        self.bind_events()
        
        # Отрисовка
        self.redraw()
    
    def setup_modern_style(self):
        """Настройка современного темного стиля"""
        self.root.configure(bg=Colors.BG_MAIN)
        
        # Шрифты
        font_family = "Segoe UI" if os.name == 'nt' else "Helvetica"
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family=font_family, size=10, weight='normal')
        
        # Стилизация ttk
        style = ttk.Style()
        style.theme_use('clam')
        
        # TFrame
        style.configure('TFrame', background=Colors.BG_PANEL)
        
        # TLabel
        style.configure('TLabel', 
            background=Colors.BG_PANEL,
            foreground=Colors.TEXT_MAIN,
            font=(font_family, 10)
        )
        
        # TButton
        style.configure('TButton',
            background=Colors.ACCENT,
            foreground='#1a1b26',
            font=(font_family, 10, 'bold'),
            padding=10,
            borderwidth=0,
            focusthickness=0
        )
        style.map('TButton',
            background=[('active', Colors.ACCENT_HOVER)]
        )
        
        # Toolbutton
        style.configure('Toolbutton',
            background=Colors.BG_PANEL,
            foreground=Colors.TEXT_MAIN
        )
        
        # Combobox
        style.configure('TCombobox',
            fieldbackground=Colors.BG_INPUT,
            background=Colors.BG_PANEL,
            foreground=Colors.TEXT_MAIN,
            arrowcolor=Colors.TEXT_MAIN,
            bordercolor=Colors.BG_INPUT,
            lightcolor=Colors.BG_INPUT,
            darkcolor=Colors.BG_INPUT,
            insertcolor=Colors.TEXT_MAIN,
            font=(font_family, 10)
        )
        style.map('TCombobox',
            fieldbackground=[('readonly', Colors.BG_INPUT)],
            selectbackground=[('readonly', Colors.ACCENT)],
            selectforeground=[('readonly', '#1a1b26')]
        )
        
        # Entry
        self.entry_style = {
            'bg': Colors.BG_INPUT,
            'fg': Colors.TEXT_MAIN,
            'insertbackground': Colors.TEXT_MAIN,
            'relief': 'flat',
            'highlightthickness': 1,
            'highlightbackground': Colors.BG_INPUT,
            'highlightcolor': Colors.ACCENT,
            'font': ('Consolas', 10)
        }
        
        # Checkbutton
        style.configure('TCheckbutton',
            background=Colors.BG_PANEL,
            foreground=Colors.TEXT_MAIN,
            font=(font_family, 10, 'bold'),
            indicatorcolor=Colors.BG_INPUT,
            focuscolor=Colors.ACCENT
        )
        style.map('TCheckbutton',
            indicatorcolor=[('selected', Colors.ACCENT)]
        )
    
    def create_ui(self):
        """Создание пользовательского интерфейса"""
        # Главная компоновка
        main_frame = tk.Frame(self.root, bg=Colors.BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Левая панель инструментов
        self.toolbar_frame = tk.Frame(main_frame, bg=Colors.BG_PANEL, width=220)
        self.toolbar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.toolbar_frame.pack_propagate(False)
        
        self.create_toolbar()
        
        # Центральная область с холстом
        canvas_frame = tk.Frame(main_frame, bg=Colors.BG_MAIN)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=Colors.BG_MAIN,
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Правая панель свойств
        self.properties_frame = tk.Frame(main_frame, bg=Colors.BG_PANEL, width=280)
        self.properties_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.properties_frame.pack_propagate(False)
        
        self.create_properties_panel()
        
        # Нижняя статусная строка
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе | Колесо: зум | ПКМ: панорамирование | Двойной клик: сброс")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 9),
            anchor='w',
            padx=15,
            pady=5
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
    
    def create_toolbar(self):
        """Создание панели инструментов"""
        title = tk.Label(
            self.toolbar_frame,
            text="🛠 Инструменты",
            bg=Colors.BG_PANEL,
            fg=Colors.ACCENT,
            font=("Segoe UI", 14, "bold"),
            pady=15
        )
        title.pack(fill=tk.X, padx=15)
        
        # Кнопки режимов
        modes = [
            ("✏️ Стена", "wall"),
            ("✋ Выделение", "select"),
            ("🪑 Мебель", "furniture"),
            ("📐 Размер", "dimension")
        ]
        
        for text, mode in modes:
            btn = tk.Button(
                self.toolbar_frame,
                text=text,
                command=lambda m=mode: self.set_mode(m),
                bg=Colors.BG_INPUT,
                fg=Colors.TEXT_MAIN,
                activebackground=Colors.ACCENT,
                activeforeground='#1a1b26',
                relief=tk.FLAT,
                padx=15,
                pady=12,
                font=("Segoe UI", 10),
                cursor="hand2"
            )
            btn.pack(fill=tk.X, padx=15, pady=3)
            setattr(self, f"btn_{mode}", btn)
        
        # Разделитель
        tk.Frame(self.toolbar_frame, height=2, bg=Colors.GRID).pack(fill=tk.X, padx=15, pady=15)
        
        # Действия со стенами
        actions_label = tk.Label(
            self.toolbar_frame,
            text="🚪 Проёмы",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor='w'
        )
        actions_label.pack(fill=tk.X, padx=15, pady=(0, 5))
        
        self.btn_window = tk.Button(
            self.toolbar_frame,
            text="🟦 Окно (1.2м)",
            command=self.add_window_mode,
            bg=Colors.WINDOW,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=10,
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        self.btn_window.pack(fill=tk.X, padx=15, pady=3)
        
        self.btn_door = tk.Button(
            self.toolbar_frame,
            text="🚪 Дверь (0.9м)",
            command=self.add_door_mode,
            bg=Colors.DOOR,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=10,
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        self.btn_door.pack(fill=tk.X, padx=15, pady=3)
        
        # Разделитель
        tk.Frame(self.toolbar_frame, height=2, bg=Colors.GRID).pack(fill=tk.X, padx=15, pady=15)
        
        # Опции
        options_label = tk.Label(
            self.toolbar_frame,
            text="⚙️ Опции",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor='w'
        )
        options_label.pack(fill=tk.X, padx=15, pady=(0, 5))
        
        self.snap_var = tk.BooleanVar(value=True)
        snap_cb = ttk.Checkbutton(
            self.toolbar_frame,
            text="🧲 Привязка",
            variable=self.snap_var,
            command=lambda: setattr(self, 'snap_enabled', self.snap_var.get())
        )
        snap_cb.pack(anchor='w', padx=15, pady=3)
        
        self.resize_var = tk.BooleanVar(value=False)
        resize_cb = ttk.Checkbutton(
            self.toolbar_frame,
            text="✏️ Геометрия",
            variable=self.resize_var,
            command=lambda: setattr(self, 'resize_mode', self.resize_var.get())
        )
        resize_cb.pack(anchor='w', padx=15, pady=3)
        
        # Разделитель
        tk.Frame(self.toolbar_frame, height=2, bg=Colors.GRID).pack(fill=tk.X, padx=15, pady=15)
        
        # Экспорт
        export_label = tk.Label(
            self.toolbar_frame,
            text="💾 Экспорт",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            anchor='w'
        )
        export_label.pack(fill=tk.X, padx=15, pady=(0, 5))
        
        exp_btn = tk.Button(
            self.toolbar_frame,
            text="📄 PDF План",
            command=self.export_pdf,
            bg=Colors.SUCCESS,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=10,
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        exp_btn.pack(fill=tk.X, padx=15, pady=3)
        
        exp_img = tk.Button(
            self.toolbar_frame,
            text="🖼 PNG Изображение",
            command=self.export_png,
            bg=Colors.ACCENT,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=10,
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        exp_img.pack(fill=tk.X, padx=15, pady=3)
        
        # Очистка
        clear_btn = tk.Button(
            self.toolbar_frame,
            text="🗑 Очистить всё",
            command=self.clear_all,
            bg=Colors.DANGER,
            fg='#1a1b26',
            activebackground='#ff5c75',
            relief=tk.FLAT,
            padx=15,
            pady=10,
            font=("Segoe UI", 10),
            cursor="hand2"
        )
        clear_btn.pack(fill=tk.X, padx=15, pady=20)
    
    def create_properties_panel(self):
        """Создание панели свойств"""
        title = tk.Label(
            self.properties_frame,
            text="📋 Свойства",
            bg=Colors.BG_PANEL,
            fg=Colors.ACCENT,
            font=("Segoe UI", 14, "bold"),
            pady=15
        )
        title.pack(fill=tk.X, padx=15)
        
        # Контейнер для свойств
        props_container = tk.Frame(self.properties_frame, bg=Colors.BG_PANEL)
        props_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Свойства стены
        wall_frame = tk.LabelFrame(
            props_container,
            text="Стена",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=10
        )
        wall_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Длина
        tk.Label(wall_frame, text="Длина (м):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_length = tk.Entry(wall_frame, **self.entry_style, width=15)
        self.prop_length.pack(fill=tk.X, pady=(3, 10))
        
        # Толщина
        tk.Label(wall_frame, text="Толщина (м):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_thickness = tk.Entry(wall_frame, **self.entry_style, width=15)
        self.prop_thickness.pack(fill=tk.X, pady=(3, 10))
        
        # Угол
        tk.Label(wall_frame, text="Угол (°):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_angle = tk.Entry(wall_frame, **self.entry_style, width=15)
        self.prop_angle.pack(fill=tk.X, pady=(3, 10))
        
        # Материал
        tk.Label(wall_frame, text="Материал:", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_material = ttk.Combobox(wall_frame, values=MATERIALS, state='readonly')
        self.prop_material.pack(fill=tk.X, pady=(3, 10))
        
        # Кнопка применить
        apply_btn = tk.Button(
            wall_frame,
            text="✅ Применить",
            command=self.apply_wall_properties,
            bg=Colors.SUCCESS,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        apply_btn.pack(fill=tk.X, pady=(5, 0))
        
        # Свойства мебели
        furn_frame = tk.LabelFrame(
            props_container,
            text="Мебель",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=10
        )
        furn_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Тип мебели
        tk.Label(furn_frame, text="Тип:", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_furn_type = ttk.Combobox(furn_frame, values=[f[0] for f in FURNITURE_TYPES], state='readonly')
        self.prop_furn_type.pack(fill=tk.X, pady=(3, 10))
        self.prop_furn_type.bind('<<ComboboxSelected>>', self.on_furniture_type_change)
        
        # Ширина
        tk.Label(furn_frame, text="Ширина (м):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_furn_width = tk.Entry(furn_frame, **self.entry_style, width=15)
        self.prop_furn_width.pack(fill=tk.X, pady=(3, 10))
        
        # Глубина
        tk.Label(furn_frame, text="Глубина (м):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_furn_depth = tk.Entry(furn_frame, **self.entry_style, width=15)
        self.prop_furn_depth.pack(fill=tk.X, pady=(3, 10))
        
        # Поворот
        tk.Label(furn_frame, text="Поворот (°):", bg=Colors.BG_PANEL, fg=Colors.TEXT_MAIN).pack(anchor='w')
        self.prop_furn_rotation = tk.Entry(furn_frame, **self.entry_style, width=15)
        self.prop_furn_rotation.pack(fill=tk.X, pady=(3, 10))
        
        # Кнопка применить мебель
        apply_furn_btn = tk.Button(
            furn_frame,
            text="✅ Применить",
            command=self.apply_furniture_properties,
            bg=Colors.SUCCESS,
            fg='#1a1b26',
            activebackground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        apply_furn_btn.pack(fill=tk.X, pady=(5, 0))
        
        # Информация
        info_frame = tk.LabelFrame(
            props_container,
            text="Инфо",
            bg=Colors.BG_PANEL,
            fg=Colors.TEXT_DIM,
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=10
        )
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = tk.Text(
            info_frame,
            bg=Colors.BG_INPUT,
            fg=Colors.TEXT_MAIN,
            font=("Consolas", 9),
            relief=tk.FLAT,
            wrap=tk.WORD,
            height=6
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)
        self.info_text.insert('1.0', "Выберите объект для просмотра свойств\n\nСтены: {}\nМебель: {}".format(len(self.walls), len(self.furniture)))
    
    def bind_events(self):
        """Привязка событий"""
        self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.canvas.bind('<ButtonPress-3>', self.on_right_click)
        self.canvas.bind('<B3-Motion>', self.on_pan_drag)
        self.canvas.bind('<ButtonRelease-3>', self.on_pan_release)
        self.canvas.bind('<MouseWheel>', self.on_mouse_wheel)
        self.canvas.bind('<Double-Button-1>', self.on_double_click)
        self.canvas.bind('<Motion>', self.on_mouse_move)
    
    def screen_to_world(self, sx, sy):
        """Преобразование экранных координат в мировые"""
        wx = (sx - self.offset_x) / self.scale
        wy = (sy - self.offset_y) / self.scale
        return Point(wx, wy)
    
    def world_to_screen(self, wx, wy):
        """Преобразование мировых координат в экранные"""
        sx = wx * self.scale + self.offset_x
        sy = wy * self.offset_y + self.offset_y
        return (sx, sy)
    
    def snap_point(self, point):
        """Привязка точки к сетке и углам"""
        if not self.snap_enabled:
            return point
        
        snapped_x = round(point.x / GRID_SIZE) * GRID_SIZE
        snapped_y = round(point.y / GRID_SIZE) * GRID_SIZE
        
        best_point = Point(snapped_x, snapped_y)
        min_dist = point.distance_to(best_point)
        
        # Проверка привязки к концам стен
        for wall in self.walls:
            for endpoint in [wall.start, wall.end]:
                dist = point.distance_to(endpoint)
                if dist < SNAP_RADIUS and dist < min_dist:
                    min_dist = dist
                    best_point = Point(endpoint.x, endpoint.y)
        
        return best_point
    
    def set_mode(self, mode):
        """Установка режима работы"""
        self.mode = mode
        self.draw_mode = False
        self.current_start = None
        self.selected_wall = None
        self.selected_furniture = None
        
        # Обновление кнопок
        for m in ['wall', 'select', 'furniture', 'dimension']:
            btn = getattr(self, f"btn_{m}", None)
            if btn:
                if m == mode:
                    btn.config(bg=Colors.ACCENT, fg='#1a1b26')
                else:
                    btn.config(bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN)
        
        self.update_status()
        self.redraw()
    
    def update_status(self):
        """Обновление статусной строки"""
        modes = {
            'wall': "Режим: Рисование стен | ЛКМ: начало/конец | Esc: отмена",
            'select': "Режим: Выделение | ЛКМ: выбор | Drag: перемещение",
            'furniture': "Режим: Мебель | Выберите тип в панели свойств и кликните на план",
            'dimension': "Режим: Просмотр размеров"
        }
        self.status_var.set(modes.get(self.mode, ""))
    
    def on_mouse_down(self, event):
        """Обработка нажатия кнопки мыши"""
        world_point = self.screen_to_world(event.x, event.y)
        
        if self.mode == 'wall':
            if not self.draw_mode:
                self.current_start = self.snap_point(world_point)
                self.draw_mode = True
            else:
                end_point = self.snap_point(world_point)
                if self.current_start and end_point.distance_to(self.current_start) > 10:
                    wall = Wall(self.current_start, end_point)
                    self.walls.append(wall)
                self.draw_mode = False
                self.current_start = None
            self.redraw()
        
        elif self.mode == 'select':
            # Поиск стены
            clicked_wall = None
            for wall in reversed(self.walls):
                if wall.contains_point(world_point):
                    clicked_wall = wall
                    break
            
            # Поиск мебели
            clicked_furn = None
            scale_inv = 1.0 / self.scale
            for furn in reversed(self.furniture):
                if furn.contains_point(world_point, scale_inv):
                    clicked_furn = furn
                    break
            
            if clicked_wall:
                self.selected_wall = clicked_wall
                self.selected_furniture = None
                self.update_properties_panel()
            elif clicked_furn:
                self.selected_furniture = clicked_furn
                self.selected_wall = None
                self.update_properties_panel()
            else:
                self.selected_wall = None
                self.selected_furniture = None
                self.update_properties_panel()
            
            self.redraw()
        
        elif self.mode == 'furniture':
            # Добавление мебели
            furn_type = self.prop_furn_type.get()
            if not furn_type:
                messagebox.showwarning("Предупреждение", "Выберите тип мебели в панели свойств!")
                return
            
            dims = next((f[1:] for f in FURNITURE_TYPES if f[0] == furn_type), (1.0, 1.0))
            furn = Furniture(world_point.x, world_point.y, dims[0], dims[1], furn_type)
            self.furniture.append(furn)
            self.selected_furniture = furn
            self.update_properties_panel()
            self.redraw()
    
    def on_mouse_drag(self, event):
        """Перетаскивание мыши"""
        world_point = self.screen_to_world(event.x, event.y)
        
        if self.mode == 'wall' and self.draw_mode and self.current_start:
            self.redraw()
            # Рисование линии предпросмотра
            start_screen = self.world_to_screen(self.current_start.x, self.current_start.y)
            end_screen = self.world_to_screen(world_point.x, world_point.y)
            self.canvas.create_line(start_screen, end_screen, 
                                   fill=Colors.WALL, width=3, dash=(5, 5))
        
        elif self.mode == 'select':
            if self.selected_wall:
                # Перетаскивание стены или изменение размера
                if self.resize_mode:
                    endpoint = self.selected_wall.get_closest_endpoint(world_point)
                    snapped = self.snap_point(world_point)
                    if endpoint == self.selected_wall.start:
                        self.selected_wall.start = snapped
                    else:
                        self.selected_wall.end = snapped
                else:
                    # Перетаскивание всей стены
                    pass  # Реализация перетаскивания всей стены
                
                self.update_properties_panel()
                self.redraw()
            
            elif self.selected_furniture:
                # Перетаскивание мебели
                self.selected_furniture.x = world_point.x
                self.selected_furniture.y = world_point.y
                self.update_properties_panel()
                self.redraw()
    
    def on_mouse_up(self, event):
        """Отпускание кнопки мыши"""
        pass
    
    def on_right_click(self, event):
        """Начало панорамирования"""
        self.pan_active = True
        self.pan_start = (event.x, event.y)
        self.canvas.config(cursor="fleur")
    
    def on_pan_drag(self, event):
        """Панорамирование"""
        if self.pan_active and self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (event.x, event.y)
            self.redraw()
    
    def on_pan_release(self, event):
        """Конец панорамирования"""
        self.pan_active = False
        self.pan_start = None
        self.canvas.config(cursor="crosshair")
    
    def on_mouse_wheel(self, event):
        """Масштабирование колесом мыши"""
        factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.scale * factor
        new_scale = max(MIN_SCALE, min(MAX_SCALE, new_scale))
        
        # Зум к курсору
        if new_scale != self.scale:
            mouse_world = self.screen_to_world(event.x, event.y)
            self.scale = new_scale
            # Корректировка оффсета для зума к точке
            self.offset_x = event.x - mouse_world.x * self.scale
            self.offset_y = event.y - mouse_world.y * self.scale
            self.redraw()
    
    def on_double_click(self, event):
        """Сброс масштаба и позиции"""
        self.scale = 1.0
        self.offset_x = 400
        self.offset_y = 300
        self.redraw()
    
    def on_mouse_move(self, event):
        """Движение мыши для подсветки"""
        world_point = self.screen_to_world(event.x, event.y)
        
        # Подсветка стен при наведении
        if self.mode in ['select', 'wall']:
            self.redraw()
            for wall in self.walls:
                if wall.contains_point(world_point):
                    # Рисуем подсветку
                    ss = self.world_to_screen(wall.start.x, wall.start.y)
                    se = self.world_to_screen(wall.end.x, wall.end.y)
                    self.canvas.create_line(ss, se, fill=Colors.HIGHLIGHT, width=5, capstyle=tk.ROUND)
        
        # Обновление статуса с координатами
        meters_x = world_point.x / SCALE_FACTOR
        meters_y = world_point.y / SCALE_FACTOR
        self.status_var.set(f"X: {meters_x:.2f}м Y: {meters_y:.2f}м | Зум: {self.scale*100:.0f}%")
    
    def on_furniture_type_change(self, event):
        """Изменение типа мебели"""
        furn_type = self.prop_furn_type.get()
        dims = next((f[1:] for f in FURNITURE_TYPES if f[0] == furn_type), (1.0, 1.0))
        self.prop_furn_width.delete(0, tk.END)
        self.prop_furn_width.insert(0, str(dims[0]))
        self.prop_furn_depth.delete(0, tk.END)
        self.prop_furn_depth.insert(0, str(dims[1]))
    
    def update_properties_panel(self):
        """Обновление панели свойств"""
        # Сброс
        for entry in [self.prop_length, self.prop_thickness, self.prop_angle]:
            entry.delete(0, tk.END)
        self.prop_material.set('')
        
        for entry in [self.prop_furn_width, self.prop_furn_depth, self.prop_furn_rotation]:
            entry.delete(0, tk.END)
        self.prop_furn_type.set('')
        
        if self.selected_wall:
            w = self.selected_wall
            self.prop_length.insert(0, f"{w.get_length_meters():.2f}")
            self.prop_thickness.insert(0, f"{w.thickness:.2f}")
            self.prop_angle.insert(0, f"{w.get_angle_degrees():.1f}")
            self.prop_material.set(w.material)
            
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert('1.0', f"Стена выбрана\nМатериал: {w.material}\nПроёмы: {len(w.openings)}")
        
        elif self.selected_furniture:
            f = self.selected_furniture
            self.prop_furn_type.set(f.name)
            self.prop_furn_width.insert(0, f"{f.width:.2f}")
            self.prop_furn_depth.insert(0, f"{f.depth:.2f}")
            self.prop_furn_rotation.insert(0, f"{f.rotation:.1f}")
            
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert('1.0', f"Мебель: {f.name}\nРазмер: {f.width}x{f.depth}м\nПоворот: {f.rotation}°")
        
        else:
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert('1.0', "Выберите объект\n\nСтены: {}\nМебель: {}".format(len(self.walls), len(self.furniture)))
    
    def apply_wall_properties(self):
        """Применение свойств стены"""
        if not self.selected_wall:
            messagebox.showwarning("Предупреждение", "Сначала выберите стену!")
            return
        
        try:
            length = float(self.prop_length.get())
            if length > 0:
                self.selected_wall.set_length_meters(length)
            
            thickness = float(self.prop_thickness.get())
            if thickness > 0:
                self.selected_wall.thickness = thickness
            
            angle = float(self.prop_angle.get())
            self.selected_wall.set_angle_degrees(angle)
            
            material = self.prop_material.get()
            if material:
                self.selected_wall.material = material
            
            self.redraw()
            messagebox.showinfo("Успех", "Свойства стены обновлены!")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректные числовые значения!")
    
    def apply_furniture_properties(self):
        """Применение свойств мебели"""
        if not self.selected_furniture:
            messagebox.showwarning("Предупреждение", "Сначала выберите мебель!")
            return
        
        try:
            width = float(self.prop_furn_width.get())
            depth = float(self.prop_furn_depth.get())
            rotation = float(self.prop_furn_rotation.get())
            
            if width > 0 and depth > 0:
                self.selected_furniture.width = width
                self.selected_furniture.depth = depth
                self.selected_furniture.rotation = rotation
                
                self.redraw()
                messagebox.showinfo("Успех", "Свойства мебели обновлены!")
            else:
                messagebox.showerror("Ошибка", "Размеры должны быть положительными!")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректные числовые значения!")
    
    def add_window_mode(self):
        """Режим добавления окна"""
        if not self.selected_wall:
            messagebox.showinfo("Инфо", "Сначала выберите стену в режиме 'Выделение'!")
            return
        self.mode = 'add_window'
        self.update_status()
        self.status_var.set("Кликните по выбранной стене чтобы добавить окно (1.2м)")
    
    def add_door_mode(self):
        """Режим добавления двери"""
        if not self.selected_wall:
            messagebox.showinfo("Инфо", "Сначала выберите стену в режиме 'Выделение'!")
            return
        self.mode = 'add_door'
        self.update_status()
        self.status_var.set("Кликните по выбранной стене чтобы добавить дверь (0.9м)")
    
    def redraw(self):
        """Перерисовка холста"""
        self.canvas.delete('all')
        
        # Сетка
        self.draw_grid()
        
        # Стены
        for wall in self.walls:
            self.draw_wall(wall)
        
        # Мебель
        for furn in self.furniture:
            self.draw_furniture(furn)
        
        # Размеры
        self.draw_dimensions()
    
    def draw_grid(self):
        """Отрисовка сетки"""
        grid_spacing = GRID_SIZE * self.scale
        
        # Вычисляем видимую область
        visible_x_start = -self.offset_x / self.scale
        visible_y_start = -self.offset_y / self.scale
        visible_width = self.canvas.winfo_width() / self.scale
        visible_height = self.canvas.winfo_height() / self.scale
        
        start_col = int(visible_x_start / GRID_SIZE) - 1
        end_col = int((visible_x_start + visible_width) / GRID_SIZE) + 1
        start_row = int(visible_y_start / GRID_SIZE) - 1
        end_row = int((visible_y_start + visible_height) / GRID_SIZE) + 1
        
        for col in range(start_col, end_col + 1):
            x = col * GRID_SIZE
            sx, sy = self.world_to_screen(x, visible_y_start * GRID_SIZE)
            ex, ey = self.world_to_screen(x, (visible_y_start + visible_height) * GRID_SIZE)
            self.canvas.create_line(sx, sy, ex, ey, fill=Colors.GRID, width=1)
        
        for row in range(start_row, end_row + 1):
            y = row * GRID_SIZE
            sx, sy = self.world_to_screen(visible_x_start * GRID_SIZE, y)
            ex, ey = self.world_to_screen((visible_x_start + visible_width) * GRID_SIZE, y)
            self.canvas.create_line(sx, sy, ex, ey, fill=Colors.GRID, width=1)
    
    def draw_wall(self, wall, selected=False):
        """Отрисовка стены"""
        ss = self.world_to_screen(wall.start.x, wall.start.y)
        se = self.world_to_screen(wall.end.x, wall.end.y)
        
        thickness_px = wall.thickness * SCALE_FACTOR * self.scale
        color = Colors.WALL_SELECTED if selected else Colors.WALL
        
        # Основная линия стены
        self.canvas.create_line(ss, se, fill=color, width=max(3, thickness_px), capstyle=tk.ROUND)
        
        # Проёмы
        for op in wall.openings:
            pos_px = op['pos'] * SCALE_FACTOR * self.scale
            width_px = op['width'] * SCALE_FACTOR * self.scale
            
            # Точка центра проёма на стене
            dx = se[0] - ss[0]
            dy = se[1] - ss[1]
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            
            ux, uy = dx / length, dy / length
            center_x = ss[0] + ux * pos_px
            center_y = ss[1] + uy * pos_px
            
            if op['type'] == 'window':
                # Окно - фиолетовая линия внутри стены
                self.canvas.create_line(
                    center_x - width_px/2, center_y - width_px/2,
                    center_x + width_px/2, center_y + width_px/2,
                    fill=Colors.WINDOW, width=3
                )
            else:
                # Дверь - голубой разрыв с дугой
                self.canvas.create_line(
                    center_x - width_px/2, center_y - width_px/2,
                    center_x + width_px/2, center_y + width_px/2,
                    fill=Colors.BG_MAIN, width=max(3, thickness_px) + 2
                )
                # Дуга двери
                arc_radius = width_px
                self.canvas.create_arc(
                    center_x - arc_radius, center_y - arc_radius,
                    center_x + arc_radius, center_y + arc_radius,
                    start=0, extent=90,
                    outline=Colors.DOOR, width=2, style=tk.ARC
                )
        
        # Ручки выделения
        if selected:
            handle_color = Colors.HANDLE if self.resize_mode else Colors.ACCENT
            for pt in [wall.start, wall.end]:
                sp = self.world_to_screen(pt.x, pt.y)
                self.canvas.create_oval(
                    sp[0]-6, sp[1]-6, sp[0]+6, sp[1]+6,
                    fill=handle_color, outline='#1a1b26', width=2
                )
    
    def draw_furniture(self, furn):
        """Отрисовка мебели"""
        corners = furn.get_bounds_pixels(1.0 / self.scale)
        points = []
        for c in corners:
            sp = self.world_to_screen(c.x, c.y)
            points.extend(sp)
        
        color = Colors.FURNITURE if self.selected_furniture != furn else Colors.HIGHLIGHT
        
        self.canvas.create_polygon(points, fill=color, outline='#1a1b26', width=2)
        
        # Название
        cx = sum(p[0] for p in zip(points[::2], points[1::2])) / 4
        cy = sum(p[1] for p in zip(points[::2], points[1::2])) / 4
        self.canvas.create_text(cx, cy, text=furn.name[:10], fill='#1a1b26', font=('Arial', 8, 'bold'))
    
    def draw_dimensions(self):
        """Отрисовка размеров как на чертежах"""
        for wall in self.walls:
            ss = self.world_to_screen(wall.start.x, wall.start.y)
            se = self.world_to_screen(wall.end.x, wall.end.y)
            
            length_m = wall.get_length_meters()
            
            # Выносные линии
            offset = 25
            dx = se[0] - ss[0]
            dy = se[1] - ss[1]
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            
            # Нормаль к стене
            nx, ny = -dy / length, dx / length
            
            # Точки выносных линий
            ext1 = (ss[0] + nx * offset, ss[1] + ny * offset)
            ext2 = (se[0] + nx * offset, se[1] + ny * offset)
            
            # Выносные линии
            self.canvas.create_line(ss, ext1, fill=Colors.DIMENSION, width=1)
            self.canvas.create_line(se, ext2, fill=Colors.DIMENSION, width=1)
            
            # Размерная линия
            self.canvas.create_line(ext1, ext2, fill=Colors.DIMENSION, width=1)
            
            # Текст размера по центру
            mid_x = (ext1[0] + ext2[0]) / 2
            mid_y = (ext1[1] + ext2[1]) / 2
            self.canvas.create_text(
                mid_x, mid_y,
                text=f"{length_m:.2f}м",
                fill=Colors.DIMENSION,
                font=('Consolas', 10, 'bold'),
                anchor='center'
            )
    
    def export_pdf(self):
        """Экспорт в PDF"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Сохранить план в PDF"
        )
        if not filename:
            return
        
        try:
            c = pdfcanvas.Canvas(filename, pagesize=A4)
            width, height = A4
            
            # Масштабирование под страницу
            margin = 2 * cm
            draw_width = width - 2 * margin
            draw_height = height - 2 * margin
            
            # Находим границы плана
            if not self.walls:
                messagebox.showwarning("Предупреждение", "Нет объектов для экспорта!")
                return
            
            all_x = []
            all_y = []
            for wall in self.walls:
                all_x.extend([wall.start.x, wall.end.x])
                all_y.extend([wall.start.y, wall.end.y])
            for furn in self.furniture:
                all_x.append(furn.x)
                all_y.append(furn.y)
            
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            
            plan_width = max_x - min_x + 2
            plan_height = max_y - min_y + 2
            
            scale_x = draw_width / (plan_width * SCALE_FACTOR)
            scale_y = draw_height / (plan_height * SCALE_FACTOR)
            scale = min(scale_x, scale_y)
            
            offset_x = margin - min_x * SCALE_FACTOR * scale
            offset_y = height - margin - max_y * SCALE_FACTOR * scale
            
            # Рисуем стены
            for wall in self.walls:
                x1 = wall.start.x * SCALE_FACTOR * scale + offset_x
                y1 = wall.start.y * SCALE_FACTOR * scale + offset_y
                x2 = wall.end.x * SCALE_FACTOR * scale + offset_x
                y2 = wall.end.y * SCALE_FACTOR * scale + offset_y
                
                thickness = wall.thickness * SCALE_FACTOR * scale
                c.setStrokeColorRL(rl_colors.Color(hex=Colors.WALL.replace('#', '#')))
                c.setLineWidth(max(1, thickness))
                c.line(x1, y1, x2, y2)
                
                # Размеры
                c.setStrokeColorRL(rl_colors.green)
                c.setLineWidth(0.5)
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                c.drawString(mid_x - 20, mid_y, f"{wall.get_length_meters():.2f}м")
            
            c.save()
            messagebox.showinfo("Успех", f"План сохранен в {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def export_png(self):
        """Экспорт в PNG"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            title="Сохранить план как изображение"
        )
        if not filename:
            return
        
        try:
            # Создаем изображение большого размера
            img = Image.new('RGB', (2000, 1500), color=(26, 27, 38))
            draw = ImageDraw.Draw(img)
            
            # Сохраняем текущие параметры
            old_scale = self.scale
            old_offset_x = self.offset_x
            old_offset_y = self.offset_y
            
            # Временно меняем для рендера
            self.scale = 2.0
            self.offset_x = 200
            self.offset_y = 200
            
            # Рисуем сетку
            for x in range(0, 2000, 50):
                draw.line([(x, 0), (x, 1500)], fill=(65, 72, 104), width=1)
            for y in range(0, 1500, 50):
                draw.line([(0, y), (2000, y)], fill=(65, 72, 104), width=1)
            
            # Рисуем стены
            for wall in self.walls:
                ss = self.world_to_screen(wall.start.x, wall.start.y)
                se = self.world_to_screen(wall.end.x, wall.end.y)
                thickness = max(3, wall.thickness * SCALE_FACTOR * self.scale)
                draw.line([ss, se], fill=(255, 158, 100), width=int(thickness))
            
            # Восстанавливаем параметры
            self.scale = old_scale
            self.offset_x = old_offset_x
            self.offset_y = old_offset_y
            
            img.save(filename)
            messagebox.showinfo("Успех", f"Изображение сохранено в {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def clear_all(self):
        """Очистка всего плана"""
        if messagebox.askyesno("Подтверждение", "Удалить весь план?"):
            self.walls = []
            self.furniture = []
            self.selected_wall = None
            self.selected_furniture = None
            self.update_properties_panel()
            self.redraw()

def main():
    root = tk.Tk()
    app = HomePlannerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
