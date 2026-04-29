# ==============================================================================
# File: dashboard.py
# Version: 5.0.0 (Modular refactor)
# Date: 2026-04-26
# Maintainer: Team-9 Secure Skies
# Description: Entry-point for the SECURESKIES MLAT Tactical Hub.
#              All heavy logic has been moved to sibling modules so this
#              file is limited to Flask/SocketIO bootstrap and glue.
#              Modules: config, state, mlat, utils, mqtt_handler, html.
# ==============================================================================
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="eventlet")
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import logging

import config                # loads env constants first
from page_template import HTML_TEMPLATE
import mqtt_handler as mqtt

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Flask / SocketIO
# ------------------------------------------------------------------------------
app = Flask(__name__)
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
)

# Inject the SocketIO instance so mqtt_handler can broadcast map_update.
mqtt.set_socketio(socketio)


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    mqtt.start_mqtt()
    
@socketio.on('inject_demo')
def handle_inject(data):
    """Expert mode: inject a fake aircraft for demo purposes."""
    import time
    data['_injected'] = True
    data['_inject_ts'] = time.time()
    # Add to state so it appears in next map_update
    from state import state
    hex_id = data.get('hex', '00dead')
    state['aircraft'][hex_id] = data
    state['aircraft'][hex_id]['trail'] = [(data['lat'], data['lon'])]
    state['aircraft'][hex_id]['last_seen'] = time.time()
    state['aircraft'][hex_id]['seen_by'] = data.get('seen_by', ['sensor-north'])
    # Auto-remove after 30 seconds
    import threading
    def cleanup():
        state['aircraft'].pop(hex_id, None)
    threading.Timer(30.0, cleanup).start()

socketio.run(app, host="0.0.0.0", port=8080)
