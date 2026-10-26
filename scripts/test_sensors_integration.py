import ast, json, os, subprocess, time, urllib.error, urllib.request, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PROJECT="estacionamiento-sensors-it"; GATEWAY="http://127.0.0.1:18080"
COMPOSE=["docker","compose","-p",PROJECT,"-f","docker-compose.yml","-f","docker-compose.integration.yml"]
ENV={**os.environ,"GATEWAY_PORT":"18080","SENSOR_SIMULATOR_ENABLED":"true",
     "INTEGRATION_SENSOR_FRESH_SECONDS":"5"}
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
def states():
    output=run("exec","-T","sensores","python","scripts/inspect_state.py","--all")
    return ast.literal_eval(output.splitlines()[-1])
def test_contract():
    email=f"sensor-{uuid.uuid4()}@example.com"; password="integration-password-123"
    assert request("POST",f"{GATEWAY}/api/v1/usuarios/registro",{"name":"Sensor User","email":email,"password":password})[0]==201
    _,login=request("POST",f"{GATEWAY}/api/v1/usuarios/login",{"email":email,"password":password})
    auth={"Authorization":f"Bearer {login['access_token']}"}
    _,admin_login=request("POST",f"{GATEWAY}/api/v1/usuarios/login",
        {"email":"admin-integration@example.com","password":"integration-admin-password"})
    admin={"Authorization":f"Bearer {admin_login['access_token']}"}
    _,parkings=request("GET",f"{GATEWAY}/api/v1/parkings",headers=auth); parking_id=parkings[0]["id"]
    def spot(): return request("GET",f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas",headers=auth)[1][0]
    wait(lambda:spot()["availability"]=="available","El simulador no publico el estado libre")
    assert request("GET",f"{GATEWAY}/api/v1/simulacion/sensores",headers=auth)[0]==403
    status,sensors=request("GET",f"{GATEWAY}/api/v1/simulacion/sensores",headers=admin)
    assert status==200 and len(sensors)==168
    target=next(item for item in sensors if item["label"]=="C-12")
    assert request("PUT",f"{GATEWAY}/api/v1/simulacion/sensores/C-12",{"failed":True},admin)[1]["status"]=="stopped"
    def target_spot():
        values=request("GET",f"{GATEWAY}/api/v1/parkings/{parking_id}/plazas",headers=auth)[1]
        return next(item for item in values if item["id"]==target["spot_id"])
    wait(lambda:target_spot()["availability"]=="unknown","El fallo no vencio el sensor individual",timeout=20)
    def has_alert():
        status,body=request("GET",f"{GATEWAY}/api/v1/metricas/alertas?limit=100",headers=admin)
        return status==200 and any(item["label"]=="C-12" for item in body["items"])
    wait(has_alert,"Metricas no mostro la alerta de C-12",timeout=20)
    assert request("PUT",f"{GATEWAY}/api/v1/simulacion/sensores/C-12",{"failed":False},admin)[1]["status"]=="active"
    wait(lambda:target_spot()["availability"]=="available","El sensor C-12 no se recupero",timeout=20)
    wait(lambda:not has_alert(),"La alerta de C-12 no desaparecio",timeout=20)
    before=state()["sequence"]; assert before>0
    run("exec","-T","sensores","python","scripts/set_state.py","--occupied","true")
    wait(lambda:spot()["availability"]=="occupied","El cambio físico no fue publicado")
    run("restart","sensores")
    wait(lambda:state()["sequence"]>before,"La secuencia no continuo tras reiniciar")
    run("stop","rabbitmq")
    wait(lambda:any(item["pending_event"] is not None for item in states()),
         "No se persistio el evento pendiente",timeout=20)
    pending_sensor=next(item for item in states() if item["pending_event"] is not None)
    pending=pending_sensor["pending_event"]
    assert next(item for item in states() if item["sensor_id"]==pending_sensor["sensor_id"])["pending_event"]["event_id"]==pending["event_id"]
    run("start","rabbitmq")
    wait(lambda:all(item["pending_event"] is None for item in states()),
         "No se confirmo el evento pendiente",timeout=60)
    wait(lambda:spot()["version"]>=2,"Parkings no proceso el reporte recuperado")
def main():
    print(f"Levantando pila aislada {PROJECT}..."); run("down","-v","--remove-orphans",check=False)
    try:
        run("up","--build","-d","--wait"); test_contract()
        print("OK: simulacion individual, alertas, recuperacion, secuencia durable y RabbitMQ")
    finally: run("down","-v","--remove-orphans",check=False)
if __name__=="__main__": main()
