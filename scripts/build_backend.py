"""Create a native, relocatable Python + Ghostscript resource bundle on macOS."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, text=True, **kwargs)


def dependencies(binary):
    output = run(['otool', '-L', binary], capture_output=True).stdout
    return [line.strip().split(' (')[0] for line in output.splitlines()[1:]]


def bundle_ghostscript():
    executable = shutil.which('gs')
    if not executable:
        raise RuntimeError('Install Ghostscript first: brew install ghostscript')
    prefix = Path(executable).resolve().parent.parent
    destination = BUILD / 'ghostscript'
    shutil.rmtree(destination, ignore_errors=True)
    (destination / 'bin').mkdir(parents=True)
    (destination / 'lib').mkdir()
    copied = {}

    def copy_binary(source, target):
        source = Path(source).resolve()
        if source in copied:
            return copied[source]
        if target.exists():
            raise RuntimeError(f'Conflicting library names: {target.name}')
        architectures = run(['lipo', '-archs', source], capture_output=True).stdout.split()
        if platform.machine() not in architectures:
            raise RuntimeError(f'Wrong architecture in {source}: {architectures}')
        shutil.copy2(source, target)
        target.chmod(0o755)
        copied[source] = target
        for dependency in dependencies(source):
            if dependency.startswith(('/System/', '/usr/lib/')):
                continue
            if dependency == str(source):
                continue
            if dependency.startswith('@loader_path/'):
                dep_path = source.parent / dependency[len('@loader_path/'):]
            elif dependency.startswith('@executable_path/'):
                dep_path = Path(executable).resolve().parent / dependency[len('@executable_path/'):]
            elif dependency.startswith('@rpath/'):
                name = dependency[len('@rpath/'):]
                candidates = [source.parent / name, prefix / 'lib' / name]
                load = run(['otool', '-l', source], capture_output=True).stdout.splitlines()
                for index, line in enumerate(load):
                    if line.strip() == 'cmd LC_RPATH':
                        raw = load[index+2].strip().split('path ',1)[1].split(' (offset')[0]
                        raw = raw.replace('@loader_path',str(source.parent)).replace('@executable_path',str(Path(executable).resolve().parent))
                        candidates.append(Path(raw) / name)
                dep_path = next((p for p in candidates if p.exists()), None)
                if not dep_path:
                    raise RuntimeError(f'Cannot resolve {dependency} used by {source}')
            else:
                dep_path = Path(dependency)
            if dep_path.resolve() == source:
                continue
            bundled = copy_binary(dep_path, destination / 'lib' / dep_path.resolve().name)
            relative = '@loader_path/' + os.path.relpath(bundled, target.parent)
            run(['install_name_tool', '-change', dependency, relative, target])
        if target.suffix == '.dylib':
            run(['install_name_tool', '-id', '@loader_path/' + target.name, target])
        return target

    copy_binary(executable, destination / 'bin/gs')
    versions = sorted((prefix / 'share/ghostscript').glob('*'))
    versions = [p for p in versions if (p / 'Resource/Init').is_dir()]
    if not versions:
        raise RuntimeError('Ghostscript resources could not be found in its installation prefix.')
    shutil.copytree(versions[-1], destination / 'share')
    fonts = prefix / 'share/fonts'
    if fonts.exists():
        shutil.copytree(fonts, destination / 'fonts')
    else:
        (destination / 'fonts').mkdir()
    licenses = destination / 'licenses'
    licenses.mkdir()
    # Preserve Homebrew formula licenses as well as Ghostscript's bundled documentation.
    for source in copied:
        parents = [p for p in source.parents if p.parent.name and p.parent.parent.name == 'Cellar']
        for formula in parents:
            for license_file in list(formula.glob('COPYING*')) + list(formula.glob('LICENSE*')):
                if license_file.is_file():
                    shutil.copy2(license_file, licenses / f'{formula.parent.name}-{license_file.name}')
    for binary in copied.values():
        for dep in dependencies(binary):
            if dep.startswith(('/opt/homebrew/', '/usr/local/')):
                raise RuntimeError(f'Non-relocatable dependency left in {binary}: {dep}')
        run(['codesign', '--force', '--sign', '-', binary])
    env = {**os.environ, 'GS_LIB': os.pathsep.join(str(destination / 'share' / p) for p in ['Resource/Init','lib','Resource/Font']), 'GS_FONTPATH': str(destination / 'fonts')}
    run([destination / 'bin/gs','-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=nullpage','-c','quit'],env=env)
    (destination / 'bundle-manifest.json').write_text(json.dumps({'architecture':platform.machine(),'libraries':[str(p.relative_to(destination)) for p in copied.values()]},indent=2))


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Native macOS packaging requires a Mac. Use npm test for platform-independent checks.')
    wanted = os.environ.get('COMPRESSO_BUILD_ARCH', 'arm64' if platform.machine() == 'arm64' else 'x64')
    actual = 'arm64' if platform.machine() == 'arm64' else 'x64'
    if wanted != actual:
        raise SystemExit('Python architecture does not match the requested Electron build. Use a native Python environment.')
    BUILD.mkdir(exist_ok=True)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
         '--name', 'compresso-backend', '--distpath', BUILD / 'backend', '--workpath', BUILD / 'pyinstaller',
         '--specpath', BUILD, '--paths', ROOT / 'backend', '--collect-all', 'imagehash',
         '--hidden-import', 'converter', '--hidden-import', 'imaging', '--hidden-import', 'vault', '--hidden-import', 'skimage.metrics._structural_similarity', '--collect-data', 'skimage', '--hidden-import', 'duplicates', '--hidden-import', 'entropy', '--collect-submodules', 'uvicorn',
         '--exclude-module', 'tkinter', '--exclude-module', 'matplotlib', '--exclude-module', 'torch',
         ROOT / 'backend/main.py'])
    bundle_ghostscript()
    run([sys.executable, ROOT / 'scripts/smoke_backend.py', '--bundled'])
    print('Native Python and Ghostscript resources are ready for Electron Builder.')


if __name__ == '__main__':
    main()
