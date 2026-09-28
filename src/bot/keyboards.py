"""Inline keyboard builders."""

from typing import List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import strings


class KeyboardBuilder:
    """Build inline keyboards for bot interactions."""

    @staticmethod
    def build_main_menu() -> InlineKeyboardMarkup:
        """
        Build main menu keyboard with available commands.

        Returns:
            InlineKeyboardMarkup with command options
        """
        keyboard = [
            [InlineKeyboardButton(
                strings.MENU_BUTTONS["emoji_cropper"],
                callback_data="cmd_emoji_cropper"
            )],
            [InlineKeyboardButton(
                strings.MENU_BUTTONS["help"],
                callback_data="cmd_help"
            )],
        ]

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_back_to_menu() -> InlineKeyboardMarkup:
        """
        Build keyboard with back to menu button.

        Returns:
            InlineKeyboardMarkup with back button
        """
        keyboard = [
            [InlineKeyboardButton(
                strings.MENU_BUTTONS["back_to_menu"],
                callback_data="cmd_start"
            )],
        ]

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_grid_selection(grid_sizes: List[Tuple[int, int]]) -> InlineKeyboardMarkup:
        """
        Build keyboard for grid size selection.

        Args:
            grid_sizes: List of (cols, rows) tuples

        Returns:
            InlineKeyboardMarkup with grid options
        """
        keyboard = [[InlineKeyboardButton(
            strings.GRID_WHOLE_IMAGE,
            callback_data="grid_1x1"
        )]]
        for cols, rows in grid_sizes:
            text = f"{cols}x{rows} ({cols * rows} эмодзи)"
            callback_data = f"grid_{cols}x{rows}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_padding_selection() -> InlineKeyboardMarkup:
        """
        Build keyboard for padding selection.

        Returns:
            InlineKeyboardMarkup with padding options
        """
        keyboard = [
            [InlineKeyboardButton("1 - Минимальный", callback_data="padding_1")],
            [InlineKeyboardButton("2 - Маленький", callback_data="padding_2")],
            [InlineKeyboardButton("3 - Средний", callback_data="padding_3")],
            [InlineKeyboardButton("4 - Большой", callback_data="padding_4")],
            [InlineKeyboardButton("5 - Максимальный", callback_data="padding_5")],
        ]

        return InlineKeyboardMarkup(keyboard)
