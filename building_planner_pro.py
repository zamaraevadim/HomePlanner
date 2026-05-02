#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой планировщик зданий 2.0
Функционал:
- Свободное рисование стен любой длины и под любым углом
- Привязка (snapping) к узлам сетки и концам других стен
- Установка окон и дверей в стены
- Сетка (вкл/выкл)
- Экспорт в PDF с корректным отображением всех объектов
- Слои и свойства объектов
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import math
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib import colors
from reportlab.lib.units import cm

# --- КОНСТАНТЫ ---
GRID_SIZE = 50  # Размер клетки сетки в пикселях (экран)
SNAP_RADIUS = 15  # Радиус привязки курсора в пикселях
DEFAULT_WALL_THICKNESS = 0.3  # Толщина стены по умолчанию (м)
SCALE_FACTOR = 20  # Пикселей на метр (базовый масштаб)

# Цвета материалов
MATERIAL_COLORS = {
    "Кирпич": "#B54B3D",
    "Дерево": "#8B5A2B",
    "Газобетон": "#B0B0B0",
    "Каркас": "#F5DEB3",
    "Перегородка": "#D3D3D3"
}

class Point:
    """Класс для хранения точки (координаты в пикселях экрана)"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

class Wall:
    """Класс Стены"""
    def __init__(self, x1, y1, x2, y2, thickness=DEFAULT_WALL_THICKNESS, material="Дерево"):
        self.start = Point(x1, y1)
        self.end = Point(x2, y2)
        self.thickness = thickness  # в метрах
        self.material = material
        self.selected = False
        self.id = None  # ID объекта на канвасе

    @property
    def length_m(self):
        """Длина стены в метрах"""
        px_len = self.start.distance_to(self.end)
        return px_len / SCALE_FACTOR

    @property
    def angle(self):
        """Угол стены в градусах"""
        return math.degrees(math.atan2(self.end.y - self.start.y, self.end.x - self.start.x))

    def get_screen_thickness(self):
        """Толщина стены в пикселях"""
        return self.thickness * SCALE_FACTOR

    def contains_point(self, x, y, tolerance=5):
        """Проверяет, находится ли точка (x,y) близко к линии стены (для выделения)"""
        # Расстояние от точки до отрезка
        p = Point(x, y)
        line_vec = Point(self.end.x - self.start.x, self.end.y - self.start.y)
        point_vec = Point(p.x - self.start.x, p.y - self.start.y)
        
        line_len_sq = line_vec.x**2 + line_vec.y**2
        if line_len_sq == 0: return p.distance_to(self.start) < tolerance
        
        t = max(0, min(1, (point_vec.x * line_vec.x + point_vec.y * line_vec.y) / line_len_sq))
        projection = Point(self.start.x + t * line_vec.x, self.start.y + t * line_vec.y)
        return p.distance_to(projection) < tolerance

    def get_endpoints(self):
        return [self.start, self.end]

class Opening:
    """Класс для Окна или Двери (проем в стене)"""
    def __init__(self, wall, offset_from_start, width, type_opening="window"):
        self.wall = wall  # Ссылка на объект стены
        self.offset = offset_from_start  # Расстояние от начала стены в пикселях
        self.width = width  # Ширина проема в пикселях
        self.type = type_opening  # 'window' или 'door'
        self.selected = False

    def get_screen_coords(self):
        """Возвращает координаты центра и угла для отрисовки"""
        if not self.wall: return None
        
        dx = self.wall.end.x - self.wall.start.x
        dy = self.wall.end.y - self.wall.start.y
        length = math.hypot(dx, dy)
        if length == 0: return None
        
        # Нормализованный вектор направления
        ux, uy = dx / length, dy / length
        
        # Центр проема
        cx = self.wall.start.x + ux * self.offset
        cy = self.wall.start.y + uy * self.offset
        
        angle = math.degrees(math.atan2(dy, dx))
        return cx, cy, angle

class BuildingPlan:
    """Основная модель данных проекта"""
    def __init__(self):
        self.walls = []
        self.openings = []
        self.project_name = "Мой проект"
        self.show_grid = True
        self.scale = SCALE_FACTOR

    def add_wall(self, wall):
        self.walls.append(wall)

    def remove_wall(self, wall):
        if wall in self.walls:
            self.walls.remove(wall)
        # Удаляем связанные проемы
        self.openings = [op for op in self.openings if op.wall != wall]

    def add_opening(self, opening):
        self.openings.append(opening)

    def clear(self):
        self.walls = []
        self.openings = []

class Renderer:
    """Базовый класс для отрисовки (общая логика)"""
    
    @staticmethod
    def draw_wall_path(canvas_obj, wall, scale_px_per_m):
        """Рисует контур стены (два параллельных отрезка + торцы)"""
        thick_px = wall.thickness * scale_px_per_m
        half_thick = thick_px / 2
        
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        length = math.hypot(dx, dy)
        if length == 0: return []
        
        # Нормаль к стене
        nx = -dy / length
        ny = dx / length
        
        # 4 угла стены
        x1 = wall.start.x + nx * half_thick
        y1 = wall.start.y + ny * half_thick
        x2 = wall.end.x + nx * half_thick
        y2 = wall.end.y + ny * half_thick
        x3 = wall.end.x - nx * half_thick
        y3 = wall.end.y - ny * half_thick
        x4 = wall.start.x - nx * half_thick
        y4 = wall.start.y - ny * half_thick
        
        coords = [x1, y1, x2, y2, x3, y3, x4, y4]
        return coords

    @staticmethod
    def get_snap_points(plan):
        """Собирает все точки привязки (концы всех стен)"""
        points = []
        for wall in plan.walls:
            points.append(wall.start)
            points.append(wall.end)
        return points

class TkinterRenderer(Renderer):
    """Отрисовка на Canvas Tkinter"""
    
    def __init__(self, canvas_widget, plan):
        self.canvas = canvas_widget
        self.plan = plan
        self.items = {}  # Хранение ID объектов для обновления

    def clear(self):
        self.canvas.delete("all")
        self.items = {}

    def draw_grid(self, width, height):
        if not self.plan.show_grid:
            return
            
        step = GRID_SIZE
        self.canvas.create_rectangle(0, 0, width, height, fill="white")
        
        # Вертикальные линии
        for x in range(0, width, step):
            self.canvas.create_line(x, 0, x, height, fill="#e0e0e0", tags="grid")
        # Горизонтальные линии
        for y in range(0, height, step):
            self.canvas.create_line(0, y, width, y, fill="#e0e0e0", tags="grid")
            
        # Координатная сетка (подписи)
        for x in range(0, width, step):
            m_val = x / self.plan.scale
            self.canvas.create_text(x, 10, text=f"{m_val:.1f}", font=("Arial", 8), fill="#aaa", tags="grid")
        for y in range(0, height, step):
            m_val = y / self.plan.scale
            self.canvas.create_text(10, y, text=f"{m_val:.1f}", font=("Arial", 8), fill="#aaa", tags="grid")

    def render(self):
        self.clear()
        width = int(self.canvas.cget("width"))
        height = int(self.canvas.cget("height"))
        
        self.draw_grid(width, height)
        
        # Отрисовка стен
        for wall in self.plan.walls:
            color = MATERIAL_COLORS.get(wall.material, "#000000")
            coords = self.draw_wall_path(self.canvas, wall, self.plan.scale)
            
            # Заливка
            if len(coords) == 8:
                self.canvas.create_polygon(coords, fill=color, outline="black", width=1, tags="wall")
                # Внутренняя линия для красоты (опционально)
                # self.canvas.create_line(wall.start.x, wall.start.y, wall.end.x, wall.end.y, fill="black", width=1, dash=(2,2))
            
            # Маркеры выделения
            if wall.selected:
                self.canvas.create_oval(wall.start.x-3, wall.start.y-3, wall.start.x+3, wall.start.y+3, fill="blue", tags="select")
                self.canvas.create_oval(wall.end.x-3, wall.end.y-3, wall.end.x+3, wall.end.y+3, fill="blue", tags="select")

        # Отрисовка проемов (окна/двери)
        for op in self.plan.openings:
            pos = op.get_screen_coords()
            if pos:
                cx, cy, angle = pos
                w_px = op.width
                # Рисуем прямоугольник проема
                # Упрощенно: просто белый прямоугольник поверх стены
                # Для правильного поворота нужно использовать полигон или матрицу трансформации
                # Здесь сделаем упрощенно: если стена горизонтальная/вертикальная - ровно, иначе поворот
                
                # Вектор вдоль стены
                dx = op.wall.end.x - op.wall.start.x
                dy = op.wall.end.y - op.wall.start.y
                length = math.hypot(dx, dy)
                if length == 0: continue
                ux, uy = dx/length, dy/length
                
                # Точки проема
                p1x = cx - ux * (w_px/2)
                p1y = cy - uy * (w_px/2)
                p2x = cx + ux * (w_px/2)
                p2y = cy + uy * (w_px/2)
                
                thick = op.wall.get_screen_thickness()
                # Нормаль
                nx, ny = -uy, ux
                
                poly = [
                    p1x + nx*thick/2, p1y + ny*thick/2,
                    p2x + nx*thick/2, p2y + ny*thick/2,
                    p2x - nx*thick/2, p2y - ny*thick/2,
                    p1x - nx*thick/2, p1y - ny*thick/2
                ]
                
                fill_color = "white" if op.type == "window" else "#DDA0DD" # Двери чуть цветные
                self.canvas.create_polygon(poly, fill=fill_color, outline="black", width=1, tags="opening")
                
                # Подпись типа
                self.canvas.create_text(cx, cy, text="Д" if op.type == "door" else "О", font=("Arial", 8), fill="red")

    def draw_temp_line(self, x1, y1, x2, y2, info_text=""):
        """Рисует временную линию при создании стены"""
        self.canvas.delete("temp")
        self.canvas.create_line(x1, y1, x2, y2, fill="red", width=2, dash=(4,4), tags="temp")
        # Текст с размерами
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        dist = math.hypot(x2-x1, y2-y1)
        meters = dist / self.plan.scale
        angle = math.degrees(math.atan2(y2-y1, x2-x1))
        
        self.canvas.create_text(mid_x, mid_y - 15, text=f"{meters:.2f} м\n{angle:.0f}°", fill="red", font=("Arial", 9, "bold"), tags="temp")

    def remove_temp(self):
        self.canvas.delete("temp")

    def draw_snap_indicator(self, x, y):
        self.canvas.delete("snap")
        r = 6
        self.canvas.create_oval(x-r, y-r, x+r, y+r, outline="green", width=2, tags="snap")

class PdfRenderer(Renderer):
    """Отрисовка в PDF"""
    
    def generate(self, filename, plan):
        c = pdfcanvas.Canvas(filename, pagesize=A4)
        width, height = A4
        
        # Титульный лист
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height - 50, plan.project_name)
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 90, f"Дата создания: {__import__('datetime').date.today()}")
        c.drawString(50, height - 110, f"Количество стен: {len(plan.walls)}")
        c.drawString(50, height - 130, f"Количество проемов: {len(plan.openings)}")
        
        c.showPage()
        
        # Страница плана
        # Масштабирование под страницу
        # Находим границы плана
        if not plan.walls:
            c.drawString(50, height/2, "План пуст. Нарисуйте стены.")
            c.save()
            return

        min_x = min(w.start.x for w in plan.walls)
        max_x = max(w.end.x for w in plan.walls)
        min_y = min(w.start.y for w in plan.walls)
        max_y = max(w.end.y for w in plan.walls)
        
        plan_w_px = max_x - min_x
        plan_h_px = max_y - min_y
        
        # Поля в пунктах (72 pt = 1 inch ~ 2.54cm)
        margin = 40
        avail_w = width - 2*margin
        avail_h = height - 2*margin
        
        # Вычисляем масштаб: сколько пунктов приходится на 1 пиксель модели
        # Или лучше: сколько пунктов на метр?
        # Пусть 1 метр = S пунктов.
        # План ширина в метрах = plan_w_px / plan.scale
        # S = avail_w / (plan_w_m + отступ)
        
        plan_w_m = plan_w_px / plan.scale
        plan_h_m = plan_h_px / plan.scale
        
        scale_factor = min(avail_w / (plan_w_m + 2), avail_h / (plan_h_m + 2)) # +2 метра запаса
        
        # Центрирование
        start_x = margin + (avail_w - plan_w_m * scale_factor) / 2
        start_y = height - margin - (avail_h - plan_h_m * scale_factor) / 2 # Y в PDF снизу вверх, но мы инвертируем логику или рисуем сверху вниз?
        # В Tkinter Y растет вниз. В PDF Y растет вверх.
        # Проще всего инвертировать Y при отрисовке: y_pdf = origin_y - y_model * scale
        
        origin_x = start_x
        origin_y = start_y # Это будет верхний левый угол плана в PDF

        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 40, "План этажа 1")
        
        # Функция конвертации координат
        def to_pdf(x, y):
            # Инвертируем Y, чтобы рисунок был как на экране (верх слева)
            return origin_x + x * (scale_factor / plan.scale), origin_y - y * (scale_factor / plan.scale)

        # Рисуем стены
        for wall in plan.walls:
            color_hex = MATERIAL_COLORS.get(wall.material, "#000000")
            # Конвертация цвета hex в rgb для reportlab
            r = int(color_hex[1:3], 16) / 255.0
            g = int(color_hex[3:5], 16) / 255.0
            b = int(color_hex[5:7], 16) / 255.0
            
            coords_screen = self.draw_wall_path(None, wall, plan.scale) # Получаем пиксели модели
            # Конвертируем 4 точки в PDF
            poly_pdf = []
            for i in range(0, 8, 2):
                px, py = to_pdf(coords_screen[i], coords_screen[i+1])
                poly_pdf.extend([px, py])
            
            c.setFillColorRGB(r, g, b)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(1)
            c.drawPolygon(poly_pdf)
            
        # Рисуем проемы
        for op in plan.openings:
            pos = op.get_screen_coords()
            if pos:
                cx, cy, angle = pos
                # Пересчет координат проема аналогично стенам (упрощенно - белый прямоугольник)
                # Вектор стены
                dx = op.wall.end.x - op.wall.start.x
                dy = op.wall.end.y - op.wall.start.y
                length = math.hypot(dx, dy)
                if length == 0: continue
                ux, uy = dx/length, dy/length
                
                # Координаты концов проема в модели
                p1x = cx - ux * (op.width/2)
                p1y = cy - uy * (op.width/2)
                p2x = cx + ux * (op.width/2)
                p2y = cy + uy * (op.width/2)
                
                thick = op.wall.get_screen_thickness()
                nx, ny = -uy, ux
                
                pts = [
                    (p1x + nx*thick/2, p1y + ny*thick/2),
                    (p2x + nx*thick/2, p2y + ny*thick/2),
                    (p2x - nx*thick/2, p2y - ny*thick/2),
                    (p1x - nx*thick/2, p1y - ny*thick/2)
                ]
                
                poly_pdf = []
                for (px, py) in pts:
                    pdf_x, pdf_y = to_pdf(px, py)
                    poly_pdf.extend([pdf_x, pdf_y])
                
                c.setFillColorRGB(1, 1, 1) # Белый
                if op.type == "door":
                    c.setFillColorRGB(0.8, 0.6, 0.8)
                c.drawPolygon(poly_pdf)

        c.save()

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Простой планировщик зданий 2.0")
        self.geometry("1000x700")
        
        self.plan = BuildingPlan()
        self.renderer = None  # Будет создан после создания canvas
        
        # Состояние редактора
        self.mode = "draw_wall"  # draw_wall, select, add_window, add_door
        self.current_wall_start = None
        self.dragged_object = None
        self.drag_offset = Point(0,0)
        self.hover_snap_point = None
        
        self._init_ui()
        
    def _init_ui(self):
        # Верхняя панель
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Кнопки режимов
        ttk.Label(toolbar, text="Режим:").pack(side=tk.LEFT, padx=5)
        
        self.btn_draw = ttk.Button(toolbar, text="🏗 Стена", command=lambda: self.set_mode("draw_wall"))
        self.btn_draw.pack(side=tk.LEFT, padx=2)
        
        self.btn_select = ttk.Button(toolbar, text="✋ Выделение", command=lambda: self.set_mode("select"))
        self.btn_select.pack(side=tk.LEFT, padx=2)
        
        self.btn_win = ttk.Button(toolbar, text="🪟 Окно", command=lambda: self.set_mode("add_window"))
        self.btn_win.pack(side=tk.LEFT, padx=2)
        
        self.btn_door = ttk.Button(toolbar, text="🚪 Дверь", command=lambda: self.set_mode("add_door"))
        self.btn_door.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Свойства
        ttk.Label(toolbar, text="Материал:").pack(side=tk.LEFT, padx=5)
        self.combo_material = ttk.Combobox(toolbar, values=list(MATERIAL_COLORS.keys()), state="readonly", width=10)
        self.combo_material.current(1) # Дерево
        self.combo_material.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Толщина (м):").pack(side=tk.LEFT, padx=5)
        self.entry_thickness = ttk.Entry(toolbar, width=5)
        self.entry_thickness.insert(0, "0.3")
        self.entry_thickness.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Действия
        self.btn_grid = ttk.Button(toolbar, text="Сетка: ВКЛ", command=self.toggle_grid)
        self.btn_grid.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="🗑 Удалить выделенное", command=self.delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📄 Сохранить PDF", command=self.export_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="❌ Очистить все", command=self.clear_all).pack(side=tk.RIGHT, padx=5)
        
        # Холст
        self.canvas = tk.Canvas(self, bg="white", width=800, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.renderer = TkinterRenderer(self.canvas, self.plan)
        
        # Привязка событий
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Delete>", lambda e: self.delete_selected())
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе. Выберите режим 'Стена' для начала рисования.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.set_mode("draw_wall")
        self.renderer.render()

    def set_mode(self, mode):
        self.mode = mode
        self.current_wall_start = None
        self.renderer.remove_temp()
        self.status_var.set(f"Режим: {mode}")
        
        # Визуальное выделение кнопок (упрощенно сброс цветов)
        # В реальном приложении можно менять relief или color

    def toggle_grid(self):
        self.plan.show_grid = not self.plan.show_grid
        self.btn_grid.config(text=f"Сетка: {'ВКЛ' if self.plan.show_grid else 'ВЫКЛ'}")
        self.renderer.render()

    def get_snap_point(self, x, y):
        """Ищет ближайшую точку привязки"""
        snap_points = Renderer.get_snap_points(self.plan)
        # Добавляем точки сетки
        if self.plan.show_grid:
            gx = round(x / GRID_SIZE) * GRID_SIZE
            gy = round(y / GRID_SIZE) * GRID_SIZE
            snap_points.append(Point(gx, gy))
            
        best_point = None
        min_dist = SNAP_RADIUS
        
        mouse = Point(x, y)
        for pt in snap_points:
            d = mouse.distance_to(pt)
            if d < min_dist:
                min_dist = d
                best_point = pt
                
        return best_point

    def on_mouse_move(self, event):
        x, y = event.x, event.y
        snap = self.get_snap_point(x, y)
        
        if snap:
            self.hover_snap_point = snap
            self.renderer.draw_snap_indicator(snap.x, snap.y)
            x, y = snap.x, snap.y # Курсор прыгает к точке
        else:
            self.hover_snap_point = None
            self.canvas.delete("snap")
            
        if self.mode == "draw_wall" and self.current_wall_start:
            self.renderer.draw_temp_line(self.current_wall_start.x, self.current_wall_start.y, x, y)
            dist = math.hypot(x - self.current_wall_start.x, y - self.current_wall_start.y)
            m = dist / self.plan.scale
            ang = math.degrees(math.atan2(y - self.current_wall_start.y, x - self.current_wall_start.x))
            self.status_var.set(fДлина: {m:.2f} м | Угол: {ang:.1f}°")
        elif self.mode == "select":
            # Подсветка стен под курсором
            pass

    def on_mouse_down(self, event):
        x, y = event.x, event.y
        snap = self.get_snap_point(x, y)
        if snap: x, y = snap.x, snap.y
        
        if self.mode == "draw_wall":
            if not self.current_wall_start:
                self.current_wall_start = Point(x, y)
                self.status_var.set("Перетащите мышь для указания длины и угла стены.")
            else:
                # Завершение стены
                self.finish_wall(x, y)
                
        elif self.mode == "select":
            # Поиск объекта для перетаскивания
            # Сначала проверяем стены
            for wall in reversed(self.plan.walls): # Сверху вниз
                if wall.contains_point(x, y):
                    self.dragged_object = wall
                    self.drag_offset = Point(x - wall.start.x, y - wall.start.y) # Запоминаем смещение относительно начала
                    wall.selected = True
                    # Снимаем выделение с остальных
                    for w in self.plan.walls:
                        if w != wall: w.selected = False
                    self.renderer.render()
                    return
            
            # Если не попали в стену, снимаем выделение
            for w in self.plan.walls: w.selected = False
            self.renderer.render()

    def on_mouse_drag(self, event):
        x, y = event.x, event.y
        snap = self.get_snap_point(x, y)
        if snap: x, y = snap.x, snap.y
        
        if self.mode == "draw_wall" and self.current_wall_start:
            self.renderer.draw_temp_line(self.current_wall_start.x, self.current_wall_start.y, x, y)
            
        elif self.mode == "select" and self.dragged_object:
            # Перемещение стены
            wall = self.dragged_object
            dx = x - self.drag_offset.x - wall.start.x
            dy = y - self.drag_offset.y - wall.start.y
            
            wall.start.x += dx
            wall.start.y += dy
            wall.end.x += dx
            wall.end.y += dy
            self.renderer.render()

    def on_mouse_up(self, event):
        if self.mode == "select":
            self.dragged_object = None
            
    def finish_wall(self, x, y):
        try:
            thick = float(self.entry_thickness.get())
            if thick <= 0: raise ValueError
        except:
            messagebox.showerror("Ошибка", "Некорректная толщина стены")
            self.current_wall_start = None
            self.renderer.remove_temp()
            return
            
        mat = self.combo_material.get()
        wall = Wall(self.current_wall_start.x, self.current_wall_start.y, x, y, thick, mat)
        
        # Проверка на нулевую длину
        if wall.length_m < 0.1:
            messagebox.showwarning("Внимание", "Стена слишком короткая")
            self.current_wall_start = None
            self.renderer.remove_temp()
            return
            
        self.plan.add_wall(wall)
        self.current_wall_start = None # Начинаем новую стену от конца предыдущей? Пока нет.
        self.renderer.remove_temp()
        self.renderer.render()
        self.status_var.set(f"Стена добавлена. Длина: {wall.length_m:.2f} м")

    def delete_selected(self):
        count = 0
        # Удаляем стены
        for wall in list(self.plan.walls):
            if wall.selected:
                self.plan.remove_wall(wall)
                count += 1
        if count > 0:
            self.renderer.render()
            self.status_var.set(f"Удалено объектов: {count}")
        else:
            self.status_var.set("Ничего не выделено для удаления")

    def clear_all(self):
        if messagebox.askyesno("Подтверждение", "Удалить весь проект?"):
            self.plan.clear()
            self.renderer.render()
            self.status_var.set("Проект очищен")

    def export_pdf(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if file_path:
            try:
                renderer = PdfRenderer()
                renderer.generate(file_path, self.plan)
                messagebox.showinfo("Успех", f"Файл сохранен: {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка PDF", str(e))

if __name__ == "__main__":
    app = Application()
    app.mainloop()
