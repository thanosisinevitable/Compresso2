from pathlib import Path
import stat


class Cancelled(Exception):
    pass


def checked_file(value):
    path = Path(value).absolute()
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'Choose a regular file, not a symbolic link: {path.name}')
    if path.resolve() != path:
        raise ValueError(f'The file path contains an alias. Choose the file again: {path.name}')
    return path


def fingerprint(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.resolve() != path:
        raise ValueError(f'{path.name} is no longer a regular file.')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
