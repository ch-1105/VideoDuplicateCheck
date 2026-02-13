import os
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.comparator import DuplicateGroup
from ..utils.file_utils import delete_file, move_file, move_to_recycle_bin


class ResultPanel(QWidget):
    preview_requested = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self._groups: list[DuplicateGroup] = []

        layout = QVBoxLayout(self)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["文件", "分辨率", "码率", "大小(MB)", "建议"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self._emit_preview)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        actions = QHBoxLayout()
        self.prev_btn = QPushButton("上一条", self)
        self.next_btn = QPushButton("下一条", self)
        self.smart_select_btn = QPushButton("智能勾选可删除", self)
        self.move_btn = QPushButton("移动选中", self)
        self.delete_btn = QPushButton("删除到回收站", self)
        self.permanent_delete_btn = QPushButton("永久删除", self)
        self.play_btn = QPushButton("播放选中", self)
        self.open_dir_btn = QPushButton("打开目录", self)
        self.export_csv_btn = QPushButton("导出 CSV", self)
        self.export_json_btn = QPushButton("导出 JSON", self)

        self.prev_btn.clicked.connect(lambda: self._navigate_in_group(-1))
        self.next_btn.clicked.connect(lambda: self._navigate_in_group(1))
        self.smart_select_btn.clicked.connect(self._smart_select_deletable)
        self.move_btn.clicked.connect(self._move_selected)
        self.delete_btn.clicked.connect(self._delete_selected_to_recycle)
        self.permanent_delete_btn.clicked.connect(self._delete_selected_permanent)
        self.play_btn.clicked.connect(self._play_selected)
        self.open_dir_btn.clicked.connect(self._open_selected_parent)
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_json_btn.clicked.connect(self._export_json)

        actions.addWidget(self.prev_btn)
        actions.addWidget(self.next_btn)
        actions.addWidget(self.smart_select_btn)
        actions.addWidget(self.move_btn)
        actions.addWidget(self.delete_btn)
        actions.addWidget(self.permanent_delete_btn)
        actions.addWidget(self.play_btn)
        actions.addWidget(self.open_dir_btn)
        actions.addWidget(self.export_csv_btn)
        actions.addWidget(self.export_json_btn)
        layout.addLayout(actions)

    def set_groups(self, groups: list[DuplicateGroup]) -> None:
        self._groups = groups
        self.tree.clear()

        for group_index, group in enumerate(groups, start=1):
            root = QTreeWidgetItem(
                [f"第 {group_index} 组 (相似度 {group.similarity:.2f})", "", "", "", ""]
            )
            self.tree.addTopLevelItem(root)

            for item in group.items:
                is_keep = item.path == group.recommended_keep.path
                child = QTreeWidgetItem(
                    [
                        str(item.path),
                        f"{item.width}x{item.height}",
                        str(item.bitrate),
                        f"{item.size_bytes / (1024 * 1024):.2f}",
                        "保留" if is_keep else "可删除",
                    ]
                )
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                root.addChild(child)
            root.setExpanded(True)

    def _selected_paths(self) -> list[Path]:
        selected: list[Path] = []
        for node in self.tree.selectedItems():
            if node.parent() is None:
                continue
            selected.append(Path(node.text(0)))
        return selected

    def _first_selected_path(self) -> Path | None:
        selected = self._selected_paths()
        return selected[0] if selected else None

    def _checked_paths(self) -> list[Path]:
        checked: list[Path] = []
        for group_index in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(group_index)
            if root is None:
                continue
            for item_idx in range(root.childCount()):
                child = root.child(item_idx)
                if child.checkState(0) == Qt.CheckState.Checked:
                    checked.append(Path(child.text(0)))
        return checked

    def _target_paths(self) -> list[Path]:
        checked = self._checked_paths()
        if checked:
            return checked
        return self._selected_paths()

    def _move_selected(self) -> None:
        selected = self._target_paths()
        if not selected:
            return
        dst = QFileDialog.getExistingDirectory(self, "选择移动目标目录")
        if not dst:
            return
        for path in selected:
            if path.exists():
                move_file(path, Path(dst))

    def _delete_selected_to_recycle(self) -> None:
        selected = self._target_paths()
        if not selected:
            return

        answer = QMessageBox.question(
            self,
            "删除确认",
            f"将 {len(selected)} 个文件移动到回收站？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        success = 0
        for path in selected:
            if path.exists() and move_to_recycle_bin(path):
                success += 1

        QMessageBox.information(
            self,
            "回收站删除完成",
            f"已移动到回收站: {success}/{len(selected)}",
        )

    def _delete_selected_permanent(self) -> None:
        selected = self._target_paths()
        if not selected:
            return

        first_confirm = QMessageBox.warning(
            self,
            "永久删除",
            f"你即将永久删除 {len(selected)} 个文件，此操作不可恢复。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first_confirm != QMessageBox.StandardButton.Yes:
            return

        second_confirm = QMessageBox.warning(
            self,
            "二次确认",
            "请再次确认：是否永久删除这些文件？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if second_confirm != QMessageBox.StandardButton.Yes:
            return

        success = 0
        for path in selected:
            if path.exists():
                delete_file(path)
                success += 1

        QMessageBox.information(
            self,
            "永久删除完成",
            f"已永久删除: {success}/{len(selected)}",
        )

    def _play_selected(self) -> None:
        selected = self._first_selected_path()
        if selected is None or not selected.exists():
            return
        os.startfile(str(selected))

    def _open_selected_parent(self) -> None:
        selected = self._first_selected_path()
        if selected is None:
            return
        parent = selected.parent
        if parent.exists():
            os.startfile(str(parent))

    def _emit_preview(self) -> None:
        selected = self._first_selected_path()
        if selected is not None:
            self.preview_requested.emit(selected)

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is not None:
            self.tree.clearSelection()
            self.tree.setCurrentItem(item)
            item.setSelected(True)

        menu = QMenu(self.tree)
        play_action = menu.addAction("播放")
        open_dir_action = menu.addAction("打开目录")
        menu.addSeparator()
        check_action = menu.addAction("勾选")
        uncheck_action = menu.addAction("取消勾选")
        menu.addSeparator()
        recycle_action = menu.addAction("删除到回收站")
        permanent_action = menu.addAction("永久删除")

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == play_action:
            self._play_selected()
        elif chosen == open_dir_action:
            self._open_selected_parent()
        elif chosen == check_action:
            self._set_checked_for_selection(Qt.CheckState.Checked)
        elif chosen == uncheck_action:
            self._set_checked_for_selection(Qt.CheckState.Unchecked)
        elif chosen == recycle_action:
            self._delete_selected_to_recycle()
        elif chosen == permanent_action:
            self._delete_selected_permanent()

    def _set_checked_for_selection(self, state: Qt.CheckState) -> None:
        items = self.tree.selectedItems()
        for item in items:
            if item.parent() is None:
                for idx in range(item.childCount()):
                    item.child(idx).setCheckState(0, state)
            else:
                item.setCheckState(0, state)

    def _smart_select_deletable(self) -> None:
        for group_index, group in enumerate(self._groups):
            root = self.tree.topLevelItem(group_index)
            if root is None:
                continue
            keep = str(group.recommended_keep.path)
            for idx in range(root.childCount()):
                child = root.child(idx)
                child_path = child.text(0)
                state = Qt.CheckState.Unchecked if child_path == keep else Qt.CheckState.Checked
                child.setCheckState(0, state)

    def _group_children(self, root: QTreeWidgetItem) -> list[QTreeWidgetItem]:
        return [root.child(idx) for idx in range(root.childCount())]

    def _first_leaf_item(self) -> QTreeWidgetItem | None:
        if self.tree.topLevelItemCount() == 0:
            return None
        first_group = self.tree.topLevelItem(0)
        if first_group is None or first_group.childCount() == 0:
            return None
        return first_group.child(0)

    def _select_item(self, item: QTreeWidgetItem) -> None:
        self.tree.clearSelection()
        item.setSelected(True)
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)

    def _navigate_in_group(self, step: int) -> None:
        current = self.tree.currentItem()
        if current is None or current.parent() is None:
            first = self._first_leaf_item()
            if first is not None:
                self._select_item(first)
            return

        root = current.parent()
        children = self._group_children(root)
        if not children:
            return

        current_idx = children.index(current)
        target_idx = current_idx + step
        if target_idx < 0:
            target_idx = 0
        if target_idx >= len(children):
            target_idx = len(children) - 1

        self._select_item(children[target_idx])

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", filter="CSV Files (*.csv)")
        if not path:
            return

        lines = ["group,similarity,path,width,height,bitrate,size_bytes,recommend_keep"]
        for idx, group in enumerate(self._groups, start=1):
            for item in group.items:
                keep = int(item.path == group.recommended_keep.path)
                lines.append(
                    f'{idx},{group.similarity:.4f},"{item.path}",{item.width},{item.height},{item.bitrate},{item.size_bytes},{keep}'
                )

        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 JSON", filter="JSON Files (*.json)")
        if not path:
            return

        data = []
        for idx, group in enumerate(self._groups, start=1):
            data.append(
                {
                    "group": idx,
                    "similarity": group.similarity,
                    "recommended_keep": str(group.recommended_keep.path),
                    "items": [
                        {
                            "path": str(item.path),
                            "width": item.width,
                            "height": item.height,
                            "bitrate": item.bitrate,
                            "size_bytes": item.size_bytes,
                        }
                        for item in group.items
                    ],
                }
            )

        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
