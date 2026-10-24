import ast, json, os, subprocess, time, urllib.error, urllib.request, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PROJECT="estacionamiento-sensors-it"; GATEWAY="http://127.0.0.1:18080"
COMPOSE=["docker","compose","-p",PROJECT,"-f","docker-compose.yml","-f","docker-compose.integration.yml"]
ENV={**os.environ,"GATEWAY_PORT":"18080","SENSOR_SIMULATOR_ENABLED":"true"}
def run(*args,check=True):
    result=subprocess.run([*COMPOSE,*args],cwd=ROOT,env=ENV,capture_output=True,text=True,encoding="utf-8",errors="replace")
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
def state():
    output=run("exec","-T","sensores","python","scripts/inspect_state.py")
    return ast.literal_eval(output.splitlines()[-1])
def test_contract():
    email=f"sensor-{uuid.uuid4()}@example.com"; password="integration-password-123"
    assert request("POST",f"{GATEWAY}/api/v1/usuarios/registro",{"name":"Sensor User","email":email,"password":password})[0]==201
    _,login=request("POST",f"{GATEWAY}/api/v1/usuarios/login",{"email":email,"password":password})
    auth={"Authorization":f"Bearer {login['access_token']}"}
    _,parkings=request("GET",f"{GATEWAY}/api/v1/parkings",headers=auth); parking_id=parkings[0]["id"]
    def spot(): return request("GET",f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas",headers=auth)[1][0]
    wait(lambda:spot()["availability"]=="available","El simulador no publico el estado libre")
    before=state()["sequence"]; assert before>0
    run("exec","-T","sensores","python","scripts/set_state.py","--occupied","true")
    wait(lambda:spot()["availability"]=="occupied","El cambio físico no fue publicado")
    run("restart","sensores")
    wait(lambda:state()["sequence"]>before,"La secuencia no continuo tras reiniciar")
    run("stop","rabbitmq")
    wait(lambda:state()["pending_event"] is not None,"No se persistio el evento pendiente",timeout=20)
    pending=state()["pending_event"]
    assert state()["pending_event"]["event_id"]==pending["event_id"]
    run("start","rabbitmq")
    wait(lambda:state()["pending_event"] is None,"No se confirmo el evento pendiente",timeout=60)
    wait(lambda:spot()["version"]>=2,"Parkings no proceso el reporte recuperado")
def main():
    print(f"Levantando pila aislada {PROJECT}..."); run("down","-v","--remove-orphans",check=False)
    try:
        run("up","--build","-d","--wait"); test_contract()
        print("OK: integracion de Sensores, secuencia durable, estado físico y recuperacion de RabbitMQ")
    finally: run("down","-v","--remove-orphans",check=False)
if __name__=="__main__": main()
