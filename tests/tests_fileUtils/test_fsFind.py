#!/usr/bin/env python3

import os
import sys
import importlib

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

import file_utils.findFiles as findFiles


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


def test_verbose_help_output(capsys):
    import argparse
    parser = argparse.ArgumentParser(description='dummy')
    findFiles.print_verbose_help(parser)
    out = capsys.readouterr().out
    assert 'Examples:' in out
