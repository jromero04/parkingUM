import json, os, subprocess, time, urllib.error, urllib.request, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; PROJECT="estacionamiento-notifications-it"; GATEWAY="http://127.0.0.1:18080"
COMPOSE=["docker","compose","-p",PROJECT,"-f","docker-compose.yml","-f","docker-compose.integration.yml"]
ENV={**os.environ,"GATEWAY_PORT":"18080","SENSOR_SIMULATOR_ENABLED":"false"}
def run(*args,check=True):
    result=subprocess.run([*COMPOSE,*args],cwd=ROOT,env=ENV,capture_output=True,text=True,
                          encoding="utf-8",errors="replace")
    if check and result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result.stdout.strip()
def request(method,url,body=None,headers=None):
    call=urllib.request.Request(url,method=method,data=json.dumps(body).encode() if body is not None else None,
                                headers={"Content-Type":"application/json",**(headers or {})})
    try:
        with urllib.request.urlopen(call,timeout=15) as response:
            content=response.read().decode(); return response.status,json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        content=exc.read().decode(); return exc.code,json.loads(content) if content else None
def wait(predicate,message,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate(): return
        time.sleep(.5)
    raise AssertionError(message)
def db_rows():
    code=("from sqlalchemy import text; from app.database import SessionLocal; db=SessionLocal(); "
          "rows=db.execute(text('SELECT template,status,reservation_version FROM deliveries ORDER BY created_at')).all(); "
          "print('|'.join(','.join(map(str,row)) for row in rows)); db.close()")
    lines=run("exec","-T","notificaciones-worker","python","-c",code).splitlines()
    return lines[-1] if lines else ""
def main_test():
    email=f"notify-{uuid.uuid4()}@example.com"; password="integration-password-123"
    assert request("POST",f"{GATEWAY}/api/v1/usuarios/registro",
                   {"name":"Notify User","email":email,"password":password})[0]==201
    status,login=request("POST",f"{GATEWAY}/api/v1/usuarios/login",{"email":email,"password":password})
    auth={"Authorization":f"Bearer {login['access_token']}"}
    _,parkings=request("GET",f"{GATEWAY}/api/v1/parkings",headers=auth); parking_id=parkings[0]["id"]
    _,spots=request("GET",f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas",headers=auth); spot_id=spots[0]["id"]
    run("exec","-T","parkings-sensor-worker","python","scripts/publish_sensor_event.py","--occupied","false")
    def available():
        status,values=request("GET",f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas",headers=auth)
        return status==200 and values[0]["availability"]=="available"
    wait(available,"La plaza no quedo disponible")
    status,created=request("POST",f"{GATEWAY}/api/v1/reservas",{"parking_id":parking_id,"spot_id":spot_id},
                           {**auth,"Idempotency-Key":str(uuid.uuid4())})
    assert status==201; reservation_id=created["reservation"]["id"]
    assert request("POST",f"{GATEWAY}/api/v1/reservas/{reservation_id}/cancelacion",headers={
        **auth,"Idempotency-Key":str(uuid.uuid4())})[0]==200
    wait(lambda:"reservation_confirmed,delivered" in db_rows() and "reservation_cancelled,delivered" in db_rows(),
         "No se registraron confirmacion y cancelacion")
    run("stop","parkings")
    status,pending=request("POST",f"{GATEWAY}/api/v1/reservas",{"parking_id":parking_id,"spot_id":spot_id},
                           {**auth,"Idempotency-Key":str(uuid.uuid4())})
    assert status==202; pending_id=pending["reservation"]["id"]
    assert request("POST",f"{GATEWAY}/api/v1/reservas/{pending_id}/cancelacion",headers={
        **auth,"Idempotency-Key":str(uuid.uuid4())})[0]==202
    run("start","parkings")
    wait(lambda:"request_cancelled,delivered" in db_rows(),"No se entrego la cancelacion de solicitud")
    assert email not in run("logs","notificaciones-worker")
def main():
    print(f"Levantando pila aislada {PROJECT}..."); run("down","-v","--remove-orphans",check=False)
    try:
        run("up","--build","-d","--wait"); main_test()
        print("OK: integracion de Notificaciones, destinatarios, plantillas, persistencia y privacidad")
    finally: run("down","-v","--remove-orphans",check=False)
if __name__=="__main__": main()
