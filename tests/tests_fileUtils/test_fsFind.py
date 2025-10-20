#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from pathlib import Path
from unittest import mock

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath('src'))
sys.path.insert(0, os.path.abspath('src/file_utils'))

from file_utils.lib_extensions import ExtensionInfo
import dev_utils
from dev_utils import lib_logging

dev_utils.setup_logging = lib_logging.setup_logging
dev_utils.log_block = lib_logging.log_block
dev_utils.log_function = lib_logging.log_function
dev_utils.log_out = lib_logging.log_out

import file_utils.fsFind  as findFiles


def preload_extension_info():
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'extensions.csv')
    ExtensionInfo(csv_path)


def test_find_files_by_audio_type(tmp_path):
    preload_extension_info()
    filenames = ['song.mp3', 'sound.wav', 'video.mp4', 'note.txt']
    for name in filenames:
        (tmp_path / name).write_text('x')

    results = sorted(os.path.basename(p) for p in findFiles.find_files(
        str(tmp_path), file_types='Audio'))
    assert results == ['song.mp3', 'sound.wav']


def test_list_available_types(capsys):
    preload_extension_info()
    findFiles.list_available_types()
    out = capsys.readouterr().out
    assert 'Audio' in out
    assert 'Video' in out


def make_parser():
    parser = argparse.ArgumentParser(description='fsFind test parser')
    findFiles.add_args(parser)
    return parser


def parse_args(*args: str):
    parser = make_parser()
    return parser.parse_args(list(args))


def test_verbose_help_output(capsys):
    parser = argparse.ArgumentParser(description='dummy')
    findFiles.print_verbose_help(parser)
    out = capsys.readouterr().out
    assert 'Examples:' in out


def test_recursive_options_toggle():
    assert parse_args('--no-recursive').recursive is False
    assert parse_args('--recursive').recursive is True


def test_depth_arguments_parse():
    args = parse_args('--max-depth', '2', '--min-depth', '1')
    assert args.max_depth == 2
    assert args.min_depth == 1


def test_follow_symlinks_and_include_dirs_options():
    args = parse_args('--follow-symlinks', '--include-dirs')
    assert args.follow_symlinks is True
    assert args.include_dirs is True


def test_pattern_and_substring_options():
    args = parse_args('.', '--substr', 'test', '-s', 'data')
    assert args.directories == ['.']
    assert args.pattern is None
    assert args.substr == ['test', 'data']


def test_pattern_argument_forwarded_to_finder(tmp_path):
    directory = tmp_path / 'project'
    directory.mkdir()
    args = parse_args(str(directory))
    args.pattern = '*.py'

    with mock.patch('file_utils.fsFind.create_filter_from_args', return_value=None):
        with mock.patch('file_utils.fsFind.EnhancedFileFinder.find_files', return_value=[]) as finder:
            findFiles.process_find_pipeline(args)

    finder.assert_called_once()
    _, kwargs = finder.call_args
    assert kwargs['file_pattern'] == '*.py'


def test_regex_extension_and_type_options():
    args = parse_args('--regex', '.*\\.py$', '--ext', 'py,txt', '--type', 'text,code')
    assert args.regex == '.*\\.py$'
    assert args.ext == 'py,txt'
    assert args.type == 'text,code'


def test_size_filter_options_trigger_filter_creation():
    args = parse_args('--size-gt', '10K', '--size-lt', '20K', '--size-eq', '15K')
    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        instance = Filter.return_value
        fs_filter = findFiles.create_filter_from_args(args)
        assert fs_filter is instance
        instance.add_size_filter.assert_any_call('gt', '10K')
        instance.add_size_filter.assert_any_call('lt', '20K')
        instance.add_size_filter.assert_any_call('eq', '15K')


def test_date_filter_options_trigger_filter_creation():
    args = parse_args(
        '--modified-after', '2024-01-01', '--modified-before', '2024-02-01',
        '--created-after', '2024-03-01', '--created-before', '2024-04-01'
    )
    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        instance = Filter.return_value
        findFiles.create_filter_from_args(args)
        instance.add_date_filter.assert_any_call('after', '2024-01-01', 'modified')
        instance.add_date_filter.assert_any_call('before', '2024-02-01', 'modified')
        instance.add_date_filter.assert_any_call('after', '2024-03-01', 'created')
        instance.add_date_filter.assert_any_call('before', '2024-04-01', 'created')


def test_pattern_filter_options():
    args = parse_args(
        '--pattern-filter', '*.py', '--pattern-ignore', '*.tmp', '--file-pattern', '*.pyi',
        '--dir-pattern', 'tests*', '--file-ignore', '*.log', '--dir-ignore', 'build',
        '--ignore-filter', '*.bak', '--filter-ignore', '*.cache'
    )
    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        instance = Filter.return_value
        findFiles.create_filter_from_args(args)
        instance.add_file_pattern.assert_any_call('*.pyi')
        instance.add_dir_pattern.assert_any_call('tests*')
        instance.add_file_ignore_pattern.assert_any_call('*.tmp')
        instance.add_dir_ignore_pattern.assert_any_call('*.tmp')
        instance.add_file_pattern.assert_any_call('*.py')
        instance.add_dir_pattern.assert_any_call('*.py')
        instance.add_file_ignore_pattern.assert_any_call('*.log')
        instance.add_dir_ignore_pattern.assert_any_call('build')
        instance.add_file_ignore_pattern.assert_any_call('*.bak')
        instance.add_dir_ignore_pattern.assert_any_call('*.bak')
        instance.add_file_ignore_pattern.assert_any_call('*.cache')
        instance.add_dir_ignore_pattern.assert_any_call('*.cache')


def test_type_and_extension_filter_options():
    args = parse_args('--type-filter', 'image', '-tf', 'audio', '--extension-filter', '.py', '-ef', '.md')
    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        instance = Filter.return_value
        findFiles.create_filter_from_args(args)
        instance.add_type_filter.assert_any_call('image')
        instance.add_type_filter.assert_any_call('audio')
        instance.add_extension_filter.assert_any_call('.py')
        instance.add_extension_filter.assert_any_call('.md')


def test_filter_file_option_loads_configuration(tmp_path):
    config_file = tmp_path / 'filters.yml'
    config_file.write_text('pattern: example')
    args = parse_args('--filter-file', str(config_file))
    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        fs_filter = findFiles.create_filter_from_args(args)
        assert fs_filter is Filter.return_value


def test_filter_file_option_without_pyyaml(monkeypatch, tmp_path, caplog):
    config_file = tmp_path / 'filters.yml'
    config_file.write_text('pattern: example')
    args = parse_args('--filter-file', str(config_file))

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(findFiles.importlib.util, 'find_spec', lambda name: None)
    findFiles._YAML_MODULE = None
    findFiles._YAML_CHECKED = False

    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        fs_filter = findFiles.create_filter_from_args(args)

    assert fs_filter is Filter.return_value
    assert "PyYAML is required for --filter-file support" in caplog.text
    assert "Ignoring --filter-file because PyYAML is not available." in caplog.text


def test_min_max_depth_limits_results(tmp_path):
    root = tmp_path
    (root / 'top.txt').write_text('top')
    level1 = root / 'level1'
    level1.mkdir()
    (level1 / 'mid.txt').write_text('mid')
    level2 = level1 / 'level2'
    level2.mkdir()
    (level2 / 'deep.txt').write_text('deep')

    finder = findFiles.EnhancedFileFinder()

    max_depth_results = sorted(Path(p).name for p in finder.find_files(
        [str(root)], recursive=True, max_depth=1
    ))
    assert 'top.txt' in max_depth_results
    assert 'mid.txt' not in max_depth_results
    assert 'deep.txt' not in max_depth_results

    min_depth_results = sorted(Path(p).name for p in finder.find_files(
        [str(root)], recursive=True, min_depth=2
    ))
    assert 'top.txt' not in min_depth_results
    assert 'mid.txt' in min_depth_results
    assert 'deep.txt' in min_depth_results


def test_git_ignore_option_enables_git_filter(tmp_path):
    search_dir = tmp_path / 'project'
    search_dir.mkdir()
    (search_dir / 'file.txt').write_text('content')
    args = parse_args(str(search_dir), '--git-ignore')

    with mock.patch('file_utils.fsFind.FileSystemFilter') as Filter:
        filter_instance = Filter.return_value
        filter_instance.should_include.return_value = True
        filter_instance.should_descend.return_value = True

        with mock.patch('file_utils.fsFind.create_filter_from_args', return_value=filter_instance):
            with mock.patch('file_utils.fsFind.EnhancedFileFinder.find_files', return_value=[]) as finder:
                findFiles.process_find_pipeline(args)
        filter_instance.enable_gitignore.assert_called()
        finder.assert_called()


def test_show_stats_option_triggers_output(tmp_path, capsys):
    directory = tmp_path / 'data'
    directory.mkdir()
    file_path = directory / 'file.txt'
    file_path.write_text('content')
    args = parse_args(str(directory), '--show-stats')

    with mock.patch('file_utils.fsFind.create_filter_from_args', return_value=None):
        with mock.patch('file_utils.fsFind.EnhancedFileFinder.find_files', return_value=[str(file_path)]):
            findFiles.process_find_pipeline(args)

    captured = capsys.readouterr()
    assert 'Found 1 item' in captured.err


def test_dry_run_option_reports_directories(tmp_path, capsys):
    directory = tmp_path / 'example'
    directory.mkdir()
    args = parse_args(str(directory), '--dry-run')
    findFiles.process_find_pipeline(args)
    captured = capsys.readouterr()
    assert 'DRY RUN' in captured.err
    assert str(directory) in captured.err


def test_list_types_option_short_circuits(capsys):
    args = parse_args('--list-types')
    with mock.patch.object(findFiles, 'list_available_types') as list_types:
        findFiles.process_find_pipeline(args)
    list_types.assert_called_once()


def test_help_examples_option_short_circuits(capsys):
    args = parse_args('--help-examples')
    with mock.patch.object(findFiles, 'show_examples') as show_examples:
        findFiles.process_find_pipeline(args)
    show_examples.assert_called_once()


def test_help_verbose_option_short_circuits():
    args = parse_args('--help-verbose')
    with mock.patch.object(findFiles, 'show_verbose_help') as show_verbose_help:
        findFiles.process_find_pipeline(args)
    show_verbose_help.assert_called_once()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
