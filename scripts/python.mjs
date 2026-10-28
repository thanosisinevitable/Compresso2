import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
const python = process.env.COMPRESSO_PYTHON || path.resolve('.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) { console.error('Create .venv and install backend/requirements-dev.txt first; see README.md.'); process.exit(1); }
const child = spawn(python, process.argv.slice(2), {stdio:'inherit'});
child.on('error', error => {console.error(error.message);process.exitCode=1;});
child.on('exit', code => {process.exitCode=code ?? 1;});
