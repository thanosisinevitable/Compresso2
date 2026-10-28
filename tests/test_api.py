import time
from fastapi.testclient import TestClient
import main


def wait(client, identity, headers):
    for _ in range(200):
        response=client.get('/jobs/'+identity,headers=headers).json()
        if response['state'] not in {'queued','running'}:return response
        time.sleep(.01)
    raise AssertionError('Job did not finish')


def test_authenticated_jobs_errors_concurrency_and_cancellation(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'TOKEN','test-only-token')
    headers={'x-compresso-token':'test-only-token'}
    sample=tmp_path/'sample.bin';sample.write_bytes(bytes(range(256))*8)
    with TestClient(main.app) as client:
        assert client.get('/health').status_code==401
        assert client.get('/health',headers=headers).json()['ready']
        assert client.post('/jobs',json={'kind':'unknown','paths':[str(sample)]},headers=headers).status_code==400
        response=client.post('/jobs',json={'kind':'entropy','paths':[str(sample)]},headers=headers)
        result=wait(client,response.json()['id'],headers)
        assert result['state']=='done' and result['result']['entropy']==8
        assert client.get('/jobs/unknown',headers=headers).status_code==404
        missing=client.post('/jobs',json={'kind':'entropy','paths':[str(tmp_path/'missing')]},headers=headers).json()['id']
        assert wait(client,missing,headers)['state']=='error'

        def slow_compress(_paths,_options,job):
            for _ in range(500):
                job.check();time.sleep(.01)
            return {}
        monkeypatch.setattr(main,'compress',slow_compress)
        identities=[client.post('/jobs',json={'kind':'compress','paths':[str(sample)]},headers=headers).json()['id'] for _ in range(2)]
        assert client.post('/jobs',json={'kind':'entropy','paths':[str(sample)]},headers=headers).status_code==409
        for identity in identities:assert client.post('/jobs/'+identity+'/cancel',json={},headers=headers).status_code==200
        for identity in identities:assert wait(client,identity,headers)['state']=='cancelled'
