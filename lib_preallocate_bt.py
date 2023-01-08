import argparse
import os, os.path
import math
import torrent_parser

PREALLOCATE_BUF_SIZE = 32 * 1024 * 1024

def check_file_name(fn):
    if '/' in fn or '\x00' in fn or fn == '.' or fn == '..':
        raise ValueError(f'insafe file name: {repr(fn)}')

def check_file_in_dir(dir_path, file_path):
    real_dir_path = os.path.realpath(dir_path)
    real_file_path = os.path.realpath(file_path)
    
    if os.path.commonpath((real_dir_path, real_file_path)) != real_dir_path:
        raise ValueError(f'file {repr(file_path)} ({repr(real_file_path)})'
                f' not in directory {repr(dir_path)} ({repr(real_dir_path)})')

def format_length(length):
    table = [
        (1000_000_000_000, 'TB', 10),
        (1000_000_000, 'GB', 10),
        (1000_000, 'MB', 10),
        (1000, 'kB', 10),
    ]
    
    for row in table:
        size, unit, acc = row
        
        if length >= size:
            return f'{repr(math.ceil(length * acc / size) / acc)} {unit}'
    
    return f'{repr(length)} bytes'

def make_verbose_hooks():
    def start_reading_torrent_file(path):
        print(f'reading torrent file: {repr(path)}...')
    
    def end_reading_torrent_file(path):
        print(f'reading torrent file: {repr(path)}: done')
    
    def start_preallocation_procedure():
        print(f'preallocation procedure...')
    
    def end_preallocation_procedure():
        print(f'preallocation procedure: done')
    
    def start_preallocation_file(file):
        names, length = file
        
        print(f'preallocation file: {repr(os.path.join(*names))}'
                f' {repr(length)} ({format_length(length)})...')
    
    def end_preallocation_file(file, skipped):
        names, length = file
        
        if skipped:
            print(f'preallocation file: {repr(os.path.join(*names))}: skipped')
        else:
            print(f'preallocation file: {repr(os.path.join(*names))}: done')
    
    def preallocation_pos(pos):
        print(f'current position: {repr(pos)} ({format_length(pos)})')
    
    return {
        'start_reading_torrent_file': start_reading_torrent_file,
        'end_reading_torrent_file': end_reading_torrent_file,
        'start_preallocation_procedure': start_preallocation_procedure,
        'end_preallocation_procedure': end_preallocation_procedure,
        'start_preallocation_file': start_preallocation_file,
        'end_preallocation_file': end_preallocation_file,
        'preallocation_pos': preallocation_pos,
    }

def apply_hook(hooks, name, *args, **kwargs):
    if hooks is None:
        return
    
    hook = hooks.get(name)
    
    if hook is not None:
        return hook(*args, **kwargs)

def get_torrent_files(torrent_into):
    files = []
    
    torrent_name = torrent_into['name']
    torrent_files = torrent_into.get('files')
    
    if not isinstance(torrent_name, str):
        raise ValueError
    
    check_file_name(torrent_name)
    
    if torrent_files is not None:
        if not isinstance(torrent_files, list):
            raise ValueError
        
        for file in torrent_files:
            path = file['path']
            length = file['length']
            
            if not isinstance(path, list):
                raise ValueError
            
            if not isinstance(length, int):
                raise ValueError
            
            for p in path:
                if not isinstance(p, str):
                    raise ValueError
                
                check_file_name(p)
            
            fixed_path = [torrent_name] + path
            
            files.append((fixed_path, length))
    else:
        length = torrent_into.get('length')
        
        if not isinstance(length, int):
            raise ValueError
        
        files.append(([torrent_name], length))
    
    return files

def preallocate_file(dest_dir, file, verbose_hooks=None,
        _buf_size=PREALLOCATE_BUF_SIZE):
    names, length = file
    dirs = names[:-1]
    file_name = names[-1]
    part_file_name = f'{file_name}.part'
    
    dir_path = dest_dir
    
    for dir_name in dirs:
        dir_path = os.path.join(dir_path, dir_name)
        
        check_file_in_dir(dest_dir, dir_path)
        
        try:
            os.mkdir(dir_path)
        except FileExistsError:
            pass
    
    file_path = os.path.join(dir_path, file_name)
    
    check_file_in_dir(dest_dir, file_path)
    
    if os.path.isfile(file_path):
        # already downloaded
        
        return True
    
    part_file_path = os.path.join(dir_path, part_file_name)
    
    check_file_in_dir(dest_dir, part_file_path)
    
    with open(part_file_path, 'ab') as fd:
        while True:
            pos = fd.tell()
            
            apply_hook(verbose_hooks, 'preallocation_pos', pos)
            
            if pos >= length:
                break
            
            l = (pos + _buf_size) // _buf_size * _buf_size - pos
            
            if pos + l > length:
                l = length - pos
            
            buf = b'\x00' * l
            
            fd.write(buf)
            fd.flush()
            os.fsync(fd.fileno())
    
    return False

def preallocate_bt_cmd(torrent_path=None, dest_dir=None, verbose_hooks=None,
        _parse_torrent_file=torrent_parser.parse_torrent_file,
        _get_torrent_files=get_torrent_files,
        _preallocate_file=preallocate_file):
    
    apply_hook(verbose_hooks, 'start_reading_torrent_file', torrent_path)
    
    torrent_data = _parse_torrent_file(torrent_path)
    torrent_into = torrent_data['info']
    files = _get_torrent_files(torrent_into)
    
    apply_hook(verbose_hooks, 'end_reading_torrent_file', torrent_path)
    
    apply_hook(verbose_hooks, 'start_preallocation_procedure')
    
    for file in files:
        apply_hook(verbose_hooks, 'start_preallocation_file', file)
        
        skipped = _preallocate_file(dest_dir, file, verbose_hooks=verbose_hooks)
        
        apply_hook(verbose_hooks, 'end_preallocation_file', file, skipped)
    
    apply_hook(verbose_hooks, 'end_preallocation_procedure')

def main():
    parser = argparse.ArgumentParser(
            description='an utility to preallocate files before downloading')
    
    parser.add_argument('-v', '--verbose', action='store_true',
            help='be verbose. show what file is preallocating and progress')
    
    parser.add_argument('torrent', help='path to the source torrent file')
    
    parser.add_argument('dest', help='path to the downloading destination directory')
    
    args = parser.parse_args()
    
    if args.verbose:
        verbose_hooks = make_verbose_hooks()
    else:
        verbose_hooks = None
    
    torrent_path = args.torrent
    dest_dir = args.dest
    
    preallocate_bt_cmd(torrent_path=torrent_path, dest_dir=dest_dir,
            verbose_hooks=verbose_hooks)

# vi:ts=4:sw=4:et
