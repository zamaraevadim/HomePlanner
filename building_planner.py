#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Программа «Простой планировщик зданий»
Позволяет создавать схематичный план этажа постройки с возможностью задать
габариты, материал стен и этажность. Результат отображается на экране и
экспортируется в PDF.

Требуется: pip install reportlab
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.colors import HexColor, white, black


# =============================================================================
# Константы
# =============================================================================

THICKNESS = 0.3  # Толщина стены в метрах
OFFSET_DIM = 1.0  # Отступ для размерных линий в метрах
CANVAS_WIDTH = 700  # Ширина холста в пикселях
CANVAS_HEIGHT = 500  # Высота холста в пикселях
DIM_OFFSET_PX = 30  # Отступ размерной линии от плана в пикселях

# Цвета материалов
MATERIAL_COLORS = {
    "Кирпич": "#B54B3D",
    "Дерево": "#8B5A2B",
    "Газобетон": "#B0B0B0",
    "Каркас": "#F5DEB3"
}

# Список материалов
MATERIALS_LIST = ["Кирпич", "Дерево", "Газобетон", "Каркас"]


# =============================================================================
# Класс модели здания
# =============================================================================

class BuildingPlan:
    """
    Класс хранит параметры здания: длину, ширину, этажность, материал и название.
    Предоставляет метод для получения цвета материала.
    """
    
    def __init__(self):
        self.length = 1.0  # Длина здания в метрах
        self.width = 1.0   # Ширина здания в метрах
        self.floors = 1    # Количество этажей (1, 2, 3)
        self.material = "Кирпич"  # Материал стен
        self.project_name = "Мой проект"  # Название проекта
    
    def get_material_color(self):
        """Возвращает цвет материала стен в формате HEX."""
        return MATERIAL_COLORS.get(self.material, "#B54B3D")
    
    def validate(self):
        """
        Проверяет корректность параметров.
        Возвращает кортеж (is_valid, error_message).
        """
        if self.length < 1.0:
            return False, "Длина здания должна быть не менее 1.0 м"
        if self.width < 1.0:
            return False, "Ширина здания должна быть не менее 1.0 м"
        if self.floors not in [1, 2, 3]:
            return False, "Количество этажей должно быть 1, 2 или 3"
        if self.material not in MATERIALS_LIST:
            return False, "Некорректный материал стен"
        return True, ""


# =============================================================================
# Рендерер для tkinter Canvas
# =============================================================================

class TkinterRenderer:
    """
    Класс для отрисовки плана этажа на tkinter Canvas.
    """
    
    def __init__(self, canvas_widget):
        self.canvas = canvas_widget
    
    def clear(self):
        """Очищает холст."""
        self.canvas.delete("all")
    
    def draw_plan(self, building: BuildingPlan, current_floor: int):
        """
        Отрисовывает план этажа на холсте.
        
        :param building: Объект BuildingPlan с параметрами здания
        :param current_floor: Номер текущего этажа (1-based)
        """
        self.clear()
        
        L = building.length  # Длина в метрах
        W = building.width   # Ширина в метрах
        
        # Рассчитываем масштаб так, чтобы план поместился на холсте
        # Учитываем отступы для размерных линий (примерно 1 м в каждую сторону)
        available_width = CANVAS_WIDTH - 2 * DIM_OFFSET_PX - 40  # 40 px запас
        available_height = CANVAS_HEIGHT - 2 * DIM_OFFSET_PX - 40
        
        # Подбираем масштаб: 1 метр = K пикселей
        scale_x = available_width / L if L > 0 else 1
        scale_y = available_height / W if W > 0 else 1
        M = min(scale_x, scale_y)  # Единый масштаб по обеим осям
        
        # Вычисляем размеры плана в пикселях
        plan_width_px = L * M
        plan_height_px = W * M
        
        # Центрируем план на холсте
        origin_x = (CANVAS_WIDTH - plan_width_px) / 2
        origin_y = (CANVAS_HEIGHT - plan_height_px) / 2 + DIM_OFFSET_PX
        
        # Координаты внешнего прямоугольника
        outer_x1 = origin_x
        outer_y1 = origin_y
        outer_x2 = origin_x + plan_width_px
        outer_y2 = origin_y + plan_height_px
        
        # Координаты внутреннего прямоугольника (с учётом толщины стен)
        thickness_px = THICKNESS * M
        inner_x1 = outer_x1 + thickness_px
        inner_y1 = outer_y1 + thickness_px
        inner_x2 = outer_x2 - thickness_px
        inner_y2 = outer_y2 - thickness_px
        
        # Получаем цвет материала
        wall_color = building.get_material_color()
        
        # 1. Заливаем внешний прямоугольник цветом материала
        self.canvas.create_rectangle(
            outer_x1, outer_y1, outer_x2, outer_y2,
            fill=wall_color, outline="black", width=2
        )
        
        # 2. Заливаем внутренний прямоугольник белым (пол)
        self.canvas.create_rectangle(
            inner_x1, inner_y1, inner_x2, inner_y2,
            fill="white", outline="black", width=2
        )
        
        # 3. Рисуем размерные линии
        dim_offset = DIM_OFFSET_PX  # Отступ в пикселях
        
        # Горизонтальная размерная линия (над планом)
        dim_line_y = outer_y1 - dim_offset
        self.canvas.create_line(outer_x1, dim_line_y, outer_x2, dim_line_y, fill="black", width=1)
        # Засечки на концах
        tick_size = 5
        self.canvas.create_line(outer_x1, dim_line_y - tick_size, outer_x1, dim_line_y + tick_size, fill="black", width=1)
        self.canvas.create_line(outer_x2, dim_line_y - tick_size, outer_x2, dim_line_y + tick_size, fill="black", width=1)
        # Текст размера
        length_text = f"Длина = {L:.2f} м"
        self.canvas.create_text(
            (outer_x1 + outer_x2) / 2, dim_line_y - 10,
            text=length_text, fill="black", font=("Arial", 12)
        )
        
        # Вертикальная размерная линия (слева от плана)
        dim_line_x = outer_x1 - dim_offset
        self.canvas.create_line(dim_line_x, outer_y1, dim_line_x, outer_y2, fill="black", width=1)
        # Засечки на концах
        self.canvas.create_line(dim_line_x - tick_size, outer_y1, dim_line_x + tick_size, outer_y1, fill="black", width=1)
        self.canvas.create_line(dim_line_x - tick_size, outer_y2, dim_line_x + tick_size, outer_y2, fill="black", width=1)
        # Текст размера (горизонтально, слева от линии)
        width_text = f"Ширина = {W:.2f} м"
        self.canvas.create_text(
            dim_line_x - 40, (outer_y1 + outer_y2) / 2,
            text=width_text, fill="black", font=("Arial", 12)
        )
        
        # 4. Текст номера этажа по центру плана
        center_x = (inner_x1 + inner_x2) / 2
        center_y = (inner_y1 + inner_y2) / 2
        floor_text = f"Этаж {current_floor}"
        self.canvas.create_text(
            center_x, center_y,
            text=floor_text, fill="#808080", font=("Arial", 16, "bold")
        )


# =============================================================================
# Рендерер для PDF (reportlab)
# =============================================================================

class PdfRenderer:
    """
    Класс для отрисовки плана этажа в PDF документе.
    Использует унифицированную геометрию с TkinterRenderer.
    """
    
    def __init__(self, pdf_canvas):
        self.canvas = pdf_canvas
    
    def draw_plan(self, building: BuildingPlan, current_floor: int, 
                  page_width: float, page_height: float, margins: float):
        """
        Отрисовывает план этажа на странице PDF.
        
        :param building: Объект BuildingPlan с параметрами здания
        :param current_floor: Номер текущего этажа (1-based)
        :param page_width: Ширина страницы в пунктах
        :param page_height: Высота страницы в пунктах
        :param margins: Поля страницы в пунктах
        """
        L = building.length  # Длина в метрах
        W = building.width   # Ширина в метрах
        
        # Полезная область страницы
        useful_width = page_width - 2 * margins
        useful_height = page_height - 2 * margins
        
        # Отступ под размерные линии (1 м в координатах плана)
        dim_offset_m = OFFSET_DIM
        
        # Рассчитываем масштаб: 1 метр = S пунктов
        scale_x = useful_width / (L + 2 * dim_offset_m) if L > 0 else 1
        scale_y = useful_height / (W + 2 * dim_offset_m) if W > 0 else 1
        S = min(scale_x, scale_y)
        
        # Размеры плана в пунктах
        plan_width_pt = L * S
        plan_height_pt = W * S
        
        # Начало координат с учётом полей и отступа для размеров
        origin_x = margins + dim_offset_m * S
        origin_y = margins + dim_offset_m * S
        
        # Координаты внешнего прямоугольника
        outer_x1 = origin_x
        outer_y1 = origin_y
        outer_x2 = origin_x + plan_width_pt
        outer_y2 = origin_y + plan_height_pt
        
        # Координаты внутреннего прямоугольника
        thickness_pt = THICKNESS * S
        inner_x1 = outer_x1 + thickness_pt
        inner_y1 = outer_y1 + thickness_pt
        inner_x2 = outer_x2 - thickness_pt
        inner_y2 = outer_y2 - thickness_pt
        
        # Получаем цвет материала
        wall_color = HexColor(building.get_material_color())
        
        # 1. Заливаем внешний прямоугольник цветом материала
        self.canvas.setFillColor(wall_color)
        self.canvas.setStrokeColor(black)
        self.canvas.setLineWidth(2)
        self.canvas.rect(outer_x1, outer_y1, outer_x2 - outer_x1, outer_y2 - outer_y1, fill=True, stroke=True)
        
        # 2. Заливаем внутренний прямоугольник белым (пол)
        self.canvas.setFillColor(white)
        self.canvas.setStrokeColor(black)
        self.canvas.rect(inner_x1, inner_y1, inner_x2 - inner_x1, inner_y2 - inner_y1, fill=True, stroke=True)
        
        # 3. Размерные линии
        dim_offset_pt = dim_offset_m * S  # Отступ в пунктах
        
        # Горизонтальная размерная линия (над планом)
        dim_line_y = outer_y1 - dim_offset_pt
        self.canvas.setStrokeColor(black)
        self.canvas.setLineWidth(1)
        self.canvas.line(outer_x1, dim_line_y, outer_x2, dim_line_y)
        # Засечки
        tick_size = 5
        self.canvas.line(outer_x1, dim_line_y - tick_size, outer_x1, dim_line_y + tick_size)
        self.canvas.line(outer_x2, dim_line_y - tick_size, outer_x2, dim_line_y + tick_size)
        # Текст
        length_text = f"Длина = {L:.2f} м"
        self.canvas.setFillColor(black)
        self.canvas.setFont("Helvetica-Bold", 12)
        text_width = self.canvas.stringWidth(length_text, "Helvetica-Bold", 12)
        self.canvas.drawString((outer_x1 + outer_x2) / 2 - text_width / 2, dim_line_y + 8, length_text)
        
        # Вертикальная размерная линия (слева от плана)
        dim_line_x = outer_x1 - dim_offset_pt
        self.canvas.line(dim_line_x, outer_y1, dim_line_x, outer_y2)
        # Засечки
        self.canvas.line(dim_line_x - tick_size, outer_y1, dim_line_x + tick_size, outer_y1)
        self.canvas.line(dim_line_x - tick_size, outer_y2, dim_line_x + tick_size, outer_y2)
        # Текст (повёрнутый на 90 градусов)
        width_text = f"Ширина = {W:.2f} м"
        self.canvas.saveState()
        self.canvas.translate(dim_line_x - 40, (outer_y1 + outer_y2) / 2)
        self.canvas.rotate(90)
        self.canvas.drawString(0, 0, width_text)
        self.canvas.restoreState()
        
        # 4. Текст номера этажа по центру плана
        center_x = (inner_x1 + inner_x2) / 2
        center_y = (inner_y1 + inner_y2) / 2
        floor_text = f"Этаж {current_floor}"
        self.canvas.setFillColor(HexColor("#808080"))
        self.canvas.setFont("Helvetica-Bold", 16)
        text_width = self.canvas.stringWidth(floor_text, "Helvetica-Bold", 16)
        self.canvas.drawString(center_x - text_width / 2, center_y - 6, floor_text)


# =============================================================================
# Основное приложение
# =============================================================================

class Application:
    """
    Основной класс приложения. Содержит все виджеты, обработчики событий
    и управляет состоянием программы.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("Простой планировщик зданий")
        self.root.resizable(False, False)
        
        # Модель данных
        self.building = BuildingPlan()
        
        # Текущий этаж для отображения
        self.current_floor = 1
        
        # Создаём интерфейс
        self._create_widgets()
        self._create_menu()
    
    def _create_menu(self):
        """Создаёт меню приложения."""
        menubar = tk.Menu(self.root)
        
        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Сохранить как PDF", command=self.export_to_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=file_menu)
        
        # Меню Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self._show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def _create_widgets(self):
        """Создаёт все виджеты интерфейса."""
        # Верхняя панель управления
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)
        
        # Создаём поля ввода в сетке
        row = 0
        col = 0
        
        # Длина здания
        ttk.Label(control_frame, text="Длина здания, м:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=5)
        col += 1
        self.length_var = tk.StringVar(value="8.5")
        self.length_entry = ttk.Entry(control_frame, textvariable=self.length_var, width=10)
        self.length_entry.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        
        # Ширина здания
        ttk.Label(control_frame, text="Ширина здания, м:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=5)
        col += 1
        self.width_var = tk.StringVar(value="6.0")
        self.width_entry = ttk.Entry(control_frame, textvariable=self.width_var, width=10)
        self.width_entry.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        
        # Количество этажей
        ttk.Label(control_frame, text="Количество этажей:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=5)
        col += 1
        self.floors_var = tk.StringVar(value="1")
        self.floors_combo = ttk.Combobox(control_frame, textvariable=self.floors_var, values=["1", "2", "3"], width=5, state="readonly")
        self.floors_combo.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        
        # Материал стен
        row += 1
        col = 0
        ttk.Label(control_frame, text="Материал стен:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=5)
        col += 1
        self.material_var = tk.StringVar(value="Кирпич")
        self.material_combo = ttk.Combobox(control_frame, textvariable=self.material_var, values=MATERIALS_LIST, width=15, state="readonly")
        self.material_combo.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        
        # Название проекта
        ttk.Label(control_frame, text="Название проекта:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=5)
        col += 1
        self.project_name_var = tk.StringVar(value="Мой проект")
        self.project_name_entry = ttk.Entry(control_frame, textvariable=self.project_name_var, width=20)
        self.project_name_entry.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        
        # Кнопка генерации
        row += 1
        col = 0
        self.generate_btn = ttk.Button(control_frame, text="Сгенерировать план", command=self.generate_plan)
        self.generate_btn.grid(row=row, column=col, columnspan=6, pady=10)
        
        # Панель навигации по этажам
        nav_frame = ttk.Frame(control_frame)
        nav_frame.grid(row=row + 1, column=0, columnspan=6, pady=5)
        
        self.prev_floor_btn = ttk.Button(nav_frame, text="◀ Предыдущий этаж", command=self.prev_floor)
        self.prev_floor_btn.pack(side=tk.LEFT, padx=5)
        
        self.floor_label = ttk.Label(nav_frame, text="Этаж 1 из 1")
        self.floor_label.pack(side=tk.LEFT, padx=10)
        
        self.next_floor_btn = ttk.Button(nav_frame, text="Следующий этаж ▶", command=self.next_floor)
        self.next_floor_btn.pack(side=tk.LEFT, padx=5)
        
        # Кнопка экспорта
        self.export_btn = ttk.Button(control_frame, text="Сохранить как PDF", command=self.export_to_pdf)
        self.export_btn.grid(row=row + 2, column=0, columnspan=6, pady=5)
        
        # Холст для предпросмотра
        self.canvas_frame = ttk.Frame(self.root, padding="10")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(
            self.canvas_frame, 
            width=CANVAS_WIDTH, 
            height=CANVAS_HEIGHT, 
            bg="white",
            highlightthickness=1,
            highlightbackground="#cccccc"
        )
        self.canvas.pack()
        
        # Инициализация рендерера
        self.renderer = TkinterRenderer(self.canvas)
        
        # Обновляем состояние кнопок навигации
        self._update_nav_buttons()
    
    def _update_nav_buttons(self):
        """Обновляет состояние кнопок навигации по этажам."""
        floors = self.building.floors
        if floors > 1:
            self.prev_floor_btn.config(state=tk.NORMAL if self.current_floor > 1 else tk.DISABLED)
            self.next_floor_btn.config(state=tk.NORMAL if self.current_floor < floors else tk.DISABLED)
            self.floor_label.config(text=f"Этаж {self.current_floor} из {floors}")
        else:
            self.prev_floor_btn.config(state=tk.DISABLED)
            self.next_floor_btn.config(state=tk.DISABLED)
            self.floor_label.config(text="Этаж 1 из 1")
    
    def _read_parameters(self):
        """
        Считывает параметры из полей ввода и обновляет модель.
        Возвращает кортеж (success, error_message).
        """
        try:
            self.building.length = float(self.length_var.get())
        except ValueError:
            return False, "Длина должна быть числом"
        
        try:
            self.building.width = float(self.width_var.get())
        except ValueError:
            return False, "Ширина должна быть числом"
        
        try:
            self.building.floors = int(self.floors_var.get())
        except ValueError:
            return False, "Количество этажей должно быть числом"
        
        self.building.material = self.material_var.get()
        self.building.project_name = self.project_name_var.get()
        
        # Валидация
        is_valid, error_msg = self.building.validate()
        if not is_valid:
            return False, error_msg
        
        return True, ""
    
    def generate_plan(self):
        """Генерирует план этажа на основе введённых параметров."""
        success, error_msg = self._read_parameters()
        if not success:
            messagebox.showerror("Ошибка ввода", error_msg)
            return
        
        # Сбрасываем на первый этаж
        self.current_floor = 1
        self._update_nav_buttons()
        
        # Отрисовываем план
        self.renderer.draw_plan(self.building, self.current_floor)
    
    def prev_floor(self):
        """Переключает на предыдущий этаж."""
        if self.current_floor > 1:
            self.current_floor -= 1
            self._update_nav_buttons()
            self.renderer.draw_plan(self.building, self.current_floor)
    
    def next_floor(self):
        """Переключает на следующий этаж."""
        if self.current_floor < self.building.floors:
            self.current_floor += 1
            self._update_nav_buttons()
            self.renderer.draw_plan(self.building, self.current_floor)
    
    def export_to_pdf(self):
        """Экспортирует проект в PDF файл."""
        # Сначала считываем и валидируем параметры
        success, error_msg = self._read_parameters()
        if not success:
            messagebox.showerror("Ошибка ввода", error_msg)
            return
        
        # Диалог сохранения файла
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF файлы", "*.pdf"), ("Все файлы", "*.*")],
            title="Сохранить проект как PDF"
        )
        
        if not filename:
            return  # Пользователь отменил
        
        try:
            # Создаём PDF документ
            c = pdfcanvas.Canvas(filename, pagesize=A4)
            page_width, page_height = A4
            margins = 50  # Поля в пунктах
            
            pdf_renderer = PdfRenderer(c)
            
            # Титульная страница
            c.setFont("Helvetica-Bold", 24)
            title = self.building.project_name
            title_width = c.stringWidth(title, "Helvetica-Bold", 24)
            c.drawString((page_width - title_width) / 2, page_height - 100, title)
            
            # Таблица параметров
            c.setFont("Helvetica", 12)
            y_pos = page_height - 150
            
            params = [
                ("Длина:", f"{self.building.length:.2f} м"),
                ("Ширина:", f"{self.building.width:.2f} м"),
                ("Этажность:", str(self.building.floors)),
                ("Материал:", self.building.material),
            ]
            
            for label, value in params:
                c.drawString(margins, y_pos, label)
                c.drawString(margins + 150, y_pos, value)
                y_pos -= 25
            
            c.showPage()  # Завершаем титульную страницу
            
            # Страницы с планами этажей
            for floor in range(1, self.building.floors + 1):
                # Заголовок страницы
                c.setFont("Helvetica-Bold", 16)
                header = f"План этажа {floor}"
                header_width = c.stringWidth(header, "Helvetica-Bold", 16)
                c.drawString((page_width - header_width) / 2, page_height - 50, header)
                
                # Отрисовка плана
                pdf_renderer.draw_plan(self.building, floor, page_width, page_height, margins)
                
                if floor < self.building.floors:
                    c.showPage()  # Новая страница для следующего этажа
            
            # Сохраняем документ
            c.save()
            
            messagebox.showinfo("Успех", f"Проект успешно сохранён в файл:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Не удалось сохранить PDF:\n{str(e)}")
    
    def _show_about(self):
        """Показывает диалог 'О программе'."""
        messagebox.showinfo(
            "О программе",
            "Простой планировщик зданий\n\n"
            "Версия 1.0\n\n"
            "Программа позволяет создавать схематичные планы этажей зданий "
            "с возможностью экспорта в PDF."
        )


# =============================================================================
# Точка входа
# =============================================================================

def main():
    """Точка входа в приложение."""
    root = tk.Tk()
    app = Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
