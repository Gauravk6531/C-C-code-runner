import os
import sys
import re
import shutil
import time
import subprocess
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QTextEdit, QPlainTextEdit,
    QLabel, QTabWidget, QSplitter, QLineEdit, QStatusBar, QFrame,
    QStyle, QInputDialog, QMessageBox, QStackedWidget, QCheckBox,
    QTreeView, QFileSystemModel, QDialog, QFormLayout, QComboBox,
    QSlider, QDialogButtonBox, QMenu
)
from PySide6.QtCore import QProcess, Qt, QSize, QTimer, QFileSystemWatcher, QRegularExpression, QRect, QPoint
from PySide6.QtGui import (
    QFont, QIcon, QKeySequence, QShortcut, QTextCursor, QColor,
    QPainter, QTextFormat, QFontMetrics, QSyntaxHighlighter, QTextCharFormat, QTextDocument,
    QPixmap
)

# ==============================================================================
# 1. C/C++ Syntax Highlighter (Adaptive Light/Dark Themes)
# ==============================================================================
class CppSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setup_rules()
        
    def setup_rules(self):
        self.highlighting_rules = []
        
        # Select visual theme colors
        c_keyword = "#569cd6" if self.is_dark else "#0933e1"
        c_type = "#4ec9b0" if self.is_dark else "#037a72"
        c_prep = "#c586c0" if self.is_dark else "#a100a1"
        c_comment = "#6a9955" if self.is_dark else "#008000"
        c_string = "#ce9178" if self.is_dark else "#a31515"
        c_number = "#b5cea8" if self.is_dark else "#098658"
        c_function = "#dcdcaa" if self.is_dark else "#795e26"
        c_operator = "#d4d4d4" if self.is_dark else "#3b3b3b"
        
        # Color formats
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(c_keyword))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = [
            "char", "class", "const", "double", "enum", "explicit", "export",
            "extern", "float", "inline", "int", "long", "operator", "private",
            "protected", "public", "short", "signals", "signed", "slots",
            "static", "struct", "template", "typedef", "typename", "union",
            "unsigned", "virtual", "bool", "using", "namespace",
            "break", "case", "catch", "continue", "default", "do", "else", "for",
            "goto", "if", "new", "return", "switch", "this", "throw", "try", "while",
            "delete", "sizeof"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, keyword_format))

        # Types and STL elements
        type_format = QTextCharFormat()
        type_format.setForeground(QColor(c_type))
        types = ["std", "string", "vector", "map", "set", "cout", "cin", "endl", "printf", "scanf", "iostream"]
        for t in types:
            pattern = QRegularExpression(rf"\b{t}\b")
            self.highlighting_rules.append((pattern, type_format))

        # Function formatting
        function_format = QTextCharFormat()
        function_format.setForeground(QColor(c_function))
        self.highlighting_rules.append((QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()"), function_format))

        # Operator formatting
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor(c_operator))
        operators = ["+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">=", "&&", "||", "&", "|", "!", "%"]
        for op in operators:
            pattern = QRegularExpression(QRegularExpression.escape(op))
            self.highlighting_rules.append((pattern, operator_format))

        # Preprocessor format
        preprocessor_format = QTextCharFormat()
        preprocessor_format.setForeground(QColor(c_prep))
        self.highlighting_rules.append((QRegularExpression(r"#[a-zA-Z]+"), preprocessor_format))

        # Single line comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(c_comment))
        self.highlighting_rules.append((QRegularExpression(r"//[^\n]*"), comment_format))

        # Multi-line comments format
        self.multi_line_comment_format = QTextCharFormat()
        self.multi_line_comment_format.setForeground(QColor(c_comment))

        # String literals
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(c_string))
        self.highlighting_rules.append((QRegularExpression(r"\".*?\""), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'.*?'"), string_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(c_number))
        self.highlighting_rules.append((QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), number_format))

    def update_theme(self, is_dark):
        self.is_dark = is_dark
        self.setup_rules()
        self.rehighlight()

    def highlightBlock(self, text):
        # Apply standard single-line rules
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

        # Handle multi-line comments /* ... */
        self.setCurrentBlockState(0)
        start_expression = QRegularExpression(r"/\*")
        end_expression = QRegularExpression(r"\*/")

        start_index = 0
        if self.previousBlockState() != 1:
            start_match = start_expression.match(text)
            start_index = start_match.capturedStart() if start_match.hasMatch() else -1
        
        while start_index >= 0:
            end_match = end_expression.match(text, start_index)
            end_index = end_match.capturedStart() if end_match.hasMatch() else -1
            comment_length = 0
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + end_match.capturedLength()
            
            self.setFormat(start_index, comment_length, self.multi_line_comment_format)
            start_match = start_expression.match(text, start_index + comment_length)
            start_index = start_match.capturedStart() if start_match.hasMatch() else -1


# ==============================================================================
# 2. IntelliSense Autocomplete Popover List Widget
# ==============================================================================
class AutocompletePopup(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("autocompletePopup")
        self.setStyleSheet("""
            QListWidget#autocompletePopup {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
            QListWidget#autocompletePopup::item {
                padding: 4px 8px;
            }
            QListWidget#autocompletePopup::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget#autocompletePopup::item:selected {
                background-color: #094771;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        self.hide()


# ==============================================================================
# 3. Line Number Gutter Area Widget
# ==============================================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


# ==============================================================================
# 4. Minimap Code Preview Widget
# ==============================================================================
class Minimap(QPlainTextEdit):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # Hide scrollbars completely
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Disable cursor focus and interaction
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        # Extremely small font
        font = QFont("Consolas", 2)
        font.setFixedPitch(True)
        self.setFont(font)
        
        self.setStyleSheet("background-color: #1a1a1a; border: none; border-left: 1px solid #2d2d2d;")


# ==============================================================================
# 4a. C/C++ Custom Vector Badge File System Model
# ==============================================================================
class CppFileExplorerModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.icon_cache = {}
        
    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.icon_cache.clear()
        
    def data(self, index, role=Qt.ItemDataRole.DecorationRole):
        if role == Qt.ItemDataRole.DecorationRole:
            if self.isDir(index):
                return self.get_folder_icon()
            
            filepath = self.filePath(index)
            ext = os.path.splitext(filepath)[1].lower()
            if ext == '.c':
                return self.get_c_icon()
            elif ext in ['.cpp', '.cc', '.cxx']:
                return self.get_cpp_icon()
            elif ext in ['.h', '.hpp']:
                return self.get_h_icon()
            elif ext in ['.txt', '.md']:
                return self.get_txt_icon()
            else:
                return self.get_generic_icon()
                
        return super().data(index, role)
        
    def get_c_icon(self):
        if 'c' not in self.icon_cache:
            self.icon_cache['c'] = self.create_badge_icon("#e76f51", "C")
        return self.icon_cache['c']
        
    def get_cpp_icon(self):
        if 'cpp' not in self.icon_cache:
            self.icon_cache['cpp'] = self.create_badge_icon("#264653", "C+")
        return self.icon_cache['cpp']
        
    def get_h_icon(self):
        if 'h' not in self.icon_cache:
            self.icon_cache['h'] = self.create_badge_icon("#2a9d8f", "H")
        return self.icon_cache['h']
        
    def get_txt_icon(self):
        if 'txt' not in self.icon_cache:
            self.icon_cache['txt'] = self.create_badge_icon("#4a4e69", "T")
        return self.icon_cache['txt']
        
    def get_generic_icon(self):
        if 'generic' not in self.icon_cache:
            self.icon_cache['generic'] = self.create_badge_icon("#6c757d", "•")
        return self.icon_cache['generic']
        
    def get_folder_icon(self):
        if 'folder' not in self.icon_cache:
            self.icon_cache['folder'] = self.create_badge_icon("#f4a261", "F")
        return self.icon_cache['folder']
        
    def create_badge_icon(self, color_hex, text):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw rounded rectangle background
        painter.setBrush(QColor(color_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 16, 16, 3, 3)
        
        # Draw text inside
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return QIcon(pixmap)


# ==============================================================================
# 4b. Custom IDE Settings Configuration Dialog Widget
# ==============================================================================
class SettingsDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setWindowTitle("coderun Settings")
        self.setMinimumWidth(380)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Consistent professional style
        is_dark = self.main_app.theme_is_dark
        bg_color = "#252526" if is_dark else "#f3f3f3"
        text_color = "#d4d4d4" if is_dark else "#333333"
        input_bg = "#3c3c3c" if is_dark else "#ffffff"
        input_border = "#3c3c3c" if is_dark else "#cccccc"
        btn_bg = "#3c3c3c" if is_dark else "#e1e1e1"
        btn_hover = "#4c4c4c" if is_dark else "#d1d1d1"
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg_color}; color: {text_color}; }}
            QLabel {{ color: {text_color}; font-size: 12px; }}
            QComboBox {{ background-color: {input_bg}; border: 1px solid {input_border}; padding: 4px; color: {text_color}; border-radius: 3px; }}
            QSlider::groove:horizontal {{ border: 1px solid {input_border}; height: 6px; background: {input_bg}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: #007acc; width: 14px; margin: -4px 0; border-radius: 7px; }}
            QCheckBox {{ color: {text_color}; }}
            QPushButton {{ background-color: {btn_bg}; border: 1px solid {input_border}; color: {text_color}; padding: 5px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
        """)
        
        # 1. Font Family
        self.font_combo = QComboBox()
        self.font_combo.addItems(["JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "Segoe UI"])
        self.font_combo.setCurrentText(self.main_app.settings.get("font_family", "JetBrains Mono"))
        layout.addRow("Font Family:", self.font_combo)
        
        # 2. Font Size
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(8, 30)
        self.size_slider.setValue(self.main_app.settings.get("font_size", 14))
        self.size_label = QLabel(str(self.size_slider.value()) + "px")
        self.size_slider.valueChanged.connect(lambda val: self.size_label.setText(str(val) + "px"))
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.size_slider)
        size_layout.addWidget(self.size_label)
        layout.addRow("Font Size:", size_layout)
        
        # 3. Line Height
        self.line_height_combo = QComboBox()
        self.line_height_combo.addItems(["1.0", "1.2", "1.4", "1.5", "1.8", "2.0"])
        self.line_height_combo.setCurrentText(str(self.main_app.settings.get("line_height", 1.4)))
        layout.addRow("Line Height:", self.line_height_combo)
        
        # 4. Tab Size
        self.tab_size_combo = QComboBox()
        self.tab_size_combo.addItems(["2", "4", "8"])
        self.tab_size_combo.setCurrentText(str(self.main_app.settings.get("tab_size", 4)))
        layout.addRow("Tab Size (spaces):", self.tab_size_combo)
        
        # 5. Word Wrap
        self.wrap_box = QCheckBox()
        self.wrap_box.setChecked(self.main_app.settings.get("word_wrap", False))
        layout.addRow("Word Wrap:", self.wrap_box)
        
        # 6. Ligatures
        self.ligature_box = QCheckBox()
        self.ligature_box.setChecked(self.main_app.settings.get("ligatures", True))
        layout.addRow("Enable Ligatures:", self.ligature_box)
        
        # 7. Auto Save
        self.autosave_box = QCheckBox()
        self.autosave_box.setChecked(self.main_app.settings.get("auto_save", False))
        layout.addRow("Auto Save:", self.autosave_box)
        
        # 8. Terminal Font Size
        self.terminal_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.terminal_size_slider.setRange(8, 24)
        self.terminal_size_slider.setValue(self.main_app.settings.get("terminal_font_size", 12))
        self.terminal_size_label = QLabel(str(self.terminal_size_slider.value()) + "px")
        self.terminal_size_slider.valueChanged.connect(lambda val: self.terminal_size_label.setText(str(val) + "px"))
        
        term_layout = QHBoxLayout()
        term_layout.addWidget(self.terminal_size_slider)
        term_layout.addWidget(self.terminal_size_label)
        layout.addRow("Terminal Font Size:", term_layout)
        
        # OK / Cancel Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def save_settings(self):
        self.main_app.settings["font_family"] = self.font_combo.currentText()
        self.main_app.settings["font_size"] = self.size_slider.value()
        self.main_app.settings["line_height"] = float(self.line_height_combo.currentText())
        self.main_app.settings["tab_size"] = int(self.tab_size_combo.currentText())
        self.main_app.settings["word_wrap"] = self.wrap_box.isChecked()
        self.main_app.settings["ligatures"] = self.ligature_box.isChecked()
        self.main_app.settings["auto_save"] = self.autosave_box.isChecked()
        self.main_app.settings["terminal_font_size"] = self.terminal_size_slider.value()
        
        self.main_app.save_settings_to_file()
        self.main_app.apply_loaded_settings()
        self.accept()


# ==============================================================================
# 5. Custom VS Code-like Code Editor
# ==============================================================================
class CodeEditor(QPlainTextEdit):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.filepath = None
        self.is_dirty = False
        self.line_number_area = LineNumberArea(self)
        
        # Connect signals for gutter drawing and brace highlighting
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_editor_effects)
        
        self.update_line_number_area_width(0)
        self.setup_editor()

        # Initialize Autocomplete Popup
        self.autocomplete_popup = AutocompletePopup(self)
        self.autocomplete_popup.itemDoubleClicked.connect(self.insert_completion)

        # Smart Quote / Auto pair state machine tracking
        self.last_auto_inserted_closing_pos = -1
        self.last_auto_inserted_char = ''

    def setup_editor(self):
        # Configure plain text editor settings
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas", 11)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Custom tab stop distance (4 spaces)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(' ') * 4)

    def zoom_in(self):
        font = self.font()
        size = font.pointSize()
        if size < 40:
            font.setPointSize(size + 1)
            self.setFont(font)
            self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(' ') * self.main_app.settings.get("tab_size", 4))
            self.update_line_number_area_width(0)
            
    def zoom_out(self):
        font = self.font()
        size = font.pointSize()
        if size > 6:
            font.setPointSize(size - 1)
            self.setFont(font)
            self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(' ') * self.main_app.settings.get("tab_size", 4))
            self.update_line_number_area_width(0)

    def reset_zoom(self):
        font = self.font()
        font.setPointSize(self.main_app.settings.get("font_size", 14))
        self.setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(' ') * self.main_app.settings.get("tab_size", 4))
        self.update_line_number_area_width(0)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def line_number_area_width(self):
        digits = 1
        max_blocks = max(1, self.blockCount())
        while max_blocks >= 10:
            max_blocks /= 10
            digits += 1
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
        self.update_autocomplete_popup_position()

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        is_dark = self.main_app.theme_is_dark
        gutter_bg = QColor("#1e1e1e") if is_dark else QColor("#f3f3f3")
        painter.fillRect(event.rect(), gutter_bg)

        active_block = self.textCursor().block().blockNumber()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                # Highlight active line number in high-contrast cyan or bold gray
                if block_number == active_block:
                    painter.setPen(QColor("#00ffcc") if is_dark else QColor("#007acc"))
                    font = painter.font()
                    font.setBold(True)
                    painter.setFont(font)
                else:
                    painter.setPen(QColor("#858585"))
                    font = painter.font()
                    font.setBold(False)
                    painter.setFont(font)
                    
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_editor_effects(self):
        """Combines current line highlighting and brace matching overlays."""
        extra_selections = []
        
        # 1. Highlight active editing line
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#282828") if self.main_app.theme_is_dark else QColor("#f2f2f2")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
            
        self.setExtraSelections(extra_selections)
        
        # 2. Highlight matching parenthesis/braces
        self.highlight_matching_braces()

    def highlight_matching_braces(self):
        """Looks for adjacent bracket markers and highlights their matching pairs, or flags errors."""
        extra_selections = self.extraSelections()
        cursor = self.textCursor()
        pos = cursor.position()
        doc = self.document()
        
        char_left = doc.characterAt(pos - 1)
        char_right = doc.characterAt(pos)
        
        pairs = {
            '(': ')', '[': ']', '{': '}', '<': '>',
            ')': '(', ']': '[', '}': '{', '>': '<'
        }
        
        target_pos = -1
        current_char = ''
        search_pos = -1
        
        if char_left in pairs:
            current_char = char_left
            search_pos = pos - 1
        elif char_right in pairs:
            current_char = char_right
            search_pos = pos
            
        if current_char:
            match_char = pairs[current_char]
            direction = 1 if current_char in ['(', '[', '{', '<'] else -1
            
            # Find matching bracket position
            depth = 1
            idx = search_pos + direction
            doc_len = doc.characterCount()
            
            while 0 <= idx < doc_len:
                c = doc.characterAt(idx)
                if c == current_char:
                    depth += 1
                elif c == match_char:
                    depth -= 1
                    if depth == 0:
                        target_pos = idx
                        break
                idx += direction
                
            if target_pos != -1:
                # Format for matching braces
                match_format = QTextCharFormat()
                match_format.setBackground(QColor("#3e3e3e") if self.main_app.theme_is_dark else QColor("#e4e4e4"))
                match_format.setForeground(QColor("#00ffcc") if self.main_app.theme_is_dark else QColor("#007acc"))
                match_format.setFontWeight(QFont.Weight.Bold)
                
                # Selection 1 (Current Brace)
                sel1 = QTextEdit.ExtraSelection()
                sel1.format = match_format
                sel1.cursor = self.textCursor()
                sel1.cursor.setPosition(search_pos)
                sel1.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                
                # Selection 2 (Matching Brace)
                sel2 = QTextEdit.ExtraSelection()
                sel2.format = match_format
                sel2.cursor = self.textCursor()
                sel2.cursor.setPosition(target_pos)
                sel2.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                
                extra_selections.append(sel1)
                extra_selections.append(sel2)
            else:
                # Unmatched opening brace: visual red spellcheck underline error
                err_format = QTextCharFormat()
                err_format.setBackground(QColor("#5a1d1d") if self.main_app.theme_is_dark else QColor("#ffd2d2"))
                err_format.setUnderlineColor(QColor("#be2e13"))
                err_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
                
                sel = QTextEdit.ExtraSelection()
                sel.format = err_format
                sel.cursor = self.textCursor()
                sel.cursor.setPosition(search_pos)
                sel.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                extra_selections.append(sel)
                
        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        """Intercepts keyboard inputs to emulate professional coding gestures with perfect caret synchronization."""
        cursor = self.textCursor()
        key = event.key()
        text = event.text()

        # 1. Handle Autocomplete popup keyboard overrides
        if self.autocomplete_popup.isVisible():
            if key == Qt.Key.Key_Escape:
                self.autocomplete_popup.hide()
                event.accept()
                return
            elif key in [Qt.Key.Key_Down, Qt.Key.Key_Up]:
                self.autocomplete_popup.keyPressEvent(event)
                event.accept()
                return
            elif key in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab]:
                self.insert_completion()
                event.accept()
                return

        # Query text of current block without moving cursor side-effects
        block = cursor.block()
        line_text = block.text()
        pos_in_block = cursor.positionInBlock()
        line_prefix = line_text[:pos_in_block]
        line_suffix = line_text[pos_in_block:]

        # 2. Smart Pair Deletion on BACKSPACE
        if key == Qt.Key.Key_Backspace:
            current_pos = cursor.position()
            if current_pos == self.last_auto_inserted_closing_pos:
                char_left = line_prefix[-1] if line_prefix else ""
                char_right = line_suffix[0] if line_suffix else ""
                pairs = {
                    '(': ')', '[': ']', '{': '}', '<': '>', '"': '"', "'": "'"
                }
                if char_left == self.last_auto_inserted_char and char_right == pairs.get(char_left):
                    cursor.beginEditBlock()
                    cursor.deleteChar()          # Deletes right pair character
                    cursor.deletePreviousChar()  # Deletes left pair character
                    cursor.endEditBlock()
                    self.last_auto_inserted_closing_pos = -1
                    self.last_auto_inserted_char = ''
                    event.accept()
                    return
            
            # Reset state on standard backspace
            self.last_auto_inserted_closing_pos = -1
            self.last_auto_inserted_char = ''

            # Indentation-Aware backspacing: delete 4 spaces if line prefix consists entirely of spaces
            if line_prefix and all(c == ' ' for c in line_prefix) and len(line_prefix) >= 4 and len(line_prefix) % 4 == 0:
                cursor.beginEditBlock()
                for _ in range(4):
                    cursor.deletePreviousChar()
                cursor.endEditBlock()
                event.accept()
                return

        # Reset state on other text modifications
        if text:
            self.last_auto_inserted_closing_pos = -1
            self.last_auto_inserted_char = ''

        # 3. Smart Pair Skipping
        if text in [')', ']', '}', '>', '"', "'"]:
            if line_suffix and line_suffix.startswith(text):
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
                self.setTextCursor(cursor)
                self.last_auto_inserted_closing_pos = -1
                self.last_auto_inserted_char = ''
                event.accept()
                return

        # 4. Auto Pair Creation
        opening_pairs = {
            '(': ')',
            '[': ']',
            '{': '}',
            '<': '>',
            '"': '"',
            "'": "'"
        }
        if text in opening_pairs:
            # Check for Case 2: quote is likely intended as closing an unclosed string on the current line
            is_unbalanced_quote = False
            if text == '"':
                left_quotes = line_prefix.count('"')
                if left_quotes % 2 == 1:
                    is_unbalanced_quote = True
            elif text == "'":
                left_single_quotes = line_prefix.count("'")
                if left_single_quotes % 2 == 1:
                    is_unbalanced_quote = True
            
            if is_unbalanced_quote:
                # Just insert the single quote character
                cursor.insertText(text)
                self.last_auto_inserted_closing_pos = -1
                self.last_auto_inserted_char = ''
            else:
                # Standard auto-pair insertion
                cursor.beginEditBlock()
                cursor.insertText(text + opening_pairs[text])
                cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
                self.setTextCursor(cursor)
                cursor.endEditBlock()
                self.last_auto_inserted_closing_pos = cursor.position()
                self.last_auto_inserted_char = text
            event.accept()
            return

        # 5. Map Tab key inside selections to indent/outdent
        if key == Qt.Key.Key_Tab:
            if cursor.hasSelection():
                self.indent_lines(outdent=False)
            else:
                cursor.insertText("    ")
            event.accept()
            return

        # 6. Map Shift+Tab to outdent
        if key == Qt.Key.Key_Backtab:
            self.indent_lines(outdent=True)
            event.accept()
            return

        # 7. Smart ENTER Curly Brace auto-indent
        if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            char_left = line_prefix[-1] if line_prefix else ""
            char_right = line_suffix[0] if line_suffix else ""
            
            indent = ""
            for char in line_text:
                if char.isspace():
                    indent += char
                else:
                    break

            if char_left == "{" and char_right == "}":
                cursor.beginEditBlock()
                cursor.insertText("\n" + indent + "    \n" + indent)
                cursor.movePosition(QTextCursor.MoveOperation.Up)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
                self.setTextCursor(cursor)
                cursor.endEditBlock()
                event.accept()
                return
            else:
                cursor.insertText("\n" + indent)
                event.accept()
                return

        # Standard keyboard delegate
        super().keyPressEvent(event)
        
        # 7. Scan and invoke autocomplete popups
        if text.isalnum() or text == '_':
            self.trigger_autocomplete()
        else:
            self.autocomplete_popup.hide()

    # ==============================================================================
    # 6. IntelliSense Suggestions Logic
# ==============================================================================
    def trigger_autocomplete(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText().strip()
        
        if len(word) < 2:
            self.autocomplete_popup.hide()
            return
            
        # Complete dictionary vocab pool
        keywords = [
            "char", "class", "const", "double", "enum", "explicit", "extern",
            "float", "inline", "int", "long", "private", "protected", "public",
            "short", "static", "struct", "template", "typedef", "typename",
            "unsigned", "virtual", "bool", "using", "namespace", "return",
            "break", "case", "continue", "default", "else", "for", "if", "while",
            "sizeof", "printf", "scanf", "cout", "cin", "endl", "vector", "string",
            "map", "set", "iostream", "algorithm", "push_back", "size", "clear"
        ]
        
        # Dynamically scan variable/function tokens inside active editor document
        doc_text = self.toPlainText()
        doc_words = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", doc_text))
        
        total_vocabulary = set(keywords) | doc_words
        # Exclude active typing word
        if word in total_vocabulary:
            total_vocabulary.remove(word)
            
        # Filter matching suggestions
        matches = sorted([w for w in total_vocabulary if w.lower().startswith(word.lower())])
        
        if matches:
            self.autocomplete_popup.clear()
            self.autocomplete_popup.addItems(matches[:10])  # Cap autocomplete at 10 items
            self.autocomplete_popup.setCurrentRow(0)
            
            self.autocomplete_popup.show()
            self.update_autocomplete_popup_position()
        else:
            self.autocomplete_popup.hide()

    def update_autocomplete_popup_position(self):
        if not self.autocomplete_popup.isVisible():
            return
        rect = self.cursorRect()
        popup_pos = self.viewport().mapToGlobal(rect.bottomLeft())
        # Constrain dimensions
        h = min(150, self.autocomplete_popup.count() * 24 + 4)
        self.autocomplete_popup.setGeometry(popup_pos.x(), popup_pos.y() + 4, 220, h)
        self.autocomplete_popup.raise_()

    def insert_completion(self):
        current_item = self.autocomplete_popup.currentItem()
        if not current_item:
            self.autocomplete_popup.hide()
            return
            
        completion = current_item.text()
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.insertText(completion)
        self.setTextCursor(cursor)
        self.autocomplete_popup.hide()

    # ==============================================================================
    # 7. Advanced IDE Line Manipulations & Gestures
# ==============================================================================
    def indent_lines(self, outdent=False):
        """Indent or outdent selected multiline block in 4-space tab increments."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        start_block = cursor.blockNumber()
        
        cursor.setPosition(end)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        end_block = cursor.blockNumber()
        
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            cursor.setPosition(block.position())
            if outdent:
                text = block.text()
                removed = 0
                for _ in range(4):
                    if text and text.startswith(" "):
                        cursor.deleteChar()
                        text = text[1:]
                        removed += 1
                    else:
                        break
            else:
                cursor.insertText("    ")
        cursor.endEditBlock()
        
        # Reselect lines
        new_start = self.document().findBlockByNumber(start_block).position()
        new_end = self.document().findBlockByNumber(end_block).position() + self.document().findBlockByNumber(end_block).length() - 1
        cursor.setPosition(new_start)
        cursor.setPosition(new_end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def toggle_comment(self):
        """Toggles standard C/C++ line comments (//) on selection or active line."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        self.blockSignals(True)
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        
        lines = []
        # Assemble list of lines inside selection
        while cursor.position() < end or (cursor.position() == end and start == end):
            line_pos = cursor.position()
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            line_text = cursor.selectedText()
            cursor.clearSelection()
            lines.append((line_pos, line_text))
            
            if not cursor.movePosition(QTextCursor.MoveOperation.Down) or cursor.position() >= self.document().characterCount() - 1:
                break
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            
        all_commented = True
        for _, text in lines:
            trimmed = text.lstrip()
            if trimmed and not trimmed.startswith("//"):
                all_commented = False
                break
                
        cursor.beginEditBlock()
        for pos, text in reversed(lines):
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            if all_commented:
                # Remove comment markers
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                line_content = cursor.selectedText()
                trimmed = line_content.lstrip()
                if trimmed.startswith("// "):
                    new_line = line_content.replace("// ", "", 1)
                elif trimmed.startswith("//"):
                    new_line = line_content.replace("//", "", 1)
                else:
                    new_line = line_content
                cursor.insertText(new_line)
            else:
                # Prepend comment markers preserving leading indentation
                indent = ""
                for char in text:
                    if char.isspace():
                        indent += char
                    else:
                        break
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                line_content = cursor.selectedText()
                new_line = indent + "// " + line_content.lstrip()
                cursor.insertText(new_line)
        cursor.endEditBlock()
        self.blockSignals(False)
        self.main_app.on_editor_modified(self)

    def toggle_block_comment(self):
        """Wraps selected text blocks inside /* ... */ block comments (Shift+Alt+A)."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.insertText("/*  */")
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            self.setTextCursor(cursor)
            return
            
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.insertText("/* ")
        cursor.setPosition(end + 3)
        cursor.insertText(" */")
        self.main_app.on_editor_modified(self)

    def duplicate_line(self):
        """Duplicates active line or selected block immediately below (Ctrl+D)."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            pos = cursor.selectionEnd()
            cursor.setPosition(pos)
            cursor.insertText(text)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            line_start = cursor.position()
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            line_text = cursor.selectedText()
            cursor.clearSelection()
            cursor.insertText("\n" + line_text)
        self.main_app.on_editor_modified(self)

    def delete_line(self):
        """Deletes active line completely (Ctrl+Shift+K)."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar() # trailing newline
        cursor.endEditBlock()
        self.main_app.on_editor_modified(self)

    def move_lines(self, direction):
        """Moves selected lines or current active block up or down (Alt+Up/Down)."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        line_start = cursor.blockNumber()
        
        cursor.setPosition(end)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        line_end = cursor.blockNumber()
        
        if direction == -1: # Move block up
            if line_start == 0:
                return
            target_block = self.document().findBlockByNumber(line_start - 1)
            target_text = target_block.text()
            
            # Select target lines
            cursor.setPosition(self.document().findBlockByNumber(line_start).position())
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            for _ in range(line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            selected_text = cursor.selectedText()
            
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            
            cursor.setPosition(self.document().findBlockByNumber(line_start - 1).position())
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            
            cursor.insertText(selected_text + "\n" + target_text)
            
            new_pos = self.document().findBlockByNumber(line_start - 1).position()
            cursor.setPosition(new_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            for _ in range(line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            cursor.endEditBlock()
            
        elif direction == 1: # Move block down
            if line_end >= self.document().blockCount() - 1:
                return
            target_block = self.document().findBlockByNumber(line_end + 1)
            target_text = target_block.text()
            
            # Select lines
            cursor.setPosition(self.document().findBlockByNumber(line_start).position())
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            for _ in range(line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            selected_text = cursor.selectedText()
            
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.deleteChar()
            
            cursor.setPosition(self.document().findBlockByNumber(line_start + (line_end - line_start) + 1).position())
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            
            cursor.insertText(target_text + "\n" + selected_text)
            
            new_pos = self.document().findBlockByNumber(line_start + 1).position()
            cursor.setPosition(new_pos)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            for _ in range(line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            cursor.endEditBlock()
            
        self.main_app.on_editor_modified(self)


# ==============================================================================
# 6. Find & Replace Floating Widget Panel
# ==============================================================================
class FindReplacePanel(QFrame):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setObjectName("findReplacePanel")
        self.setup_panel()
        
    def setup_panel(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        # Row 1: Find Controls
        row1 = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.find_input.returnPressed.connect(self.find_next)
        
        self.case_box = QPushButton("Aa")
        self.case_box.setCheckable(True)
        self.case_box.setFixedWidth(30)
        self.case_box.setToolTip("Match Case")
        
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.find_next)
        
        self.prev_btn = QPushButton("Prev")
        self.prev_btn.clicked.connect(self.find_prev)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedWidth(24)
        self.close_btn.clicked.connect(self.hide)
        
        row1.addWidget(self.find_input)
        row1.addWidget(self.case_box)
        row1.addWidget(self.next_btn)
        row1.addWidget(self.prev_btn)
        row1.addWidget(self.close_btn)
        
        # Row 2: Replace Controls
        self.replace_row = QWidget()
        row2 = QHBoxLayout(self.replace_row)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)
        
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")
        
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self.replace_text)
        
        self.all_btn = QPushButton("Replace All")
        self.all_btn.clicked.connect(self.replace_all)
        
        row2.addWidget(self.replace_input)
        row2.addWidget(self.replace_btn)
        row2.addWidget(self.all_btn)
        
        layout.addLayout(row1)
        layout.addWidget(self.replace_row)
        self.hide()

    def find_next(self):
        editor = self.main_app.get_active_editor()
        if not editor:
            return
        search_text = self.find_input.text()
        if not search_text:
            return
            
        flags = QTextDocument.FindFlag(0)
        if self.case_box.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        found = editor.find(search_text, flags)
        if not found:
            # Wrap around from start
            cursor = editor.textCursor()
            cursor.setPosition(0)
            editor.setTextCursor(cursor)
            editor.find(search_text, flags)
            
    def find_prev(self):
        editor = self.main_app.get_active_editor()
        if not editor:
            return
        search_text = self.find_input.text()
        if not search_text:
            return
            
        flags = QTextDocument.FindFlag.FindBackward
        if self.case_box.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        found = editor.find(search_text, flags)
        if not found:
            # Wrap around from end
            cursor = editor.textCursor()
            cursor.setPosition(editor.document().characterCount() - 1)
            editor.setTextCursor(cursor)
            editor.find(search_text, flags)
            
    def replace_text(self):
        editor = self.main_app.get_active_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
            editor.setTextCursor(cursor)
        self.find_next()
        
    def replace_all(self):
        editor = self.main_app.get_active_editor()
        if not editor:
            return
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not search_text:
            return
            
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(0)
        editor.setTextCursor(cursor)
        
        flags = QTextDocument.FindFlag(0)
        if self.case_box.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        count = 0
        while editor.find(search_text, flags):
            c = editor.textCursor()
            c.insertText(replace_text)
            count += 1
            
        cursor.endEditBlock()
        self.main_app.write_system_log(f"Replaced {count} occurrences of '{search_text}'", success=True)


# ==============================================================================
# 7. Sleek Welcome Landing Page Widget
# ==============================================================================
class WelcomeWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomeWidget")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        
        logo = QLabel("💻")
        logo.setStyleSheet("font-size: 64px; margin-bottom: 5px;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        
        title = QLabel("coderun C/C++ IDE")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("A lightweight, blazingly fast C/C++ development workspace")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Shortcut Guides
        shortcuts = [
            ("New File", "Ctrl + N"),
            ("Open File", "Ctrl + O"),
            ("Open Folder", "📂 Open Folder Button"),
            ("Save Active File", "Ctrl + S"),
            ("Save File As", "Ctrl + Shift + S"),
            ("Toggle Comments", "Ctrl + /"),
            ("Block Comment", "Shift + Alt + A"),
            ("Duplicate Lines", "Ctrl + D"),
            ("Move Lines Block", "Alt + Up / Down"),
            ("Delete Line Block", "Ctrl + Shift + K"),
            ("Find / Replace", "Ctrl + F / Ctrl + H"),
            ("Compile & Run", "F5 / Ctrl + R"),
        ]
        
        grid_container = QWidget()
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setSpacing(6)
        
        for action, key in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(25)
            
            lbl_action = QLabel(action)
            lbl_action.setStyleSheet("color: #858585; font-size: 11px;")
            lbl_action.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_action.setFixedWidth(180)
            
            lbl_key = QLabel(key)
            lbl_key.setStyleSheet("color: #569cd6; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
            lbl_key.setAlignment(Qt.AlignmentFlag.AlignLeft)
            lbl_key.setFixedWidth(180)
            
            row.addWidget(lbl_action)
            row.addWidget(lbl_key)
            grid_layout.addLayout(row)
            
        layout.addWidget(grid_container)


# ==============================================================================
# 8. Main IDE Application Window Class
# ==============================================================================
class CoderunApp(QMainWindow):
    def __init__(self, target_dir=None):
        super().__init__()
        
        # Workspace Configuration
        self.target_dir = os.path.abspath(target_dir) if target_dir else os.getcwd()
        self.theme_is_dark = True
        
        # Initialize default settings dictionary
        self.settings = {
            "font_family": "JetBrains Mono",
            "font_size": 14,
            "line_height": 1.4,
            "tab_size": 4,
            "word_wrap": False,
            "ligatures": True,
            "auto_save": False,
            "terminal_font_size": 12
        }
        self.load_settings_from_file()
        
        # Asynchronous Process Execution State
        self.process = None
        self.compile_start_time = 0
        self.compile_time = 0
        self.run_start_time = 0
        self.run_time = 0
        self.is_compiling = False
        self.is_running_program = False
        
        # Verify Compiler Availability and Paths
        self.gcc_path = self.find_compiler_path("gcc")
        self.gpp_path = self.find_compiler_path("g++")
        
        self.gcc_version = self.get_compiler_version(self.gcc_path) if self.gcc_path else None
        self.gpp_version = self.get_compiler_version(self.gpp_path) if self.gpp_path else None
        
        # UI Setup
        self.init_ui()
        self.update_compiler_status()
        self.apply_loaded_settings()
        self.refresh_files()
        
        # File system watcher for auto-refresh list updates
        self.watcher = QFileSystemWatcher(self)
        if os.path.exists(self.target_dir):
            self.watcher.addPath(self.target_dir)
            self.watcher.directoryChanged.connect(self.refresh_files)

    def find_compiler_path(self, compiler):
        path = shutil.which(compiler)
        if not path and os.name == 'nt':
            common_paths = [
                f"C:\\msys64\\ucrt64\\bin\\{compiler}.exe",
                f"C:\\msys64\\mingw64\\bin\\{compiler}.exe",
                f"C:\\msys64\\clang64\\bin\\{compiler}.exe",
                f"C:\\MinGW\\bin\\{compiler}.exe"
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
        return path

    def get_compiler_version(self, compiler_path):
        try:
            result = subprocess.run([compiler_path, "--version"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return result.stdout.split('\n')[0]
        except Exception:
            return "Found (Unknown)"

    def init_ui(self):
        self.setWindowTitle("coderun - C/C++ IDE")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        self.setCentralWidget(main_widget)
        
        # --- Top Banner Layout ---
        header_widget = QFrame()
        header_widget.setObjectName("headerWidget")
        header_widget.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 18px;")
        header_layout.addWidget(folder_icon)
        
        dir_info_layout = QVBoxLayout()
        dir_title = QLabel("WORKSPACE DIRECTORY")
        dir_title.setStyleSheet("color: #858585; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        self.dir_path_lbl = QLabel(self.target_dir)
        self.dir_path_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        dir_info_layout.addWidget(dir_title)
        dir_info_layout.addWidget(self.dir_path_lbl)
        header_layout.addLayout(dir_info_layout)
        header_layout.addStretch()
        
        # Header Controls
        self.theme_btn = QPushButton("Toggle Theme")
        self.theme_btn.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_btn)
        
        self.settings_btn = QPushButton("Settings ⚙️")
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.settings_btn)
        
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_folder_btn.clicked.connect(self.select_folder)
        header_layout.addWidget(self.open_folder_btn)
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.refresh_files)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addWidget(header_widget)
        
        # --- Missing Compiler warning banner ---
        if not self.gcc_version and not self.gpp_version:
            self.warning_banner = QFrame()
            self.warning_banner.setStyleSheet("background-color: #5a1d1d; border: 1px solid #be2e13; border-radius: 4px;")
            warn_layout = QHBoxLayout(self.warning_banner)
            warn_layout.setContentsMargins(12, 6, 12, 6)
            warn_lbl = QLabel("⚠️ NO COMPILER DETECTED: C/C++ compilation tools (gcc/g++) are missing from your PATH. Setup compilers globally to run programs.")
            warn_lbl.setStyleSheet("color: #ffcccc; font-weight: bold;")
            warn_layout.addWidget(warn_lbl)
            main_layout.addWidget(self.warning_banner)
            
        # --- Splitter UI layout ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet("QSplitter::handle { background-color: #2d2d2d; width: 4px; }")
        
        # -- Left Sidebar Widget --
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(6)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter files...")
        self.search_input.textChanged.connect(self.filter_files)
        left_layout.addWidget(self.search_input)
        
        # Beautiful QTreeView File Explorer
        self.file_explorer = QTreeView()
        self.file_model = CppFileExplorerModel(self)
        self.file_model.setRootPath(self.target_dir)
        self.file_model.setNameFilters(["*.c", "*.cpp", "*.cc", "*.cxx", "*.h", "*.hpp", "*.txt", "*.md"])
        self.file_model.setNameFilterDisables(False) # Hide files that don't match filters
        
        self.file_explorer.setModel(self.file_model)
        self.file_explorer.setRootIndex(self.file_model.index(self.target_dir))
        
        # Hide standard file size/type/date columns to mimic clean VS Code tree explorer
        self.file_explorer.setHeaderHidden(True)
        for i in range(1, self.file_model.columnCount()):
            self.file_explorer.hideColumn(i)
            
        self.file_explorer.setObjectName("fileExplorer")
        self.file_explorer.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_explorer.customContextMenuRequested.connect(self.show_explorer_context_menu)
        self.file_explorer.doubleClicked.connect(self.on_explorer_double_clicked)
        
        left_layout.addWidget(self.file_explorer)
        
        # Sidebar Actions Toolbar
        sidebar_actions = QHBoxLayout()
        sidebar_actions.setSpacing(4)
        
        self.new_file_btn = QPushButton("New File")
        self.new_file_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.new_file_btn.clicked.connect(self.new_file)
        sidebar_actions.addWidget(self.new_file_btn)
        
        self.rename_file_btn = QPushButton("Rename")
        self.rename_file_btn.clicked.connect(self.rename_file)
        sidebar_actions.addWidget(self.rename_file_btn)
        
        self.delete_file_btn = QPushButton("Delete")
        self.delete_file_btn.clicked.connect(self.delete_file)
        sidebar_actions.addWidget(self.delete_file_btn)
        
        left_layout.addLayout(sidebar_actions)
        main_splitter.addWidget(left_widget)
        
        # -- Right Main Stack Layout (Toolbar actions + Code Workspace / Welcome Widget + Output console) --
        right_panel_container = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_container)
        right_panel_layout.setContentsMargins(5, 0, 0, 0)
        right_panel_layout.setSpacing(8)
        
        # Actions Panel block
        actions_frame = QFrame()
        actions_frame.setObjectName("actionsFrame")
        actions_frame.setFrameShape(QFrame.Shape.StyledPanel)
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(10)
        
        self.active_file_lbl = QLabel("No File Selected")
        self.active_file_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #569cd6;")
        actions_layout.addWidget(self.active_file_lbl)
        actions_layout.addStretch()
        
        # Performance timing stats
        self.time_lbl = QLabel("Compile: --s  |  Run: --s")
        self.time_lbl.setStyleSheet("color: #858585; font-family: 'Consolas'; font-size: 11px;")
        actions_layout.addWidget(self.time_lbl)
        
        # Save / Save As / Compile / Stop controls
        self.save_btn = QPushButton("Save")
        self.save_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.save_btn.clicked.connect(self.save_active_file)
        actions_layout.addWidget(self.save_btn)
        
        self.save_as_btn = QPushButton("Save As")
        self.save_as_btn.clicked.connect(self.save_as_file)
        actions_layout.addWidget(self.save_as_btn)
        
        self.run_btn = QPushButton("RUN FILE")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_btn.clicked.connect(self.run_selected_file)
        actions_layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.clicked.connect(self.terminate_process)
        actions_layout.addWidget(self.stop_btn)
        
        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self.clear_console)
        actions_layout.addWidget(self.clear_btn)
        
        right_panel_layout.addWidget(actions_frame)
        
        # Find and Replace Panel (Floats above workspace)
        self.find_replace_panel = FindReplacePanel(self)
        right_panel_layout.addWidget(self.find_replace_panel)
        
        # Vertical Workspace Splitter (Editor vs Console)
        workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        workspace_splitter.setStyleSheet("QSplitter::handle { background-color: #2d2d2d; height: 4px; }")
        
        # Editor Workspace Stack (0 = Welcome landing page, 1 = Editor Tabs)
        self.workspace_stack = QStackedWidget()
        
        self.welcome_widget = WelcomeWidget()
        self.workspace_stack.addWidget(self.welcome_widget)
        
        # Multi-tab widget representing open files
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.setMovable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_tab)
        self.editor_tabs.currentChanged.connect(self.on_active_tab_changed)
        self.editor_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor_tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.editor_tabs.tabBar().installEventFilter(self)
        self.workspace_stack.addWidget(self.editor_tabs)
        
        workspace_splitter.addWidget(self.workspace_stack)
        
        # Bottom Console Stack Layout
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(6)
        
        self.console = QTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Console output compiles and streams here...")
        console_layout.addWidget(self.console)
        
        # Stdin input bar
        input_layout = QHBoxLayout()
        input_lbl = QLabel("Standard Input:")
        input_lbl.setStyleSheet("color: #858585; font-size: 11px;")
        self.stdin_input = QLineEdit()
        self.stdin_input.setPlaceholderText("Provide program inputs here and hit Enter to feed standard input (stdin)...")
        self.stdin_input.returnPressed.connect(self.send_stdin)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_stdin)
        
        input_layout.addWidget(input_lbl)
        input_layout.addWidget(self.stdin_input)
        input_layout.addWidget(self.send_btn)
        console_layout.addLayout(input_layout)
        
        workspace_splitter.addWidget(console_widget)
        
        workspace_splitter.setSizes([480, 250])
        right_panel_layout.addWidget(workspace_splitter)
        
        main_splitter.addWidget(right_panel_container)
        main_splitter.setSizes([250, 950])
        main_layout.addWidget(main_splitter)
        
        # --- Bottom Status Bar Configuration ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.cursor_info_lbl = QLabel("")
        self.cursor_info_lbl.setStyleSheet("color: #ffffff; font-family: 'Consolas', monospace; font-size: 11px; margin-right: 15px;")
        self.status_bar.addPermanentWidget(self.cursor_info_lbl)
        
        # Map Keyboard Shortcuts
        self.setup_shortcuts()
        
        # Apply CSS Themes
        self.apply_theme()
        self.update_editor_ui_state()
        self.update_compiler_status()

    def setup_shortcuts(self):
        # Ctrl+N -> New File
        self.sc_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self.sc_new.activated.connect(self.new_file)
        
        # Ctrl+O -> Open File dialog
        self.sc_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.sc_open.activated.connect(self.open_file_dialog)
        
        # Ctrl+S -> Save
        self.sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.sc_save.activated.connect(self.save_active_file)
        
        # Ctrl+Shift+S -> Save As
        self.sc_save_as = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.sc_save_as.activated.connect(self.save_as_file)
        
        # Ctrl+F -> Show Find Replace Panel
        self.sc_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.sc_find.activated.connect(self.show_find_panel)
        
        # Ctrl+H -> Show Replace Panel
        self.sc_replace = QShortcut(QKeySequence("Ctrl+H"), self)
        self.sc_replace.activated.connect(self.show_replace_panel)
        
        # Ctrl+/ -> Toggle comment
        self.sc_comment = QShortcut(QKeySequence("Ctrl+/"), self)
        self.sc_comment.activated.connect(self.toggle_editor_comment)

        # Shift+Alt+A -> Toggle block comment
        self.sc_block_comment = QShortcut(QKeySequence("Shift+Alt+A"), self)
        self.sc_block_comment.activated.connect(self.toggle_editor_block_comment)
        
        # F5 / Ctrl+R -> Run
        self.sc_run1 = QShortcut(QKeySequence("F5"), self)
        self.sc_run1.activated.connect(self.run_selected_file)
        self.sc_run2 = QShortcut(QKeySequence("Ctrl+R"), self)
        self.sc_run2.activated.connect(self.run_selected_file)
        
        # F6 / Ctrl+Shift+R -> Refresh
        self.sc_ref1 = QShortcut(QKeySequence("F6"), self)
        self.sc_ref1.activated.connect(self.refresh_files)
        self.sc_ref2 = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        self.sc_ref2.activated.connect(self.refresh_files)
        
        # Escape -> Stop / Terminate processes
        self.sc_stop = QShortcut(QKeySequence("Escape"), self)
        self.sc_stop.activated.connect(self.terminate_process)
        
        # Ctrl+L -> Clear output console
        self.sc_clear = QShortcut(QKeySequence("Ctrl+L"), self)
        self.sc_clear.activated.connect(self.clear_console)

        # Line manipulating shortcuts delegated to active editor
        self.sc_dup = QShortcut(QKeySequence("Ctrl+D"), self)
        self.sc_dup.activated.connect(lambda: self.delegate_editor_shortcut("duplicate_line"))
        
        self.sc_del = QShortcut(QKeySequence("Ctrl+Shift+K"), self)
        self.sc_del.activated.connect(lambda: self.delegate_editor_shortcut("delete_line"))
        
        self.sc_move_up = QShortcut(QKeySequence("Alt+Up"), self)
        self.sc_move_up.activated.connect(lambda: self.delegate_editor_shortcut("move_lines", -1))
        
        self.sc_move_down = QShortcut(QKeySequence("Alt+Down"), self)
        self.sc_move_down.activated.connect(lambda: self.delegate_editor_shortcut("move_lines", 1))

        # Editor zoom shortcuts
        self.sc_zoom_in1 = QShortcut(QKeySequence("Ctrl+Plus"), self)
        self.sc_zoom_in1.activated.connect(self.zoom_in_active_editor)
        self.sc_zoom_in2 = QShortcut(QKeySequence("Ctrl+="), self)
        self.sc_zoom_in2.activated.connect(self.zoom_in_active_editor)
        
        self.sc_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.sc_zoom_out.activated.connect(self.zoom_out_active_editor)
        
        self.sc_zoom_reset = QShortcut(QKeySequence("Ctrl+0"), self)
        self.sc_zoom_reset.activated.connect(self.reset_zoom_active_editor)

    def delegate_editor_shortcut(self, method_name, *args):
        editor = self.get_active_editor()
        if editor:
            method = getattr(editor, method_name)
            method(*args)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self)
        dialog.exec()
        
    def load_settings_from_file(self):
        settings_path = os.path.join(self.target_dir, ".gemini_settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except Exception:
                pass
                
    def save_settings_to_file(self):
        settings_path = os.path.join(self.target_dir, ".gemini_settings.json")
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass
            
    def apply_loaded_settings(self):
        font_family = self.settings.get("font_family", "JetBrains Mono")
        font_size = self.settings.get("font_size", 14)
        tab_size = self.settings.get("tab_size", 4)
        word_wrap = self.settings.get("word_wrap", False)
        term_size = self.settings.get("terminal_font_size", 12)
        
        font = QFont(font_family, font_size)
        font.setFixedPitch(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        
        for idx in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(idx)
            editor = tab.findChild(CodeEditor)
            if editor:
                editor.setFont(font)
                editor.setTabStopDistance(QFontMetrics(font).horizontalAdvance(' ') * tab_size)
                editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if word_wrap else QPlainTextEdit.LineWrapMode.NoWrap)
                editor.update_line_number_area_width(0)
                
        term_font = QFont("Consolas", term_size)
        self.console.setFont(term_font)
        
    def show_explorer_context_menu(self, point):
        index = self.file_explorer.indexAt(point)
        if not index.isValid():
            return
            
        filepath = self.file_model.filePath(index)
        is_dir = self.file_model.isDir(index)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #252526; border: 1px solid #3c3c3c; color: #cccccc; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #094771; color: #ffffff; }
        """)
        
        if not is_dir:
            act_open = menu.addAction("Open")
            act_open_tab = menu.addAction("Open in New Tab")
            menu.addSeparator()
            act_rename = menu.addAction("Rename")
            act_delete = menu.addAction("Delete")
            act_duplicate = menu.addAction("Duplicate")
            menu.addSeparator()
            act_copy_path = menu.addAction("Copy Path")
            act_reveal = menu.addAction("Reveal in Explorer")
            menu.addSeparator()
            act_compile = menu.addAction("Compile File")
            act_run = menu.addAction("Run File")
            
            action = menu.exec(self.file_explorer.viewport().mapToGlobal(point))
            
            if action == act_open or action == act_open_tab:
                self.open_file_by_path(filepath)
            elif action == act_rename:
                self.rename_explorer_item(filepath)
            elif action == act_delete:
                self.delete_explorer_item(filepath)
            elif action == act_duplicate:
                self.duplicate_explorer_item(filepath)
            elif action == act_copy_path:
                QApplication.clipboard().setText(filepath)
                self.write_system_log("Copied path to clipboard.", success=True)
            elif action == act_reveal:
                self.reveal_in_explorer(filepath)
            elif action == act_compile or action == act_run:
                self.open_file_by_path(filepath)
                self.run_selected_file()
        else:
            act_new_file = menu.addAction("New File")
            act_new_folder = menu.addAction("New Folder")
            menu.addSeparator()
            act_rename = menu.addAction("Rename")
            act_delete = menu.addAction("Delete")
            act_refresh = menu.addAction("Refresh")
            
            action = menu.exec(self.file_explorer.viewport().mapToGlobal(point))
            
            if action == act_new_file:
                self.new_file_in_dir(filepath)
            elif action == act_new_folder:
                self.new_folder_in_dir(filepath)
            elif action == act_rename:
                self.rename_explorer_item(filepath)
            elif action == act_delete:
                self.delete_explorer_item(filepath)
            elif action == act_refresh:
                self.refresh_files()
                
    def on_explorer_double_clicked(self, index):
        if not index.isValid():
            return
        filepath = self.file_model.filePath(index)
        if not self.file_model.isDir(index):
            self.open_file_by_path(filepath)
            
    def new_file_in_dir(self, dirpath):
        name, ok = QInputDialog.getText(self, "New File", "Enter file name:")
        if ok and name.strip():
            full_path = os.path.join(dirpath, name.strip())
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write("")
                self.open_file_by_path(full_path)
                self.write_system_log(f"Created file: {name}", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create file: {str(e)}")
                
    def new_folder_in_dir(self, dirpath):
        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name.strip():
            full_path = os.path.join(dirpath, name.strip())
            try:
                os.makedirs(full_path, exist_ok=True)
                self.write_system_log(f"Created folder: {name}", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder: {str(e)}")
                
    def rename_explorer_item(self, path):
        old_name = os.path.basename(path)
        name, ok = QInputDialog.getText(self, "Rename", "Enter new name:", text=old_name)
        if ok and name.strip() and name.strip() != old_name:
            new_path = os.path.join(os.path.dirname(path), name.strip())
            try:
                os.rename(path, new_path)
                # Update open tabs referencing the renamed path!
                for idx in range(self.editor_tabs.count()):
                    tab = self.editor_tabs.widget(idx)
                    editor = tab.findChild(CodeEditor)
                    if editor and editor.filepath == path:
                        editor.filepath = new_path
                        self.editor_tabs.setTabText(idx, name.strip())
                        if self.editor_tabs.currentIndex() == idx:
                            self.active_file_lbl.setText(name.strip())
                        break
                self.write_system_log(f"Renamed '{old_name}' to '{name}'", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not rename: {str(e)}")
                
    def delete_explorer_item(self, path):
        name = os.path.basename(path)
        ret = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete '{name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            try:
                # Close associated tab if open
                for idx in reversed(range(self.editor_tabs.count())):
                    tab = self.editor_tabs.widget(idx)
                    editor = tab.findChild(CodeEditor)
                    if editor and editor.filepath == path:
                        self.editor_tabs.removeTab(idx)
                        break
                        
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.write_system_log(f"Deleted '{name}' successfully.", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {str(e)}")
                
    def duplicate_explorer_item(self, path):
        if os.path.isdir(path):
            return
        dir_name = os.path.dirname(path)
        base, ext = os.path.splitext(os.path.basename(path))
        new_path = os.path.join(dir_name, f"{base}_copy{ext}")
        try:
            shutil.copy2(path, new_path)
            self.write_system_log(f"Duplicated to '{os.path.basename(new_path)}'", success=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not duplicate file: {str(e)}")
            
    def reveal_in_explorer(self, path):
        norm = os.path.normpath(path)
        subprocess.run(["explorer", "/select,", norm], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
    def show_tab_context_menu(self, point):
        idx = self.editor_tabs.tabBar().tabAt(point)
        if idx == -1:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #252526; border: 1px solid #3c3c3c; color: #cccccc; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #094771; color: #ffffff; }
        """)
        
        act_close = menu.addAction("Close")
        act_close_others = menu.addAction("Close Others")
        act_close_all = menu.addAction("Close All")
        menu.addSeparator()
        act_reveal = menu.addAction("Reveal in Explorer")
        act_copy_path = menu.addAction("Copy File Path")
        
        action = menu.exec(self.editor_tabs.mapToGlobal(point))
        
        tab_container = self.editor_tabs.widget(idx)
        editor = tab_container.findChild(CodeEditor)
        if not editor:
            return
            
        filepath = editor.filepath
        
        if action == act_close:
            self.close_tab(idx)
        elif action == act_close_others:
            for i in reversed(range(self.editor_tabs.count())):
                if i != idx:
                    self.close_tab(i)
        elif action == act_close_all:
            for i in reversed(range(self.editor_tabs.count())):
                self.close_tab(i)
        elif action == act_reveal:
            self.reveal_in_explorer(filepath)
        elif action == act_copy_path:
            QApplication.clipboard().setText(filepath)
            self.write_system_log("Copied path to clipboard.", success=True)
            
    def eventFilter(self, obj, event):
        if obj == self.editor_tabs.tabBar() and event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                idx = self.editor_tabs.tabBar().tabAt(event.pos())
                if idx != -1:
                    self.close_tab(idx)
                    return True
        return super().eventFilter(obj, event)

    def zoom_in_active_editor(self):
        editor = self.get_active_editor()
        if editor:
            editor.zoom_in()
            
    def zoom_out_active_editor(self):
        editor = self.get_active_editor()
        if editor:
            editor.zoom_out()
            
    def reset_zoom_active_editor(self):
        editor = self.get_active_editor()
        if editor:
            editor.reset_zoom()

    def apply_theme(self):
        """Sets main application stylesheets corresponding to theme_is_dark."""
        if hasattr(self, 'file_model'):
            self.file_model.set_theme(self.theme_is_dark)
            
        if self.theme_is_dark:
            # Slate Dark Colors Scheme (VS Code Theme Matching)
            self.setStyleSheet("""
                QMainWindow { background-color: #1e1e1e; }
                QWidget { color: #d4d4d4; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
                QFrame#headerWidget { background-color: #252526; border: 1px solid #2d2d2d; border-radius: 6px; }
                QFrame#actionsFrame { background-color: #252526; border: 1px solid #2d2d2d; border-radius: 4px; }
                QFrame#findReplacePanel { background-color: #252526; border: 1px solid #3c3c3c; border-radius: 4px; }
                QFrame#welcomeWidget { background-color: #1e1e1e; border: 1px solid #2d2d2d; border-radius: 6px; }
                QLabel#welcomeTitle { color: #ffffff; font-size: 24px; font-weight: bold; }
                QLabel#welcomeSubtitle { color: #858585; font-size: 12px; }
                QTabWidget::pane { border: 1px solid #2d2d2d; background-color: #252526; }
                QTabBar::tab { background-color: #1e1e1e; color: #969696; padding: 6px 14px; border: 1px solid #2d2d2d; border-bottom: none; }
                QTabBar::tab:selected { background-color: #1e1e1e; color: #ffffff; border-bottom: 2px solid #007acc; font-weight: bold; }
                QTreeView#fileExplorer { background-color: #252526; border: 1px solid #2d2d2d; border-radius: 4px; padding: 4px; color: #cccccc; }
                QTreeView#fileExplorer::item { padding: 4px 6px; border-radius: 3px; }
                QTreeView#fileExplorer::item:hover { background-color: #2a2d2e; color: #ffffff; }
                QTreeView#fileExplorer::item:selected { background-color: #37373d; color: #4ec9b0; font-weight: bold; }
                QLineEdit { background-color: #3c3c3c; border: 1px solid #3c3c3c; border-radius: 4px; padding: 6px 10px; color: #ffffff; }
                QLineEdit:focus { border: 1px solid #007acc; background-color: #2d2d2d; }
                QPushButton { background-color: #3c3c3c; border: 1px solid #3c3c3c; border-radius: 4px; padding: 5px 12px; font-weight: bold; color: #e1e1e1; }
                QPushButton:hover { background-color: #4c4c4c; color: #ffffff; }
                QPushButton#runBtn { background-color: #0e639c; border: 1px solid #0e639c; color: #ffffff; }
                QPushButton#runBtn:hover { background-color: #1177bb; }
                QPushButton#stopBtn { background-color: #9a2617; border: 1px solid #9a2617; color: #ffffff; }
                QPushButton#stopBtn:hover { background-color: #be2e13; }
                QTextEdit#console { background-color: #181818; border: 1px solid #2d2d2d; border-radius: 6px; padding: 12px; color: #d4d4d4; }
                QScrollBar:vertical { background: #1e1e1e; width: 10px; }
                QScrollBar::handle:vertical { background: #424242; min-height: 20px; border-radius: 5px; }
                QScrollBar::handle:vertical:hover { background: #5f5f5f; }
                QStatusBar { background-color: #007acc; color: #ffffff; }
            """)
        else:
            # Elegant Light Colors Scheme (VS Code Light+ Matching)
            self.setStyleSheet("""
                QMainWindow { background-color: #ffffff; }
                QWidget { color: #333333; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
                QFrame#headerWidget { background-color: #f3f3f3; border: 1px solid #e4e4e4; border-radius: 6px; }
                QFrame#actionsFrame { background-color: #f3f3f3; border: 1px solid #e4e4e4; border-radius: 4px; }
                QFrame#findReplacePanel { background-color: #f3f3f3; border: 1px solid #cccccc; border-radius: 4px; }
                QFrame#welcomeWidget { background-color: #ffffff; border: 1px solid #e4e4e4; border-radius: 6px; }
                QLabel#welcomeTitle { color: #000000; font-size: 24px; font-weight: bold; }
                QLabel#welcomeSubtitle { color: #6a6a6a; font-size: 12px; }
                QTabWidget::pane { border: 1px solid #e4e4e4; background-color: #ffffff; }
                QTabBar::tab { background-color: #f3f3f3; color: #6a6a6a; padding: 6px 14px; border: 1px solid #e4e4e4; border-bottom: none; }
                QTabBar::tab:selected { background-color: #ffffff; color: #000000; border-bottom: 2px solid #007acc; font-weight: bold; }
                QTreeView#fileExplorer { background-color: #ffffff; border: 1px solid #e4e4e4; border-radius: 4px; padding: 4px; color: #333333; }
                QTreeView#fileExplorer::item { padding: 4px 6px; border-radius: 3px; }
                QTreeView#fileExplorer::item:hover { background-color: #e4e6f1; color: #000000; }
                QTreeView#fileExplorer::item:selected { background-color: #cfd8dc; color: #037a72; font-weight: bold; }
                QLineEdit { background-color: #f3f3f3; border: 1px solid #e4e4e4; border-radius: 4px; padding: 6px 10px; color: #000000; }
                QLineEdit:focus { border: 1px solid #007acc; background-color: #ffffff; }
                QPushButton { background-color: #e1e1e1; border: 1px solid #cccccc; border-radius: 4px; padding: 5px 12px; font-weight: bold; color: #333333; }
                QPushButton:hover { background-color: #d1d1d1; color: #000000; }
                QPushButton#runBtn { background-color: #007acc; border: 1px solid #007acc; color: #ffffff; }
                QPushButton#runBtn:hover { background-color: #0088dd; }
                QPushButton#stopBtn { background-color: #be2e13; border: 1px solid #be2e13; color: #ffffff; }
                QPushButton#stopBtn:hover { background-color: #e53935; }
                QTextEdit#console { background-color: #f3f3f3; border: 1px solid #e4e4e4; border-radius: 6px; padding: 12px; color: #333333; }
                QScrollBar:vertical { background: #f3f3f3; width: 10px; }
                QScrollBar::handle:vertical { background: #cccccc; min-height: 20px; border-radius: 5px; }
                QScrollBar::handle:vertical:hover { background: #aaaaaa; }
                QStatusBar { background-color: #007acc; color: #ffffff; }
            """)

        # Sync active tab style sheet coloring
        for idx in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(idx)
            editor = tab.findChild(CodeEditor)
            minimap = tab.findChild(Minimap)
            if editor and minimap:
                if self.theme_is_dark:
                    editor.setStyleSheet("background-color: #1e1e1e; border: 1px solid #2d2d2d; color: #ffffff;")
                    editor.line_number_area.setStyleSheet("background-color: #1e1e1e;")
                    minimap.setStyleSheet("background-color: #1a1a1a; border: none; border-left: 1px solid #2d2d2d;")
                else:
                    editor.setStyleSheet("background-color: #ffffff; border: 1px solid #e4e4e4; color: #333333;")
                    editor.line_number_area.setStyleSheet("background-color: #f3f3f3;")
                    minimap.setStyleSheet("background-color: #fafafa; border: none; border-left: 1px solid #e4e4e4;")
                editor.highlighter.update_theme(self.theme_is_dark)
                minimap.highlighter.update_theme(self.theme_is_dark)

    def toggle_theme(self):
        self.theme_is_dark = not self.theme_is_dark
        self.apply_theme()
        self.write_system_log(f"Switched theme to {'Dark Mode' if self.theme_is_dark else 'Light Mode'}", success=True)

    def update_compiler_status(self):
        gcc_status = f"GCC: {self.gcc_version.split(') ')[-1] if self.gcc_version else 'Missing'}"
        gpp_status = f"G++: {self.gpp_version.split(') ')[-1] if self.gpp_version else 'Missing'}"
        self.status_bar.showMessage(f"🔍  Compiler Status:  {gcc_status}   |   {gpp_status}")

    def refresh_files(self):
        # Refresh the model index
        self.file_model.setRootPath(self.target_dir)
        self.file_explorer.setRootIndex(self.file_model.index(self.target_dir))
        
        # Verify active files on disk
        for idx in reversed(range(self.editor_tabs.count())):
            tab = self.editor_tabs.widget(idx)
            editor = tab.findChild(CodeEditor)
            if editor and not os.path.exists(editor.filepath):
                self.editor_tabs.removeTab(idx)
                
        self.update_editor_ui_state()

    def filter_files(self):
        query = self.search_input.text().strip().lower()
        if query:
            self.file_model.setNameFilters([f"*{query}*"])
        else:
            self.file_model.setNameFilters(["*.c", "*.cpp", "*.cc", "*.cxx", "*.h", "*.hpp", "*.txt", "*.md"])

    # ==============================================================================
    # 9. Document and Multi-Tab Management
# ==============================================================================
    def get_active_editor(self):
        idx = self.editor_tabs.currentIndex()
        if idx == -1:
            return None
        tab_widget = self.editor_tabs.widget(idx)
        return tab_widget.findChild(CodeEditor)

    def update_editor_ui_state(self):
        """Displays Welcome screen if all files are closed, else displays editor tab view."""
        count = self.editor_tabs.count()
        if count == 0:
            self.workspace_stack.setCurrentIndex(0)  # Show Welcome screen
            self.active_file_lbl.setText("No File Open")
            self.save_btn.setEnabled(False)
            self.save_as_btn.setEnabled(False)
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.cursor_info_lbl.setText("")
        else:
            self.workspace_stack.setCurrentIndex(1)  # Show Tab view
            self.save_btn.setEnabled(True)
            self.save_as_btn.setEnabled(True)
            
            editor = self.get_active_editor()
            if editor:
                self.active_file_lbl.setText(os.path.basename(editor.filepath))
                # Compiler toggles
                ext = os.path.splitext(editor.filepath)[1].lower()
                has_compiler = ext in [".c", ".cpp", ".cc", ".cxx"]
                self.run_btn.setEnabled(has_compiler and not self.is_compiling and not self.is_running_program)
                self.update_statusbar_cursor_info()

    def open_file_by_path(self, filepath):
        """Opens file in a tab, checking if it is already open first."""
        filepath = os.path.abspath(filepath)
        
        # Check if already open
        for idx in range(self.editor_tabs.count()):
            tab_widget = self.editor_tabs.widget(idx)
            editor = tab_widget.findChild(CodeEditor)
            if editor and editor.filepath == filepath:
                self.editor_tabs.setCurrentIndex(idx)
                return
                
        # Create container tab widget
        tab_container = QWidget()
        tab_layout = QHBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        
        # Code Editor
        editor = CodeEditor(self)
        editor.filepath = filepath
        editor.is_dirty = False
        
        # Minimap
        minimap = Minimap(editor)
        
        # Sync scrolling bidirectionally
        editor.verticalScrollBar().valueChanged.connect(minimap.verticalScrollBar().setValue)
        minimap.verticalScrollBar().valueChanged.connect(editor.verticalScrollBar().setValue)
        
        # Sync document contents
        editor.textChanged.connect(lambda e=editor, m=minimap: m.setPlainText(e.toPlainText()))
        
        # Bind Syntax highlighter adaptively
        editor.highlighter = CppSyntaxHighlighter(editor.document(), self.theme_is_dark)
        minimap.highlighter = CppSyntaxHighlighter(minimap.document(), self.theme_is_dark)
        
        # Add Editor and Minimap side-by-side
        tab_layout.addWidget(editor, stretch=8)
        tab_layout.addWidget(minimap, stretch=1)
        
        # Connect editor triggers
        editor.textChanged.connect(lambda e=editor: self.on_editor_modified(e))
        editor.cursorPositionChanged.connect(self.update_statusbar_cursor_info)
        
        # Add tab
        tab_title = os.path.basename(filepath)
        idx = self.editor_tabs.addTab(tab_container, tab_title)
        
        # Load contents
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            editor.blockSignals(True)
            editor.setPlainText(content)
            minimap.setPlainText(content)
            editor.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not open file: {str(e)}")
            self.editor_tabs.removeTab(idx)
            return
            
        self.editor_tabs.setCurrentIndex(idx)
        self.update_editor_ui_state()
        self.apply_theme() # Repaint styles

    def on_editor_modified(self, editor):
        if self.settings.get("auto_save", False):
            try:
                content = editor.toPlainText()
                with open(editor.filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                editor.is_dirty = False
                filename = os.path.basename(editor.filepath)
                for idx in range(self.editor_tabs.count()):
                    tab = self.editor_tabs.widget(idx)
                    if tab.findChild(CodeEditor) == editor:
                        self.editor_tabs.setTabText(idx, filename)
                        break
                if self.get_active_editor() == editor:
                    self.active_file_lbl.setText(filename)
            except Exception:
                pass
            return

        if not editor.is_dirty:
            editor.is_dirty = True
            filename = os.path.basename(editor.filepath)
            # Find active tab index and prepend bullet dot
            for idx in range(self.editor_tabs.count()):
                tab = self.editor_tabs.widget(idx)
                if tab.findChild(CodeEditor) == editor:
                    self.editor_tabs.setTabText(idx, f"• {filename}")
                    break
            self.active_file_lbl.setText(f"• {filename}")

    def save_active_file(self):
        editor = self.get_active_editor()
        if not editor:
            return
            
        try:
            content = editor.toPlainText()
            with open(editor.filepath, "w", encoding="utf-8") as f:
                f.write(content)
                
            editor.is_dirty = False
            filename = os.path.basename(editor.filepath)
            
            # Find active tab index and clear dot bullet
            for idx in range(self.editor_tabs.count()):
                tab = self.editor_tabs.widget(idx)
                if tab.findChild(CodeEditor) == editor:
                    self.editor_tabs.setTabText(idx, filename)
                    break
                    
            self.active_file_lbl.setText(filename)
            self.write_system_log(f"Saved file: {filename}", success=True)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save current document: {str(e)}")

    def save_as_file(self):
        editor = self.get_active_editor()
        if not editor:
            return
            
        filepath, _ = QFileDialog.getSaveFileName(self, "Save File As", self.target_dir, "C/C++ Files (*.c *.cpp *.cc *.cxx *.h *.hpp);;All Files (*.*)")
        if filepath:
            filepath = os.path.abspath(filepath)
            try:
                content = editor.toPlainText()
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                editor.filepath = filepath
                editor.is_dirty = False
                
                # Update tab details
                idx = self.editor_tabs.currentIndex()
                self.editor_tabs.setTabText(idx, os.path.basename(filepath))
                self.active_file_lbl.setText(os.path.basename(filepath))
                
                self.refresh_files()
                self.write_system_log(f"Saved file as: {os.path.basename(filepath)}", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Save As Error", f"Could not save file: {str(e)}")

    def close_tab(self, idx):
        tab_widget = self.editor_tabs.widget(idx)
        editor = tab_widget.findChild(CodeEditor)
        
        if editor and editor.is_dirty:
            confirm = QMessageBox.question(
                self, "Unsaved Changes",
                f"Do you want to save changes to '{os.path.basename(editor.filepath)}' before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if confirm == QMessageBox.StandardButton.Yes:
                # Set active tab temporarily to execute save
                self.editor_tabs.setCurrentIndex(idx)
                self.save_active_file()
            elif confirm == QMessageBox.StandardButton.Cancel:
                return
                
        self.editor_tabs.removeTab(idx)
        self.update_editor_ui_state()

    def on_active_tab_changed(self, idx):
        self.update_editor_ui_state()

    # ==============================================================================
    # 10. File System Explorer Panel Controls
# ==============================================================================
    def new_file(self):
        filename, ok = QInputDialog.getText(self, "New C/C++ File", "Enter file name (e.g., main.cpp):")
        if ok and filename.strip():
            filename = filename.strip()
            filename_lower = filename.lower()
            if not (filename_lower.endswith(".c") or filename_lower.endswith(".cpp") or 
                    filename_lower.endswith(".cc") or filename_lower.endswith(".cxx") or 
                    filename_lower.endswith(".h") or filename_lower.endswith(".hpp")):
                # Match extension of active editor, fallback to .cpp
                editor = self.get_active_editor()
                if editor and editor.filepath.lower().endswith(".c"):
                    ext = ".c"
                else:
                    ext = ".cpp"
                filename += ext
                
            filepath = os.path.join(self.target_dir, filename)
            if os.path.exists(filepath):
                QMessageBox.warning(self, "Warning", "A file with that name already exists!")
                return
                
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("")
                self.refresh_files()
                self.open_file_by_path(filepath)
                self.write_system_log(f"Created file: {filename}", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {str(e)}")

    def rename_file(self):
        editor = self.get_active_editor()
        if not editor:
            QMessageBox.information(self, "Rename File", "Please select an active file tab to rename.")
            return
            
        old_path = editor.filepath
        old_name = os.path.basename(old_path)
        
        new_name, ok = QInputDialog.getText(self, "Rename File", "Enter new name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            new_path = os.path.join(self.target_dir, new_name)
            if os.path.exists(new_path):
                QMessageBox.warning(self, "Warning", "A file with that name already exists!")
                return
                
            try:
                # Save changes
                if editor.is_dirty:
                    self.save_active_file()
                    
                # Close watcher temporarily
                if hasattr(self, 'watcher') and old_path in self.watcher.files():
                    self.watcher.removePath(old_path)
                    
                os.rename(old_path, new_path)
                
                # Update editor filepath properties
                editor.filepath = new_path
                idx = self.editor_tabs.currentIndex()
                self.editor_tabs.setTabText(idx, new_name)
                self.active_file_lbl.setText(new_name)
                
                self.refresh_files()
                self.write_system_log(f"Renamed file '{old_name}' to '{new_name}'", success=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename file: {str(e)}")

    def delete_file(self):
        editor = self.get_active_editor()
        if not editor:
            QMessageBox.information(self, "Delete File", "Please select an active file tab to delete.")
            return
            
        filepath = editor.filepath
        filename = os.path.basename(filepath)
        
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to permanently delete '{filename}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                # Close active tab
                idx = self.editor_tabs.currentIndex()
                editor.is_dirty = False # avoid close confirm
                self.editor_tabs.removeTab(idx)
                
                os.remove(filepath)
                self.refresh_files()
                self.update_editor_ui_state()
                self.write_system_log(f"Deleted file permanently: {filename}", error=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete file: {str(e)}")

    def open_file_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getOpenFileName(self, "Open C/C++ File", self.target_dir, "C/C++ Files (*.c *.cpp *.cc *.cxx *.h *.hpp);;All Files (*.*)")
        if filepath:
            self.open_file_by_path(filepath)

    def select_folder(self):
        from PySide6.QtWidgets import QFileDialog
        selected = QFileDialog.getExistingDirectory(self, "Select Workspace Folder", self.target_dir)
        if selected:
            self.target_dir = os.path.abspath(selected)
            self.dir_path_lbl.setText(self.target_dir)
            
            # Close all active editor tabs
            for _ in range(self.editor_tabs.count()):
                self.editor_tabs.removeTab(0)
                
            self.update_editor_ui_state()
            
            # Reset watcher paths
            if hasattr(self, 'watcher'):
                dirs = self.watcher.directories()
                if dirs:
                    self.watcher.removePaths(dirs)
                self.watcher.addPath(self.target_dir)
                
            self.refresh_files()
            self.write_system_log(f"Loaded workspace folder: {self.target_dir}", success=True)

    def show_find_panel(self):
        self.find_replace_panel.show()
        self.find_replace_panel.find_input.setFocus()
        self.find_replace_panel.find_input.selectAll()

    def show_replace_panel(self):
        self.find_replace_panel.show()
        self.find_replace_panel.find_input.setFocus()
        self.find_replace_panel.find_input.selectAll()

    def toggle_editor_comment(self):
        editor = self.get_active_editor()
        if editor:
            editor.toggle_comment()

    def toggle_editor_block_comment(self):
        editor = self.get_active_editor()
        if editor:
            editor.toggle_block_comment()

    def update_statusbar_cursor_info(self):
        editor = self.get_active_editor()
        if not editor:
            self.cursor_info_lbl.setText("")
            return
            
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        
        ext = os.path.splitext(editor.filepath)[1].lower() if editor.filepath else ""
        lang = "C" if ext == ".c" else ("C++" if ext in [".cpp", ".cc", ".cxx"] else "Plain Text")
        
        self.cursor_info_lbl.setText(f"Ln {line}, Col {col}  |  Spaces: 4  |  UTF-8  |  {lang}")

    # ==============================================================================
    # 11. Compiler and Execution Engines
# ==============================================================================
    def write_system_log(self, text, error=False, success=False):
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        color = "#a1260d" if error else ("#33a06f" if success else ("#569cd6" if self.theme_is_dark else "#0e639c"))
        self.console.insertHtml(f"<div style='color: {color}; font-family: Consolas; font-weight: bold;'>[System] {text}</div><br>")
        self.console.ensureCursorVisible()

    def clear_console(self):
        self.console.clear()

    def update_status(self, status, message=None):
        """Standard status machine managing active panel highlights and lock gates."""
        if status == "Ready":
            self.status_bar.setStyleSheet("background-color: #007acc; color: #ffffff;")
            self.status_bar.showMessage(f"Ready  |  Workspace: {self.target_dir}")
            self.run_btn.setEnabled(self.get_active_editor() is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.file_explorer.setEnabled(True)
            self.new_file_btn.setEnabled(True)
            self.rename_file_btn.setEnabled(True)
            self.delete_file_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(True)
            self.editor_tabs.setEnabled(True)
            editor = self.get_active_editor()
            if editor:
                editor.setEnabled(True)
        elif status == "Compiling":
            self.status_bar.setStyleSheet("background-color: #2b5b84; color: #ffffff;")
            self.status_bar.showMessage(f"🔨 Compiling C/C++ source code...")
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.search_input.setEnabled(False)
            self.file_explorer.setEnabled(False)
            self.new_file_btn.setEnabled(False)
            self.rename_file_btn.setEnabled(False)
            self.delete_file_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.editor_tabs.setEnabled(False)
            editor = self.get_active_editor()
            if editor:
                editor.setEnabled(False)
        elif status == "Running":
            self.status_bar.setStyleSheet("background-color: #d18d00; color: #000000; font-weight: bold;")
            self.status_bar.showMessage(f"🚀 Executing binary in background...")
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stdin_input.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.stdin_input.setFocus()
            self.refresh_btn.setEnabled(False)
            self.search_input.setEnabled(False)
            self.file_explorer.setEnabled(False)
            self.new_file_btn.setEnabled(False)
            self.rename_file_btn.setEnabled(False)
            self.delete_file_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.editor_tabs.setEnabled(False)
            editor = self.get_active_editor()
            if editor:
                editor.setEnabled(False)
        elif status == "Success":
            self.status_bar.setStyleSheet("background-color: #33a06f; color: #ffffff;")
            self.status_bar.showMessage(f"✅ Finished Successfully! " + (message if message else ""))
            self.run_btn.setEnabled(self.get_active_editor() is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.file_explorer.setEnabled(True)
            self.new_file_btn.setEnabled(True)
            self.rename_file_btn.setEnabled(True)
            self.delete_file_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(True)
            self.editor_tabs.setEnabled(True)
            editor = self.get_active_editor()
            if editor:
                editor.setEnabled(True)
        elif status == "Error":
            self.status_bar.setStyleSheet("background-color: #a1260d; color: #ffffff;")
            self.status_bar.showMessage(f"❌ Failed! " + (message if message else ""))
            self.run_btn.setEnabled(self.get_active_editor() is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.file_explorer.setEnabled(True)
            self.new_file_btn.setEnabled(True)
            self.rename_file_btn.setEnabled(True)
            self.delete_file_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(True)
            self.editor_tabs.setEnabled(True)
            editor = self.get_active_editor()
            if editor:
                editor.setEnabled(True)

    def update_time_display(self):
        comp_str = f"Compile: {self.compile_time:.3f}s" if self.compile_time > 0 else "Compile: --s"
        run_str = f"Run: {self.run_time:.3f}s" if self.run_time > 0 else "Run: --s"
        self.time_lbl.setText(f"{comp_str}  |  {run_str}")

    def run_selected_file(self):
        print("RUN CLICKED")
        editor = self.get_active_editor()
        if not editor or self.is_compiling or self.is_running_program:
            return

        # Auto-save changes before compile (VS Code Style)
        if editor.is_dirty:
            self.save_active_file()

        self.clear_console()
        self.compile_time = 0
        self.run_time = 0
        self.update_time_display()
        
        filename = os.path.basename(editor.filepath)
        base_name = os.path.splitext(filename)[0]
        self.is_compiling = True
        self.update_status("Compiling")
        
        self.last_output_binary = os.path.abspath(os.path.join(self.target_dir, f"{base_name}.exe"))
        if os.path.exists(self.last_output_binary):
            try:
                os.remove(self.last_output_binary)
            except Exception:
                self.write_system_log(f"Warning: Binary '{base_name}.exe' is locked. Force killing running instances...", error=True)
                subprocess.run(["taskkill", "/f", "/im", f"{base_name}.exe"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                time.sleep(0.2)
                try:
                    os.remove(self.last_output_binary)
                except Exception as e:
                    self.write_system_log(f"Error: Overwriting target '{base_name}.exe' failed. Details: {str(e)}", error=True)
                    self.is_compiling = False
                    self.update_status("Error", "Output binary locked")
                    return

        ext = os.path.splitext(editor.filepath)[1].lower()
        if ext == ".c":
            compiler_path = self.gcc_path
            compiler_name = "gcc"
            if not compiler_path:
                self.write_system_log("Error: GCC compiler ('gcc') is not detected on your system.", error=True)
                self.write_system_log("Please refer to the Compiler Setup Guide in the README to install it via MSYS2.", error=True)
                self.is_compiling = False
                self.update_status("Error", "GCC compiler missing")
                return
        else:
            compiler_path = self.gpp_path
            compiler_name = "g++"
            if not compiler_path:
                self.write_system_log("Error: G++ compiler ('g++') is not detected on your system.", error=True)
                self.write_system_log("Please refer to the Compiler Setup Guide in the README to install it via MSYS2.", error=True)
                self.is_compiling = False
                self.update_status("Error", "G++ compiler missing")
                return
            
        compile_cmd = [compiler_path, editor.filepath, "-o", self.last_output_binary]
        self.write_system_log(f"Compiling: {compiler_name} {editor.filepath} -o {self.last_output_binary}")
        self.compile_start_time = time.perf_counter()
        
        # Start QProcess Compiler
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.target_dir)
        self.process.readyReadStandardOutput.connect(self.read_compiler_stdout)
        self.process.readyReadStandardError.connect(self.read_compiler_stderr)
        self.process.finished.connect(self.compile_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        
        self.process.start(compiler_path, compile_cmd[1:])

    def on_process_error(self, error):
        error_str = "Unknown error occurred during execution."
        if error == QProcess.ProcessError.FailedToStart:
            error_str = "The compiler or target binary failed to start. Verify your compiler paths, standard formats, or antivirus settings."
        elif error == QProcess.ProcessError.Crashed:
            error_str = "The running process crashed or exited abnormally."
        elif error == QProcess.ProcessError.Timedout:
            error_str = "The process timed out."
        elif error == QProcess.ProcessError.WriteError:
            error_str = "Failed to write data to standard input (stdin)."
        elif error == QProcess.ProcessError.ReadError:
            error_str = "An error occurred while reading from the process stream."
            
        self.write_system_log(f"Execution Error: {error_str}", error=True)
        self.is_compiling = False
        self.is_running_program = False
        self.update_status("Error", "Execution failed")
        self.process = None

    def read_compiler_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible()

    def read_compiler_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertHtml(f"<span style='color: #f48771; font-family: Consolas;'>{data.replace('\n', '<br>')}</span>")
        self.console.ensureCursorVisible()

    def compile_finished(self, exit_code, exit_status):
        self.compile_time = time.perf_counter() - self.compile_start_time
        self.update_time_display()
        self.is_compiling = False
        
        if exit_code == 0:
            self.write_system_log(f"Compilation finished successfully in {self.compile_time:.3f} seconds.", success=True)
            self.run_compiled_binary()
        else:
            self.write_system_log(f"Compilation failed with exit code {exit_code}.", error=True)
            self.update_status("Error", f"Compiler failed (Code {exit_code})")
            self.process = None

    def run_compiled_binary(self):
        self.is_running_program = True
        self.update_status("Running")
        
        if not hasattr(self, 'last_output_binary') or not os.path.exists(self.last_output_binary):
            self.write_system_log("Error: Compiled binary was not found.", error=True)
            self.update_status("Error", "Binary missing")
            self.is_running_program = False
            return
            
        self.write_system_log(f"Executing: {os.path.basename(self.last_output_binary)}")
        self.run_start_time = time.perf_counter()
        
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.target_dir)
        self.process.readyReadStandardOutput.connect(self.read_program_stdout)
        self.process.readyReadStandardError.connect(self.read_program_stderr)
        self.process.finished.connect(self.program_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        
        self.process.start(self.last_output_binary, [])

    def read_program_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible()

    def read_program_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertHtml(f"<span style='color: #e57373; font-family: Consolas;'>{data.replace('\n', '<br>')}</span>")
        self.console.ensureCursorVisible()

    def send_stdin(self):
        if not self.process or not self.is_running_program:
            return
            
        input_text = self.stdin_input.text()
        self.process.write(input_text.encode('utf-8') + b'\n')
        
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertHtml(f"<span style='color: #4ec9b0; font-family: Consolas; font-weight: bold;'>{input_text}</span><br>")
        self.console.ensureCursorVisible()
        self.stdin_input.clear()

    def program_finished(self, exit_code, exit_status):
        self.run_time = time.perf_counter() - self.run_start_time
        self.update_time_display()
        self.is_running_program = False
        
        if exit_code == 0:
            self.write_system_log(f"Program executed successfully in {self.run_time:.3f} seconds.", success=True)
            self.update_status("Success", f"Exit code {exit_code}")
        else:
            self.write_system_log(f"Program terminated with exit code {exit_code}.", error=True)
            self.update_status("Error", f"Exit code {exit_code}")
            
        self.process = None

    def terminate_process(self):
        if not self.process:
            return
            
        self.write_system_log("Terminating process forcefully...", error=True)
        self.process.kill()
        
        if self.is_compiling:
            self.is_compiling = False
            self.compile_time = time.perf_counter() - self.compile_start_time
            self.update_status("Error", "Compilation interrupted")
        elif self.is_running_program:
            self.is_running_program = False
            self.run_time = time.perf_counter() - self.run_start_time
            self.update_status("Error", "Program interrupted")
            
        self.update_time_display()
        self.process = None

    def closeEvent(self, event):
        """Triggers check for unsaved edits on closing application."""
        unsaved = []
        for idx in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(idx)
            editor = tab.findChild(CodeEditor)
            if editor and editor.is_dirty:
                unsaved.append(editor)
                
        if unsaved:
            confirm = QMessageBox.question(
                self, "Unsaved Changes",
                f"You have unsaved changes in {len(unsaved)} file(s). Do you want to save them before exiting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if confirm == QMessageBox.StandardButton.Yes:
                # Save all
                for editor in unsaved:
                    try:
                        content = editor.toPlainText()
                        with open(editor.filepath, "w", encoding="utf-8") as f:
                            f.write(content)
                    except Exception:
                        pass
                event.accept()
            elif confirm == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
                
        if self.process:
            self.process.kill()
        event.accept()


# ==============================================================================
# 12. Main Execution Hook
# ==============================================================================
def main():
    app = QApplication(sys.argv)
    
    # Check if target directory is passed via terminal argument
    target_dir = None
    if len(sys.argv) > 1:
        potential_dir = sys.argv[1]
        if os.path.isdir(potential_dir):
            target_dir = potential_dir
            
    window = CoderunApp(target_dir)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
