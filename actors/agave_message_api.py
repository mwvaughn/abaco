from flask import Flask, g
from flask_cors import CORS

from request_utils import AgaveApi, handle_error
from auth import authn_and_authz
from controllers import MessagesResource

app = Flask(__name__)
CORS(app)
api = AgaveApi(app)

# Authn/z
@app.before_request
def auth():
    g.token = 'N/A'
    g.user = 'AGAVE'
    g.tenant = 'AGAVE-PROD'
    g.api_server = 'https://public.agaveapi.co'

# Set up error handling
@app.errorhandler(Exception)
def handle_all_errors(e):
    return handle_error(e)

# Resources
api.add_resource(MessagesResource, '/agave/<string:actor_id>/messages')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
