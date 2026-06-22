import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from automation.desktop.file_operations import FileOperations

@pytest.fixture
def file_ops():
    return FileOperations()

@patch("automation.desktop.file_operations.subprocess.Popen")
@patch("automation.desktop.window_manager.WindowManager")
@patch("automation.desktop.app_controller.AppController")
def test_open_folder_alias(mock_app_ctrl, mock_wm, mock_popen, file_ops):
    """Test opening a well-known Windows folder alias."""
    mock_app_ctrl_instance = MagicMock()
    mock_app_ctrl_instance.navigate_file_dialog.return_value = False
    mock_app_ctrl.return_value = mock_app_ctrl_instance
    
    mock_wm_instance = MagicMock()
    mock_wm.return_value = mock_wm_instance

    res = file_ops.open_folder("downloads")
    
    # It should have mapped 'downloads' to 'shell:Downloads'
    mock_popen.assert_called_once_with(["explorer", "shell:Downloads"])
    assert "Downloads" in res

@patch("automation.desktop.file_operations.get_indexer")
@patch("automation.desktop.file_operations.os.startfile")
@patch("automation.desktop.window_manager.WindowManager")
@patch("automation.desktop.app_controller.AppController")
def test_search_file_exact_match(mock_app_ctrl, mock_wm, mock_startfile, mock_get_indexer, file_ops):
    """Test searching and opening a file by exact name match."""
    mock_app_ctrl_instance = MagicMock()
    mock_app_ctrl_instance.navigate_file_dialog.return_value = False
    mock_app_ctrl.return_value = mock_app_ctrl_instance

    mock_indexer = MagicMock()
    # Mock finding exactly one result
    mock_indexer.search.return_value = [{"name": "test_doc.txt", "path": "C:\\test_doc.txt"}]
    mock_get_indexer.return_value = mock_indexer
    
    res = file_ops.search_file("test_doc.txt")
    
    mock_startfile.assert_called_once_with("C:\\test_doc.txt")
    assert "Opened test_doc.txt" in res

@patch("automation.desktop.file_operations.Path.mkdir")
def test_create_folder(mock_mkdir, file_ops):
    """Test folder creation fallback to Desktop."""
    res = file_ops.create_folder("new_project")
    mock_mkdir.assert_called_once()
    assert "Created folder:" in res

@patch("automation.desktop.file_operations.get_indexer")
@patch("send2trash.send2trash")
def test_delete_target(mock_send2trash, mock_get_indexer, file_ops):
    """Test moving a file to the recycle bin."""
    mock_indexer = MagicMock()
    mock_indexer.search.return_value = [{"name": "junk.txt", "path": "C:\\junk.txt"}]
    mock_get_indexer.return_value = mock_indexer

    res = file_ops.delete_target("junk.txt")
    
    mock_send2trash.assert_called_once_with("C:\\junk.txt")
    assert "Moved" in res
