"""Private loopback API; Electron owns the token, port and process lifetime."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageOps
import uvicorn
from common import Cancelled
from compressor import compress, ghostscript


@dataclass
class Job:
    kind: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = 'queued'
    message: str = 'Waiting'
    current: int = 0
    total: int = 0
    result: dict | None = None
    error: str | None = None
    parent_id: str | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)
    # macOS temp roots commonly use /var -> /private/var. Store canonical paths
    # so our own comparison files pass the same strict checks as picked files.
    directory: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix='compresso-')).resolve())
    lock: threading.Lock = field(default_factory=threading.Lock)
    touched: float = field(default_factory=time.monotonic)

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def progress(self, message, current=0, total=0):
        self.check()
        with self.lock:
            self.message, self.current, self.total = message, current, total

    def public(self):
        with self.lock:
            return {k: getattr(self, k) for k in ('id', 'kind', 'state', 'message', 'current', 'total', 'result', 'error')}


jobs = {}
registry_lock = threading.Lock()
thumbnail_slots = threading.BoundedSemaphore(2)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='compresso')
TOKEN = os.environ.get('COMPRESSO_TOKEN', '')


@asynccontextmanager
async def lifespan(_app):
    yield
    for job in list(jobs.values()):
        job.cancelled.set()
    executor.shutdown(wait=True, cancel_futures=True)
    for job in list(jobs.values()):
        shutil.rmtree(job.directory, ignore_errors=True)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware('http')
async def authenticate(request: Request, call_next):
    if not TOKEN or not secrets.compare_digest(request.headers.get('x-compresso-token', ''), TOKEN):
        return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
    return await call_next(request)


@app.get('/health')
def health():
    return {'ready': True, 'ghostscript': bool(ghostscript()), 'version': '2.2.0'}


class JobRequest(BaseModel):
    kind: str
    paths: list[str] = Field(default_factory=list, max_length=20000)
    options: dict = Field(default_factory=dict)


def run_job(job, request):
    try:
        job.state = 'running'
        job.check()
        if request.kind == 'compress':
            result = compress(request.paths, request.options, job)
        elif request.kind == 'scan':
            from duplicates import scan
            result = scan(request.paths[0], request.options, job)
        elif request.kind == 'target':
            from imaging import target_lock
            result = target_lock(request.paths, request.options, job)
        elif request.kind == 'lens':
            from imaging import compare
            result = compare(request.paths, request.options, job)
        elif request.kind.startswith('vault-'):
            from vault import create, inspect, restore
            result = {'vault-create': create, 'vault-open': inspect, 'vault-restore': restore}[request.kind](request.paths, request.options, job)
        else:
            from entropy import analyze
            result = analyze(request.paths[0], job)
        job.check()
        with job.lock:
            job.result, job.state = result, 'done'
    except Cancelled:
        job.state, job.message = 'cancelled', 'Cancelled'
    except Exception as error:
        job.state, job.error = 'error', str(error) or type(error).__name__
        print(f'{job.kind}: {job.error}', file=sys.stderr, flush=True)
    finally:
        job.touched = time.monotonic()
        if job.state != 'done':
            shutil.rmtree(job.directory, ignore_errors=True)


@app.post('/jobs')
def start(request: JobRequest):
    if request.kind not in {'compress', 'scan', 'entropy', 'target', 'lens', 'vault-create', 'vault-open', 'vault-restore'} or not request.paths:
        raise HTTPException(400, 'Choose an operation and input files.')
    if request.kind in {'scan', 'entropy', 'vault-open', 'vault-restore'} and len(request.paths) != 1:
        raise HTTPException(400, 'Choose one input for this operation.')
    if request.kind == 'lens' and len(request.paths) != 2:
        raise HTTPException(400, 'Choose an original and an output to compare.')
    with registry_lock:
        if sum(j.state in {'queued', 'running'} for j in jobs.values()) >= 2:
            raise HTTPException(409, 'Two operations are already running. Wait or cancel one.')
        pinned = {j.parent_id for j in jobs.values() if j.state in {'queued', 'running'}}
        parent_id = request.options.get('parentJob') if request.kind == 'lens' else None
        if parent_id:
            pinned.add(parent_id)
        finished = sorted((j for j in jobs.values() if j.state not in {'queued', 'running'} and j.id not in pinned), key=lambda j: j.touched)
        while len(jobs) >= 12 and finished:
            old = finished.pop(0)
            jobs.pop(old.id)
            shutil.rmtree(old.directory, ignore_errors=True)
        job = Job(request.kind, parent_id=parent_id)
        jobs[job.id] = job
        executor.submit(run_job, job, request)
    return {'id': job.id}


def get_job(job_id):
    if job_id not in jobs:
        raise HTTPException(404, 'This result expired. Run the operation again.')
    return jobs[job_id]


@app.get('/jobs/{job_id}')
def status(job_id: str):
    return get_job(job_id).public()


@app.post('/jobs/{job_id}/cancel')
def cancel(job_id: str):
    get_job(job_id).cancelled.set()
    return {'ok': True}


class Selection(BaseModel):
    paths: list[str] = Field(max_length=20000)


@app.post('/jobs/{job_id}/cleanup-check')
def cleanup_check(job_id: str, request: Selection):
    from duplicates import validate_cleanup
    job = get_job(job_id)
    if job.kind != 'scan' or job.state != 'done':
        raise HTTPException(400, 'Finish a scan before choosing duplicates.')
    try:
        return validate_cleanup(job.result, request.paths)
    except (ValueError, OSError) as error:
        raise HTTPException(409, str(error)) from error


class ThumbnailRequest(BaseModel):
    path: str


@app.post('/jobs/{job_id}/thumbnail')
def thumbnail(job_id: str, request: ThumbnailRequest):
    import base64
    import io
    from common import fingerprint
    job = get_job(job_id)
    if job.kind != 'scan' or not job.result:
        raise HTTPException(400, 'Scan results are not ready.')
    record = next((f for g in job.result['groups'] for f in g['files'] if f['path'] == request.path), None)
    if not record or not record['image']:
        return {'data': None}
    try:
        if fingerprint(Path(request.path)) != record['fingerprint']:
            return {'data': None}
        with thumbnail_slots, Image.open(request.path) as image:
            image.draft('RGB', (160, 120))
            image = ImageOps.exif_transpose(image)
            image.thumbnail((160, 120))
            buffer = io.BytesIO()
            image.convert('RGB').save(buffer, 'JPEG', quality=70)
            return {'data': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()}
    except (OSError, ValueError, Image.DecompressionBombError):
        return {'data': None}



class AssetRequest(BaseModel):
    key: str


@app.post('/jobs/{job_id}/asset')
def asset(job_id: str, request: AssetRequest):
    import base64
    job = get_job(job_id)
    if job.kind != 'lens' or job.state != 'done' or request.key not in {'original','compressed','difference','heatmap'}:
        raise HTTPException(400, 'Comparison image unavailable.')
    path = Path(job.result['assets'][request.key])
    return {'data': 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()}

def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    if not TOKEN:
        raise SystemExit('COMPRESSO_TOKEN must be set. Launch this backend through Electron.')
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
    if args.parent_pid:
        def watch_parent():
            sys.stdin.buffer.read()
            for job in list(jobs.values()):
                job.cancelled.set()
            server.should_exit = True
        threading.Thread(target=watch_parent, daemon=True).start()
    print(json.dumps({'event': 'ready', 'port': listener.getsockname()[1]}), flush=True)
    server.run(sockets=[listener])


if __name__ == '__main__':
    serve()
