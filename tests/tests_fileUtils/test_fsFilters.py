#!/usr/bin/env python3
"""
test_lib_filters.py - Comprehensive Tests for lib_filters.py

Tests the core filtering system including size, date, pattern, type, and git filtering.
Covers unit tests, integration tests, edge cases, and error handling.
"""

import os
import pytest
import tempfile
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

# Import the modules under test
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from file_utils.lib_filters import (
    SizeFilter, DateFilter, GitIgnoreFilter, FileSystemFilter,
    apply_config_to_filter, load_config_file, process_filters_pipeline
)


class TestSizeFilter:
    """Test suite for SizeFilter class."""
    
    def test_parse_size_bytes(self):
        """Test parsing size in bytes."""
        result = SizeFilter.parse_size("100")
        assert result == 100
    
    def test_parse_size_kilobytes(self):
        """Test parsing size in kilobytes."""
        result = SizeFilter.parse_size("100K")
        assert result == 100 * 1024
    
    def test_parse_size_megabytes(self):
        """Test parsing size in megabytes."""
        result = SizeFilter.parse_size("1.5M")
        assert result == int(1.5 * 1024 * 1024)
    
    def test_parse_size_gigabytes(self):
        """Test parsing size in gigabytes."""
        result = SizeFilter.parse_size("2G")
        assert result == 2 * 1024 * 1024 * 1024
    
    def test_parse_size_terabytes(self):
        """Test parsing size in terabytes."""
        result = SizeFilter.parse_size("1T")
        assert result == 1024 * 1024 * 1024 * 1024
    
    def test_parse_size_with_b_suffix(self):
        """Test parsing size with B suffix."""
        result = SizeFilter.parse_size("100KB")
        assert result == 100 * 1024
    
    def test_parse_size_invalid_format(self):
        """Test parsing invalid size format raises ValueError."""
        with pytest.raises(ValueError):
            SizeFilter.parse_size("invalid")
    
    def test_create_filter_greater_than(self):
        """Test creating greater than size filter."""
        size_filter = SizeFilter.create_filter('gt', '1M')
        
        # Mock file with size > 1M
        mock_path = Mock()
        mock_path.is_file.return_value = True
        mock_stat = Mock()
        mock_stat.st_size = 2 * 1024 * 1024  # 2M
        mock_path.stat.return_value = mock_stat
        
        result = size_filter(mock_path)
        assert result is True
    
    def test_create_filter_less_than(self):
        """Test creating less than size filter."""
        size_filter = SizeFilter.create_filter('lt', '1M')
        
        # Mock file with size < 1M
        mock_path = Mock()
        mock_path.is_file.return_value = True
        mock_stat = Mock()
        mock_stat.st_size = 512 * 1024  # 512K
        mock_path.stat.return_value = mock_stat
        
        result = size_filter(mock_path)
        assert result is True
    
    def test_create_filter_directory_always_passes(self):
        """Test that directories always pass size filters."""
        size_filter = SizeFilter.create_filter('gt', '1M')
        
        mock_path = Mock()
        mock_path.is_file.return_value = False
        
        result = size_filter(mock_path)
        assert result is True
    
    def test_create_filter_permission_error(self):
        """Test size filter handles permission errors gracefully."""
        size_filter = SizeFilter.create_filter('gt', '1M')
        
        mock_path = Mock()
        mock_path.is_file.return_value = True
        mock_path.stat.side_effect = PermissionError("Access denied")
        
        result = size_filter(mock_path)
        assert result is True  # Should pass on error


class TestDateFilter:
    """Test suite for DateFilter class."""
    
    def test_parse_date_ymd_format(self):
        """Test parsing YYYY-MM-DD format."""
        result = DateFilter.parse_date("2024-01-15")
        expected = datetime(2024, 1, 15)
        assert result == expected
    
    def test_parse_date_with_time(self):
        """Test parsing YYYY-MM-DD HH:MM format."""
        result = DateFilter.parse_date("2024-01-15 14:30")
        expected = datetime(2024, 1, 15, 14, 30)
        assert result == expected
    
    def test_parse_date_relative_days(self):
        """Test parsing relative date in days."""
        with patch('file_utils.lib_filters.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = DateFilter.parse_date("7d")
            expected = mock_now - timedelta(days=7)
            assert result == expected
    
    def test_parse_date_relative_weeks(self):
        """Test parsing relative date in weeks."""
        with patch('file_utils.lib_filters.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = DateFilter.parse_date("2w")
            expected = mock_now - timedelta(weeks=2)
            assert result == expected
    
    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format raises ValueError."""
        with pytest.raises(ValueError):
            DateFilter.parse_date("invalid-date")
    
    def test_create_filter_modified_after(self):
        """Test creating modified after date filter."""
        date_filter = DateFilter.create_filter('after', '2024-01-01', 'modified')
        
        # Mock file modified after target date
        mock_path = Mock()
        mock_stat = Mock()
        mock_stat.st_mtime = datetime(2024, 1, 15).timestamp()
        mock_path.stat.return_value = mock_stat
        
        result = date_filter(mock_path)
        assert result is True
    
    def test_create_filter_created_before(self):
        """Test creating created before date filter."""
        date_filter = DateFilter.create_filter('before', '2024-01-15', 'created')
        
        # Mock file created before target date
        mock_path = Mock()
        mock_stat = Mock()
        mock_stat.st_ctime = datetime(2024, 1, 1).timestamp()
        mock_path.stat.return_value = mock_stat
        
        result = date_filter(mock_path)
        assert result is True
    
    def test_create_filter_permission_error(self):
        """Test date filter handles permission errors gracefully."""
        date_filter = DateFilter.create_filter('after', '2024-01-01', 'modified')
        
        mock_path = Mock()
        mock_path.stat.side_effect = PermissionError("Access denied")
        
        result = date_filter(mock_path)
        assert result is True  # Should pass on error


class TestGitIgnoreFilter:
    """Test suite for GitIgnoreFilter class."""
    
    def test_init_with_empty_paths(self):
        """Test initializing with empty search paths."""
        git_filter = GitIgnoreFilter([])
        assert git_filter.ignore_patterns == []
    
    @patch('file_utils.lib_filters.Path')
    def test_load_gitignore_files(self, mock_path_class):
        """Test loading .gitignore files from search paths."""
        # Mock path structure
        mock_path = Mock()
        mock_path.resolve.return_value = mock_path
        mock_path.parent = mock_path
        mock_path.__truediv__ = Mock(return_value=mock_path)
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        
        # Mock reading .gitignore content
        with patch('builtins.open', mock_open(read_data="*.pyc\n__pycache__/\n")):
            git_filter = GitIgnoreFilter([Path("/test")])
            
        expected_patterns = ["*.pyc", "__pycache__/"]
        assert git_filter.ignore_patterns == expected_patterns
    
    def test_matches_gitignore_pattern_simple(self):
        """Test matching simple gitignore patterns."""
        git_filter = GitIgnoreFilter([])
        
        result = git_filter.matches_gitignore_pattern("test.pyc", "*.pyc")
        assert result is True
    
    def test_matches_gitignore_pattern_directory(self):
        """Test matching directory gitignore patterns."""
        git_filter = GitIgnoreFilter([])
        
        result = git_filter.matches_gitignore_pattern("__pycache__", "__pycache__/")
        assert result is True
    
    def test_should_ignore_matches_pattern(self):
        """Test should_ignore method with matching pattern."""
        git_filter = GitIgnoreFilter([])
        git_filter.ignore_patterns = ["*.pyc", "__pycache__/"]
        
        mock_path = Mock()
        mock_path.relative_to.return_value = Path("test.pyc")
        mock_base = Mock()
        
        result = git_filter.should_ignore(mock_path, mock_base)
        assert result is True
    
    def test_should_ignore_no_match(self):
        """Test should_ignore method with no matching pattern."""
        git_filter = GitIgnoreFilter([])
        git_filter.ignore_patterns = ["*.pyc", "__pycache__/"]
        
        mock_path = Mock()
        mock_path.relative_to.return_value = Path("test.py")
        mock_base = Mock()
        
        result = git_filter.should_ignore(mock_path, mock_base)
        assert result is False


class TestFileSystemFilter:
    """Test suite for FileSystemFilter class."""
    
    def test_init_default_values(self):
        """Test FileSystemFilter initialization with default values."""
        fs_filter = FileSystemFilter()
        
        assert fs_filter.size_filters == []
        assert fs_filter.date_filters == []
        assert fs_filter.file_patterns == []
        assert fs_filter.dir_patterns == []
        assert fs_filter.inverse is False
        assert fs_filter.skip_empty is False
        assert fs_filter.show_empty is False
    
    def test_add_size_filter(self):
        """Test adding size filter."""
        fs_filter = FileSystemFilter()
        fs_filter.add_size_filter('gt', '1M')
        
        assert len(fs_filter.size_filters) == 1
    
    def test_add_date_filter(self):
        """Test adding date filter."""
        fs_filter = FileSystemFilter()
        fs_filter.add_date_filter('after', '2024-01-01', 'modified')
        
        assert len(fs_filter.date_filters) == 1
    
    def test_add_file_pattern(self):
        """Test adding file pattern."""
        fs_filter = FileSystemFilter()
        fs_filter.add_file_pattern('*.py')
        
        assert fs_filter.file_patterns == ['*.py']
    
    def test_add_type_filter(self):
        """Test adding type filter."""
        with patch.object(FileSystemFilter, 'load_extension_data'):
            fs_filter = FileSystemFilter()
            fs_filter.add_type_filter('image')
            
            assert fs_filter.type_filters == ['image']
    
    def test_matches_patterns_success(self):
        """Test pattern matching success."""
        fs_filter = FileSystemFilter()
        
        mock_path = Mock()
        mock_path.name = "test.py"
        
        result = fs_filter.matches_patterns(mock_path, ['*.py'])
        assert result is True
    
    def test_matches_patterns_failure(self):
        """Test pattern matching failure."""
        fs_filter = FileSystemFilter()
        
        mock_path = Mock()
        mock_path.name = "test.js"
        
        result = fs_filter.matches_patterns(mock_path, ['*.py'])
        assert result is False
    
    def test_should_include_all_filters_pass(self):
        """Test should_include when all filters pass."""
        fs_filter = FileSystemFilter()
        
        mock_path = Mock()
        mock_path.is_dir.return_value = False
        
        result = fs_filter.should_include(mock_path)
        assert result is True
    
    def test_should_include_with_inverse(self):
        """Test should_include with inverse flag."""
        fs_filter = FileSystemFilter()
        fs_filter.inverse = True
        fs_filter.add_file_pattern('*.py')
        
        mock_path = Mock()
        mock_path.is_dir.return_value = False
        mock_path.name = "test.js"
        
        # Should include because inverse=True and pattern doesn't match
        result = fs_filter.should_include(mock_path)
        assert result is True
    
    @patch('file_utils.lib_filters.get_extension_data')
    def test_load_extension_data(self, mock_get_extension_data):
        """Test loading extension data."""
        mock_get_extension_data.return_value = {'types': {}, 'extensions': {}}
        
        fs_filter = FileSystemFilter()
        fs_filter.load_extension_data()
        
        assert fs_filter.extension_data is not None
        mock_get_extension_data.assert_called_once()
    
    def test_filter_paths_basic(self):
        """Test basic path filtering."""
        fs_filter = FileSystemFilter()
        
        # Mock path that should be included
        with patch.object(fs_filter, 'should_include', return_value=True):
            with patch('file_utils.lib_filters.Path') as mock_path_class:
                mock_path = Mock()
                mock_path_class.return_value = mock_path
                
                result = fs_filter.filter_paths(['test.py'], [Path('/base')])
                assert result == ['test.py']
    
    def test_filter_paths_with_inverse(self):
        """Test path filtering with inverse flag."""
        fs_filter = FileSystemFilter()
        fs_filter.inverse = True
        
        # Mock path that should be excluded normally but included with inverse
        with patch.object(fs_filter, 'should_include', return_value=False):
            with patch('file_utils.lib_filters.Path') as mock_path_class:
                mock_path = Mock()
                mock_path_class.return_value = mock_path
                
                result = fs_filter.filter_paths(['test.py'], [Path('/base')])
                assert result == ['test.py']


class TestConfigurationFunctions:
    """Test suite for configuration-related functions."""
    
    def test_load_config_file_success(self):
        """Test successful config file loading."""
        config_data = {'size_gt': '1M', 'file_patterns': ['*.py']}
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(config_data))):
            result = load_config_file('test.yml')
            
        assert result == config_data
    
    def test_load_config_file_not_found(self):
        """Test config file loading when file not found."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = load_config_file('nonexistent.yml')
            
        assert result == {}
    
    def test_apply_config_to_filter(self):
        """Test applying configuration to filter object."""
        fs_filter = FileSystemFilter()
        config = {
            'size_gt': '1M',
            'modified_after': '7d',
            'file_patterns': ['*.py', '*.js'],
            'types': ['image'],
            'inverse': True
        }
        
        with patch.object(fs_filter, 'add_size_filter') as mock_size, \
             patch.object(fs_filter, 'add_date_filter') as mock_date, \
             patch.object(fs_filter, 'add_file_pattern') as mock_pattern, \
             patch.object(fs_filter, 'add_type_filter') as mock_type:
            
            apply_config_to_filter(fs_filter, config)
            
            mock_size.assert_called_with('gt', '1M')
            mock_date.assert_called_with('after', '7d', 'modified')
            assert mock_pattern.call_count == 2
            mock_type.assert_called_with('image')
            assert fs_filter.inverse is True


class TestIntegrationScenarios:
    """Integration tests for common usage scenarios."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        
        # Create test file structure
        test_structure = [
            'test.py',
            'test.js', 
            'README.md',
            'large_file.dat',
            'small_file.txt',
            'subdir/nested.py',
            '.gitignore',
            '__pycache__/cache.pyc'
        ]
        
        for file_path in test_structure:
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create files with different sizes
            if 'large' in file_path:
                content = 'x' * (2 * 1024 * 1024)  # 2MB
            elif 'small' in file_path:
                content = 'small'
            else:
                content = f'Content of {file_path}'
                
            full_path.write_text(content)
            self.test_files.append(str(full_path))
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_size_filtering_integration(self):
        """Test size filtering in realistic scenario."""
        fs_filter = FileSystemFilter()
        fs_filter.add_size_filter('gt', '1M')
        
        # Filter should only include large files
        base_paths = [Path(self.temp_dir)]
        result = fs_filter.filter_paths(self.test_files, base_paths)
        
        # Only large_file.dat should remain
        large_files = [f for f in result if 'large_file' in f]
        assert len(large_files) == 1
    
    def test_pattern_filtering_integration(self):
        """Test pattern filtering in realistic scenario."""
        fs_filter = FileSystemFilter()
        fs_filter.add_file_pattern('*.py')
        
        base_paths = [Path(self.temp_dir)]
        result = fs_filter.filter_paths(self.test_files, base_paths)
        
        # Should only include Python files
        py_files = [f for f in result if f.endswith('.py')]
        assert len(py_files) >= 1
        assert all(f.endswith('.py') for f in result if not Path(f).is_dir())
    
    def test_combined_filtering_integration(self):
        """Test combined size and pattern filtering."""
        fs_filter = FileSystemFilter()
        fs_filter.add_file_pattern('*.dat')
        fs_filter.add_size_filter('gt', '1M')
        
        base_paths = [Path(self.temp_dir)]
        result = fs_filter.filter_paths(self.test_files, base_paths)
        
        # Should only include large .dat files
        dat_files = [f for f in result if f.endswith('.dat')]
        assert len(dat_files) == 1
    
    def test_inverse_filtering_integration(self):
        """Test inverse filtering in realistic scenario."""
        fs_filter = FileSystemFilter()
        fs_filter.add_file_pattern('*.py')
        fs_filter.inverse = True
        
        base_paths = [Path(self.temp_dir)]
        result = fs_filter.filter_paths(self.test_files, base_paths)
        
        # Should exclude Python files
        py_files = [f for f in result if f.endswith('.py')]
        assert len(py_files) == 0


class TestErrorHandling:
    """Test suite for error handling scenarios."""
    
    def test_size_filter_with_invalid_size(self):
        """Test size filter creation with invalid size."""
        with pytest.raises(ValueError):
            SizeFilter.create_filter('gt', 'invalid_size')
    
    def test_date_filter_with_invalid_date(self):
        """Test date filter creation with invalid date."""
        with pytest.raises(ValueError):
            DateFilter.create_filter('after', 'invalid_date', 'modified')
    
    def test_gitignore_filter_with_permission_error(self):
        """Test GitIgnoreFilter handling permission errors."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise exception
            git_filter = GitIgnoreFilter([Path('/test')])
            assert git_filter.ignore_patterns == []
    
    def test_filesystem_filter_with_nonexistent_path(self):
        """Test FileSystemFilter with nonexistent paths."""
        fs_filter = FileSystemFilter()
        
        # Should handle gracefully
        result = fs_filter.filter_paths(['/nonexistent/path'], [Path('/base')])
        assert isinstance(result, list)
    
    @patch('file_utils.lib_filters.log_info')
    def test_config_loading_with_yaml_error(self, mock_log):
        """Test config loading with YAML parsing error."""
        with patch('builtins.open', mock_open(read_data='invalid: yaml: content: [')):
            result = load_config_file('invalid.yml')
            
        assert result == {}
        mock_log.assert_called()


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""
    
    def test_empty_filter_paths_list(self):
        """Test filtering with empty paths list."""
        fs_filter = FileSystemFilter()
        
        result = fs_filter.filter_paths([], [Path('/base')])
        assert result == []
    
    def test_filter_with_no_base_paths(self):
        """Test filtering with no base paths."""
        fs_filter = FileSystemFilter()
        
        result = fs_filter.filter_paths(['test.py'], [])
        assert isinstance(result, list)
    
    def test_size_filter_with_zero_size(self):
        """Test size filter with zero size (empty files)."""
        size_filter = SizeFilter.create_filter('eq', '0')
        
        mock_path = Mock()
        mock_path.is_file.return_value = True
        mock_stat = Mock()
        mock_stat.st_size = 0
        mock_path.stat.return_value = mock_stat
        
        result = size_filter(mock_path)
        assert result is True
    
    def test_date_filter_with_same_timestamp(self):
        """Test date filter with exact timestamp match."""
        target_time = datetime(2024, 1, 15).timestamp()
        date_filter = DateFilter.create_filter('eq', '2024-01-15', 'modified')
        
        mock_path = Mock()
        mock_stat = Mock()
        mock_stat.st_mtime = target_time
        mock_path.stat.return_value = mock_stat
        
        result = date_filter(mock_path)
        assert result is True
    
    def test_pattern_matching_with_special_characters(self):
        """Test pattern matching with special characters."""
        fs_filter = FileSystemFilter()
        
        mock_path = Mock()
        mock_path.name = "file[special].py"
        
        # Should handle special regex characters in glob patterns
        result = fs_filter.matches_patterns(mock_path, ['file[special].py'])
        assert result is True
    
    def test_extension_filter_without_dot(self):
        """Test extension filter when extension provided without dot."""
        fs_filter = FileSystemFilter()
        fs_filter.add_extension_filter('py')  # Without dot
        
        assert '.py' in fs_filter.extension_filters


if __name__ == '__main__':
    """Run tests when executed directly."""
    pytest.main([__file__, '-v', '--tb=short'])
