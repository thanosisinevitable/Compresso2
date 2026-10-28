"""Exercise the frozen/native backend before it is included in the Mac app."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundled', action='store_true')
    parser.add_argument('--executable', type=Path, help='Test an explicit frozen backend executable')
    args = parser.parse_args()
    token = secrets.token_hex(32)
    env = {**os.environ, 'COMPRESSO_TOKEN': token}
    if args.executable:
        command = [str(args.executable.resolve())]
    elif args.bundled:
        executable = ROOT / 'build/backend/compresso-backend/compresso-backend'
        command = [str(executable)]
        gs = ROOT / 'build/ghostscript'
        env.update(COMPRESSO_GS=str(gs/'bin/gs'), GS_LIB=os.pathsep.join(str(gs/'share'/p) for p in ['Resource/Init','lib','Resource/Font']))
    else:
        command = [sys.executable, '-u', str(ROOT/'backend/main.py')]
    process = subprocess.Popen(command+['--parent-pid',str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        # communicate is deliberately not used: closing stdin is the shutdown signal.
        import selectors
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=45):
            raise RuntimeError('Backend startup timed out.')
        line = process.stdout.readline()
        if not line:
            raise RuntimeError('Backend failed: '+process.stderr.read())
        ready = json.loads(line)
        base = f'http://127.0.0.1:{ready["port"]}'

        def request(route, body=None, authenticated=True):
            data = json.dumps(body).encode() if body is not None else None
            headers = {'Content-Type':'application/json'}
            if authenticated:
                headers['x-compresso-token'] = token
            with urllib.request.urlopen(urllib.request.Request(base+route,data=data,headers=headers),timeout=10) as response:
                return json.load(response)
        for _ in range(100):
            try:
                health = request('/health')
                break
            except (OSError, urllib.error.URLError):
                time.sleep(.1)
        else:
            raise RuntimeError('Backend never became healthy.')
        try:
            request('/health', authenticated=False)
            raise AssertionError('Unauthenticated request was accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 401
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()
            sample=folder/'sample.bin';sample.write_bytes(bytes(range(256))*128)
            (folder/'copy.bin').write_bytes(sample.read_bytes())
            from PIL import Image, ImageDraw
            im=Image.new('RGB',(300,200),'white');ImageDraw.Draw(im).ellipse((40,30,180,150),fill='red')
            im.save(folder/'photo.png');im.resize((150,100)).save(folder/'small.png')
            from reportlab.pdfgen import canvas
            pdf=canvas.Canvas(str(folder/'sample.pdf'));pdf.drawString(20,100,'Compresso build verification');pdf.save()
            operations=[('entropy',[str(sample)],{}),('scan',[str(folder)],{'threshold':8}),('compress',[str(folder/'sample.pdf')],{'pdfQuality':'High'}),('compress',[str(folder/'photo.png')],{'outputFormat':'jpg'}),('compress',[str(folder/'sample.pdf')],{'outputFormat':'png','pdfDpi':72}),('target',[str(folder/'photo.png')],{'targetBytes':8000}),('vault-create',[str(sample),str(folder/'copy.bin')],{})]
            for kind, paths, options in operations:
                identity=request('/jobs',{'kind':kind,'paths':paths,'options':options})['id']
                for _ in range(600):
                    job=request('/jobs/'+identity)
                    if job['state'] not in {'queued','running'}:
                        break
                    time.sleep(.1)
                assert job['state']=='done',job
                if kind=='entropy':assert job['result']['entropy']==8
                if kind=='scan':assert job['result']['exactGroups']>=1 and job['result']['similarGroups']>=1
                if kind=='compress':
                    if options.get('outputFormat') in {'jpg','png'}:
                        with Image.open(job['result']['artifact']) as actual:
                            assert actual.format=={'jpg':'JPEG','png':'PNG'}[options['outputFormat']]
                    else:assert Path(job['result']['artifact']).read_bytes().startswith(b'%PDF')
                if kind=='target':
                    assert job['result']['successCount']==1
                    pair=job['result']['lensPairs'][0]
                    operations.append(('lens',[pair['source'],pair['output']],{'identity':pair['identity']}))
                if kind=='lens':
                    assert job['result']['ssim'] is not None
                    assert request('/jobs/'+identity+'/asset',{'key':'heatmap'})['data'].startswith('data:image/png;base64,')
                if kind=='vault-create':
                    assert job['result']['verified']
                    artifact=job['result']['artifact']
                    operations.append(('vault-open',[artifact],{}))
                    operations.append(('vault-restore',[artifact],{'version':1}))
                if kind=='vault-open':assert len(job['result']['versions'])==2
                if kind=='vault-restore':assert Path(job['result']['artifact']).read_bytes()==sample.read_bytes()
        assert health['ghostscript'], 'Ghostscript unavailable'
        print('PASS: authenticated startup; entropy; exact/visual scan; PDF; image conversion; PDF raster export; Target Lock; Lens assets; vault create/open/verified restore.')
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill();process.wait();raise RuntimeError('Backend failed to stop after parent pipe closed.')
    assert process.returncode==0,process.stderr.read()
    print('PASS: backend shutdown on parent disconnect.')


if __name__=='__main__':
    main()
