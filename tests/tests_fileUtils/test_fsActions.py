#!/usr/bin/env python3
"""
test_fsActions.py - Comprehensive Tests for fsActions.py

Tests the enhanced file system operations including move, copy, delete,
permission management, and filtering integration.
"""

import os
import pytest
import tempfile
import shutil
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock, call

# Import the modules under test
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from file_utils.fsActions import (
    FileSystemActions, create_filter_from_args, process_actions_pipeline
)
from file_utils.fsFilters import FileSystemFilter


class TestFileSystemActions:
    """Test suite for FileSystemActions class."""
    
    def setup_method(self):
        """Set up test environment for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_source = Path(self.temp_dir) / "source"
        self.test_dest = Path(self.temp_dir) / "dest"
        self.test_source.mkdir()
        self.test_dest.mkdir()
        
        # Create test files
        self.test_file = self.test_source / "test.txt"
        self.test_file.write_text("Test content")
        
        self.test_dir = self.test_source / "subdir"
        self.test_dir.mkdir()
        (self.test_dir / "nested.txt").write_text("Nested content")
        
        self.actions = FileSystemActions(dry_run=True)
    
    def teardown_method(self):
        """Clean up test environment after each test method."""
        shutil.rmtree(self.temp_dir)
    
    def test_init_default_dry_run(self):
        """Test FileSystemActions initialization with default dry_run."""
        actions = FileSystemActions()
        assert actions.dry_run is True
    
    def test_init_with_dry_run_false(self):
        """Test FileSystemActions initialization with dry_run=False."""
        actions = FileSystemActions(dry_run=False)
        assert actions.dry_run is False
    
    def test_init_stats_structure(self):
        """Test that stats dictionary is properly initialized."""
        actions = FileSystemActions()
        expected_keys = ['moved', 'copied', 'deleted', 'errors', 'skipped']
        assert all(key in actions.stats for key in expected_keys)
        assert all(actions.stats[key] == 0 for key in expected_keys)
    
    def test_create_target_path_flat_structure(self):
        """Test creating target path with flat structure (default)."""
        source = Path("/source/dir/file.txt")
        destination = Path("/dest")
        
        result = self.actions.create_target_path(source, destination)
        expected = Path("/dest/file.txt")
        assert result == expected
    
    def test_create_target_path_with_dir_structure(self):
        """Test creating target path preserving directory structure."""
        source = Path("/project/src/utils/file.txt")
        destination = Path("/backup")
        base_path = Path("/project")
        
        result = self.actions.create_target_path(source, destination, with_dir=True, base_path=base_path)
        expected = Path("/backup/src/utils/file.txt")
        assert result == expected
    
    def test_create_target_path_with_dir_fallback(self):
        """Test target path creation fallback when relative path fails."""
        source = Path("/other/file.txt")
        destination = Path("/dest")
        base_path = Path("/project")  # source not under base_path
        
        result = self.actions.create_target_path(source, destination, with_dir=True, base_path=base_path)
        expected = Path("/dest/file.txt")  # Should fallback to flat structure
        assert result == expected
    
    def test_move_file_dry_run(self):
        """Test move_file in dry-run mode."""
        source = self.test_file
        target = self.test_dest / "moved.txt"
        
        result = self.actions.move_file(source, target, dry_run=True)
        
        assert result is True
        assert source.exists()  # Source should still exist in dry-run
        assert not target.exists()  # Target should not be created
        assert self.actions.stats['moved'] == 1
    
    @patch('file_utils.fsActions.shutil.move')
    def test_move_file_execute(self, mock_move):
        """Test move_file in execute mode."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/file.txt")
        target = Path("/dest/file.txt")
        
        # Mock target parent mkdir
        with patch.object(target.parent, 'mkdir'):
            result = actions.move_file(source, target, dry_run=False)
        
        assert result is True
        mock_move.assert_called_once_with(str(source), str(target))
        assert actions.stats['moved'] == 1
    
    def test_move_file_target_exists_conflict(self):
        """Test move_file when target already exists."""
        # Create existing target
        target = self.test_dest / "test.txt"
        target.write_text("Existing content")
        
        result = self.actions.move_file(self.test_file, target, dry_run=True)
        
        assert result is True
        assert self.actions.stats['moved'] == 1
    
    def test_move_file_permission_error(self):
        """Test move_file handling permission errors."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/file.txt")
        target = Path("/dest/file.txt")
        
        with patch('file_utils.fsActions.shutil.move', side_effect=PermissionError("Access denied")):
            with patch.object(target.parent, 'mkdir'):
                result = actions.move_file(source, target, dry_run=False)
        
        assert result is False
        assert actions.stats['errors'] == 1
    
    def test_copy_file_dry_run(self):
        """Test copy_file in dry-run mode."""
        source = self.test_file
        target = self.test_dest / "copied.txt"
        
        result = self.actions.copy_file(source, target, dry_run=True)
        
        assert result is True
        assert source.exists()  # Source should still exist
        assert not target.exists()  # Target should not be created in dry-run
        assert self.actions.stats['copied'] == 1
    
    @patch('file_utils.fsActions.shutil.copy2')
    def test_copy_file_execute(self, mock_copy):
        """Test copy_file in execute mode."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/file.txt")
        target = Path("/dest/file.txt")
        
        # Mock source as file
        with patch.object(source, 'is_dir', return_value=False):
            with patch.object(target.parent, 'mkdir'):
                result = actions.copy_file(source, target, dry_run=False)
        
        assert result is True
        mock_copy.assert_called_once_with(source, target)
        assert actions.stats['copied'] == 1
    
    @patch('file_utils.fsActions.shutil.copytree')
    def test_copy_directory_execute(self, mock_copytree):
        """Test copy_file with directory in execute mode."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/dir")
        target = Path("/dest/dir")
        
        # Mock source as directory
        with patch.object(source, 'is_dir', return_value=True):
            with patch.object(target.parent, 'mkdir'):
                result = actions.copy_file(source, target, dry_run=False)
        
        assert result is True
        mock_copytree.assert_called_once_with(source, target, dirs_exist_ok=True)
        assert actions.stats['copied'] == 1
    
    def test_delete_file_dry_run(self):
        """Test delete_file in dry-run mode."""
        source = self.test_file
        
        result = self.actions.delete_file(source, dry_run=True)
        
        assert result is True
        assert source.exists()  # File should still exist in dry-run
        assert self.actions.stats['deleted'] == 1
    
    @patch('file_utils.fsActions.Path.unlink')
    def test_delete_file_execute(self, mock_unlink):
        """Test delete_file in execute mode."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/file.txt")
        
        # Mock source as file
        with patch.object(source, 'is_dir', return_value=False):
            result = actions.delete_file(source, dry_run=False)
        
        assert result is True
        mock_unlink.assert_called_once()
        assert actions.stats['deleted'] == 1
    
    @patch('file_utils.fsActions.shutil.rmtree')
    def test_delete_directory_execute(self, mock_rmtree):
        """Test delete_file with directory in execute mode."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/dir")
        
        # Mock source as directory
        with patch.object(source, 'is_dir', return_value=True):
            result = actions.delete_file(source, dry_run=False)
        
        assert result is True
        mock_rmtree.assert_called_once_with(source)
        assert actions.stats['deleted'] == 1
    
    def test_delete_file_permission_error(self):
        """Test delete_file handling permission errors."""
        actions = FileSystemActions(dry_run=False)
        source = Path("/source/file.txt")
        
        # Mock source as file and unlink to raise PermissionError
        with patch.object(source, 'is_dir', return_value=False):
            with patch.object(source, 'unlink', side_effect=PermissionError("Access denied")):
                result = actions.delete_file(source, dry_run=False)
        
        assert result is False
        assert actions.stats['errors'] == 1
    
    def test_set_permissions_dry_run(self):
        """Test set_permissions in dry-run mode."""
        path = self.test_file
        
        result = self.actions.set_permissions(path, "755", dry_run=True)
        
        assert result is True
        # In dry-run, permissions shouldn't actually change
    
    @patch('file_utils.fsActions.Path.chmod')
    def test_set_permissions_execute(self, mock_chmod):
        """Test set_permissions in execute mode."""
        actions = FileSystemActions(dry_run=False)
        path = Path("/test/file.txt")
        
        result = actions.set_permissions(path, "755", dry_run=False)
        
        assert result is True
        expected_mode = int("755", 8)
        mock_chmod.assert_called_once_with(expected_mode)
    
    def test_set_permissions_invalid_mode(self):
        """Test set_permissions with invalid permission mode."""
        actions = FileSystemActions(dry_run=False)
        path = Path("/test/file.txt")
        
        # Mock chmod to raise ValueError for invalid mode
        with patch.object(path, 'chmod', side_effect=ValueError("invalid mode")):
            result = actions.set_permissions(path, "invalid", dry_run=False)
        
        assert result is False
        assert actions.stats['errors'] == 1
    
    @patch('file_utils.fsActions.os.utime')
    def test_set_attributes_execute(self, mock_utime):
        """Test set_attributes in execute mode."""
        actions = FileSystemActions(dry_run=False)
        path = Path("/test/file.txt")
        attributes = {'atime': '1640995200', 'mtime': '1640995200'}
        
        # Mock stat for existing times
        mock_stat = Mock()
        mock_stat.st_atime = 1640995200
        mock_stat.st_mtime = 1640995200
        
        with patch.object(path, 'stat', return_value=mock_stat):
            result = actions.set_attributes(path, attributes, dry_run=False)
        
        assert result is True
        mock_utime.assert_called_once_with(path, (1640995200.0, 1640995200.0))
    
    def test_set_attributes_dry_run(self):
        """Test set_attributes in dry-run mode."""
        path = self.test_file
        attributes = {'mtime': '1640995200'}
        
        result = self.actions.set_attributes(path, attributes, dry_run=True)
        
        assert result is True
    
    def test_merge_directories(self):
        """Test merging directories functionality."""
        source_dir = self.test_source / "merge_source"
        target_dir = self.test_dest / "merge_target"
        
        # Create source and target directories with files
        source_dir.mkdir()
        target_dir.mkdir()
        (source_dir / "file1.txt").write_text("Content 1")
        (source_dir / "file2.txt").write_text("Content 2")
        (target_dir / "existing.txt").write_text("Existing content")
        
        # Test in dry-run mode
        self.actions.merge_directories(source_dir, target_dir, dry_run=True)
        
        # In dry-run, files should remain unchanged
        assert (source_dir / "file1.txt").exists()
        assert (target_dir / "existing.txt").exists()
    
    def test_print_stats(self, capsys):
        """Test print_stats output."""
        self.actions.stats['moved'] = 5
        self.actions.stats['copied'] = 3
        self.actions.stats['errors'] = 1
        
        self.actions.print_stats()
        
        captured = capsys.readouterr()
        assert "Operation Statistics" in captured.err
        assert "Moved: 5" in captured.err
        assert "Copied: 3" in captured.err
        assert "Errors: 1" in captured.err
    
    def test_print_stats_no_operations(self, capsys):
        """Test print_stats when no operations performed."""
        # All stats remain 0
        self.actions.print_stats()
        
        captured = capsys.readouterr()
        assert captured.err == ""  # Should not print anything


class TestFilterIntegration:
    """Test suite for filter integration with fsActions."""
    
    def test_create_filter_from_args_no_filters(self):
        """Test creating filter when no filter args provided."""
        mock_args = Mock()
        mock_args.filter_file = None
        mock_args.size_gt = None
        mock_args.size_lt = None
        mock_args.modified_after = None
        mock_args.modified_before = None
        mock_args.file_pattern_filter = []
        mock_args.dir_pattern_filter = []
        mock_args.pattern_filter = None
        mock_args.file_ignore = []
        mock_args.dir_ignore = []
        mock_args.ignore_filter = None
        mock_args.type_filter = []
        mock_args.extension_filter = []
        mock_args.git_ignore_filter = False
        
        result = create_filter_from_args(mock_args)
        assert result is None
    
    def test_create_filter_from_args_with_filters(self):
        """Test creating filter when filter args provided."""
        mock_args = Mock()
        mock_args.filter_file = None
        mock_args.size_gt = '1M'
        mock_args.size_lt = None
        mock_args.size_eq = None
        mock_args.modified_after = '7d'
        mock_args.modified_before = None
        mock_args.created_after = None
        mock_args.created_before = None
        mock_args.file_pattern_filter = ['*.py']
        mock_args.dir_pattern_filter = []
        mock_args.pattern_filter = None
        mock_args.file_ignore = []
        mock_args.dir_ignore = []
        mock_args.ignore_filter = None
        mock_args.type_filter = ['image']
        mock_args.extension_filter = []
        mock_args.git_ignore_filter = False
        
        result = create_filter_from_args(mock_args)
        assert isinstance(result, FileSystemFilter)
        assert len(result.size_filters) == 1
        assert len(result.date_filters) == 1
        assert result.file_patterns == ['*.py']
        assert result.type_filters == ['image']
    
    @patch('file_utils.fsActions.yaml.safe_load')
    @patch('builtins.open', mock_open(read_data='size_gt: "1M"\nfile_patterns:\n  - "*.py"'))
    def test_create_filter_from_config_file(self, mock_yaml_load):
        """Test creating filter from configuration file."""
        mock_yaml_load.return_value = {
            'size_gt': '1M',
            'file_patterns': ['*.py']
        }
        
        mock_args = Mock()
        mock_args.filter_file = 'test.yml'
        # Set all other filter args to None/empty
        for attr in ['size_gt', 'size_lt', 'size_eq', 'modified_after', 'modified_before',
                     'created_after', 'created_before', 'pattern_filter', 'ignore_filter',
                     'git_ignore_filter']:
            setattr(mock_args, attr, None if 'filter' in attr else None)
        
        for attr in ['file_pattern_filter', 'dir_pattern_filter', 'file_ignore',
                     'dir_ignore', 'type_filter', 'extension_filter']:
            setattr(mock_args, attr, [])
        
        mock_args.git_ignore_filter = False
        
        result = create_filter_from_args(mock_args)
        assert isinstance(result, FileSystemFilter)


class TestPipelineProcessing:
    """Test suite for pipeline processing functionality."""
    
    @patch('file_utils.fsActions.get_file_paths_from_input')
    @patch('file_utils.fsActions.sys.argv', ['fsActions.py', '--help-examples'])
    def test_process_actions_pipeline_help_examples(self, mock_get_paths):
        """Test process_actions_pipeline with help examples."""
        mock_args = Mock()
        mock_args.help_examples = True
        mock_args.help_verbose = False
        
        with patch('file_utils.fsActions.show_examples') as mock_show:
            process_actions_pipeline(mock_args)
            mock_show.assert_called_once()
    
    @patch('file_utils.fsActions.get_file_paths_from_input')
    def test_process_actions_pipeline_no_action(self, mock_get_paths):
        """Test process_actions_pipeline with no action specified."""
        mock_get_paths.return_value = (['test.txt'], False)
        
        mock_args = Mock()
        mock_args.help_examples = False
        mock_args.help_verbose = False
        mock_args.move = None
        mock_args.copy = None
        mock_args.delete = False
        
        with patch('builtins.print') as mock_print:
            process_actions_pipeline(mock_args)
            
        # Should print error about no action specified
        mock_print.assert_called()
        error_calls = [call for call in mock_print.call_args_list 
                      if "No action specified" in str(call)]
        assert len(error_calls) > 0
    
    @patch('file_utils.fsActions.get_file_paths_from_input')
    def test_process_actions_pipeline_multiple_actions(self, mock_get_paths):
        """Test process_actions_pipeline with multiple actions specified."""
        mock_get_paths.return_value = (['test.txt'], False)
        
        mock_args = Mock()
        mock_args.help_examples = False
        mock_args.help_verbose = False
        mock_args.move = '/dest'
        mock_args.copy = '/dest'
        mock_args.delete = False
        
        with patch('builtins.print') as mock_print:
            process_actions_pipeline(mock_args)
            
        # Should print error about multiple actions
        error_calls = [call for call in mock_print.call_args_list 
                      if "Multiple actions" in str(call)]
        assert len(error_calls) > 0
    
    @patch('file_utils.fsActions.get_file_paths_from_input')
    def test_process_actions_pipeline_no_files(self, mock_get_paths):
        """Test process_actions_pipeline with no input files."""
        mock_get_paths.return_value = ([], False)
        
        mock_args = Mock()
        mock_args.help_examples = False
        mock_args.help_verbose = False
        mock_args.move = '/dest'
        mock_args.copy = None
        mock_args.delete = False
        
        with patch('builtins.print') as mock_print:
            process_actions_pipeline(mock_args)
            
        # Should print message about no input files
        error_calls = [call for call in mock_print.call_args_list 
                      if "No input files" in str(call)]
        assert len(error_calls) > 0


class TestMoveOperationIntegration:
    """Integration tests for move operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.dest_dir = Path(self.temp_dir) / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
        
        # Create test file structure
        self.test_file = self.source_dir / "test.txt"
        self.test_file.write_text("Test content")
        
        self.sub_dir = self.source_dir / "subdir"
        self.sub_dir.mkdir()
        self.nested_file = self.sub_dir / "nested.txt"
        self.nested_file.write_text("Nested content")
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_move_operation_flat_structure(self):
        """Test move operation creating flat structure."""
        actions = FileSystemActions(dry_run=False)
        
        target_path = actions.create_target_path(self.test_file, self.dest_dir)
        result = actions.move_file(self.test_file, target_path, dry_run=False)
        
        assert result is True
        assert not self.test_file.exists()
        assert target_path.exists()
        assert target_path.read_text() == "Test content"
    
    def test_move_operation_preserve_structure(self):
        """Test move operation preserving directory structure."""
        actions = FileSystemActions(dry_run=False)
        
        target_path = actions.create_target_path(
            self.nested_file, self.dest_dir, 
            with_dir=True, base_path=self.source_dir
        )
        result = actions.move_file(self.nested_file, target_path, dry_run=False)
        
        assert result is True
        assert not self.nested_file.exists()
        assert target_path.exists()
        expected_path = self.dest_dir / "subdir" / "nested.txt"
        assert target_path == expected_path


class TestCopyOperationIntegration:
    """Integration tests for copy operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.dest_dir = Path(self.temp_dir) / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
        
        # Create test files
        self.test_file = self.source_dir / "test.txt"
        self.test_file.write_text("Test content")
        
        self.test_dir = self.source_dir / "testdir"
        self.test_dir.mkdir()
        (self.test_dir / "file1.txt").write_text("File 1")
        (self.test_dir / "file2.txt").write_text("File 2")
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_copy_file_operation(self):
        """Test copying a single file."""
        actions = FileSystemActions(dry_run=False)
        
        target_path = self.dest_dir / "copied.txt"
        result = actions.copy_file(self.test_file, target_path, dry_run=False)
        
        assert result is True
        assert self.test_file.exists()  # Source should remain
        assert target_path.exists()
        assert target_path.read_text() == "Test content"
    
    def test_copy_directory_operation(self):
        """Test copying a directory."""
        actions = FileSystemActions(dry_run=False)
        
        target_path = self.dest_dir / "copied_dir"
        result = actions.copy_file(self.test_dir, target_path, dry_run=False)
        
        assert result is True
        assert self.test_dir.exists()  # Source should remain
        assert target_path.exists()
        assert (target_path / "file1.txt").exists()
        assert (target_path / "file2.txt").exists()


class TestDeleteOperationIntegration:
    """Integration tests for delete operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("Test content")
        
        self.test_dir = Path(self.temp_dir) / "testdir"
        self.test_dir.mkdir()
        (self.test_dir / "file1.txt").write_text("File 1")
    
    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_delete_file_operation(self):
        """Test deleting a single file."""
        actions = FileSystemActions(dry_run=False)
        
        result = actions.delete_file(self.test_file, dry_run=False)
        
        assert result is True
        assert not self.test_file.exists()
    
    def test_delete_directory_operation(self):
        """Test deleting a directory."""
        actions = FileSystemActions(dry_run=False)
        
        result = actions.delete_file(self.test_dir, dry_run=False)
        
        assert result is True
        assert not self.test_dir.exists()


class TestErrorHandlingIntegration:
    """Integration tests for error handling scenarios."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.actions = FileSystemActions(dry_run=False)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_move_nonexistent_file(self):
        """Test moving a nonexistent file."""
        source = Path(self.temp_dir) / "nonexistent.txt"
        target = Path(self.temp_dir) / "target.txt"
        
        result = self.actions.move_file(source, target, dry_run=False)
        
        assert result is False
        assert self.actions.stats['errors'] == 1
    
    def test_copy_to_readonly_destination(self):
        """Test copying to read-only destination."""
        source = Path(self.temp_dir) / "source.txt"
        source.write_text("Content")
        
        readonly_dir = Path(self.temp_dir) / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only
        
        target = readonly_dir / "target.txt"
        
        try:
            result = self.actions.copy_file(source, target, dry_run=False)
            # Should handle the permission error gracefully
            assert result is False
            assert self.actions.stats['errors'] == 1
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestPerformanceScenarios:
    """Test suite for performance-related scenarios."""
    
    def setup_method(self):
        """Set up test environment with multiple files."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source"
        self.dest_dir = Path(self.temp_dir) / "dest"
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
        
        # Create multiple test files
        self.test_files = []
        for i in range(10):
            test_file = self.source_dir / f"file_{i:03d}.txt"
            test_file.write_text(f"Content of file {i}")
            self.test_files.append(test_file)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_batch_move_operations(self):
        """Test moving multiple files efficiently."""
        actions = FileSystemActions(dry_run=False)
        
        successful_moves = 0
        for test_file in self.test_files:
            target = self.dest_dir / test_file.name
            result = actions.move_file(test_file, target, dry_run=False)
            if result:
                successful_moves += 1
        
        assert successful_moves == len(self.test_files)
        assert actions.stats['moved'] == len(self.test_files)
        assert actions.stats['errors'] == 0
    
    def test_statistics_tracking_accuracy(self):
        """Test that statistics are accurately tracked during operations."""
        actions = FileSystemActions(dry_run=False)
        
        # Perform various operations
        for i, test_file in enumerate(self.test_files[:5]):
            target = self.dest_dir / f"moved_{test_file.name}"
            actions.move_file(test_file, target, dry_run=False)
        
        for test_file in self.test_files[5:7]:
            target = self.dest_dir / f"copied_{test_file.name}"
            actions.copy_file(test_file, target, dry_run=False)
        
        for test_file in self.test_files[7:]:
            actions.delete_file(test_file, dry_run=False)
        
        # Verify statistics
        assert actions.stats['moved'] == 5
        assert actions.stats['copied'] == 2
        assert actions.stats['deleted'] == 3
        total_operations = sum(actions.stats.values()) - actions.stats['errors'] - actions.stats['skipped']
        assert total_operations == 10


if __name__ == '__main__':
    """Run tests when executed directly."""
    pytest.main([__file__, '-v', '--tb=short'])
