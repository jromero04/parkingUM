import json, logging, time

import pika

from app.config import get_settings
from app.fleet import sensor_states
from app.logging_config import configure_logging


configure_logging(); logger=logging.getLogger("sensores.publisher"); EXCHANGE="sensors.events"
def run():
    settings=get_settings()
    states=sensor_states()
    if not settings.simulator_enabled:
        logger.info("Simulador deshabilitado",extra={"action":"simulator_disabled","result":"idle","correlation_id":None})
        while True: time.sleep(60)
    attempt=0
    while True:
        broker=None
        try:
            broker=pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url)); channel=broker.channel()
            channel.exchange_declare(exchange=EXCHANGE,exchange_type="topic",durable=True); channel.confirm_delivery()
            while True:
                for state in states:
                    if state.is_failed():
                        continue
                    envelope=state.prepare_event(); data=envelope["data"]
                    channel.basic_publish(exchange=EXCHANGE,routing_key="sensor.reported.v1",
                        body=json.dumps(envelope,separators=(",",":")).encode(),mandatory=True,
                        properties=pika.BasicProperties(content_type="application/json",delivery_mode=2,
                            message_id=envelope["event_id"],correlation_id=envelope["correlation_id"],type=envelope["event_type"]))
                    state.confirm(envelope["event_id"]); attempt=0
                    logger.info("",extra={"action":"event_published","result":"success",
                        "correlation_id":envelope["correlation_id"],"event_id":envelope["event_id"],
                        "sensor_id":data["sensor_id"],"spot_id":data["spot_id"],"sequence":data["sequence"]})
                time.sleep(settings.report_interval_seconds)
        except Exception:
            attempt+=1; logger.exception("Se reintentara el mismo reporte",extra={"action":"recovery_attempted",
                "result":"retry","correlation_id":None,"attempt":attempt})
            if broker is not None and broker.is_open: broker.close()
            time.sleep(min(5*attempt,30))
if __name__=="__main__": run()
