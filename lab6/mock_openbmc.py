from flask import Flask, jsonify, request, make_response
import base64

app = Flask(__name__)

VALID_USER = "root"
VALID_PASS = "0penBmc"

def check_auth():
    auth = request.headers.get("Authorization")
    if not auth:
        return False
    try:
        auth_type, credentials = auth.split(" ", 1)
        if auth_type.lower() != "basic":
            return False
        decoded = base64.b64decode(credentials).decode("utf-8")
        user, password = decoded.split(":", 1)
        return user == VALID_USER and password == VALID_PASS
    except Exception:
        return False

def authenticate():
    return make_response(
        jsonify({"error": "Unauthorized"}), 
        401,
        {"WWW-Authenticate": 'Basic realm="OpenBMC"'}
    )

@app.route("/redfish/v1/")
def redfish_root():
    if not check_auth():
        return authenticate()
    return jsonify({
        "@odata.id": "/redfish/v1/",
        "Systems": {"@odata.id": "/redfish/v1/Systems"},
        "Chassis": {"@odata.id": "/redfish/v1/Chassis"},
        "Managers": {"@odata.id": "/redfish/v1/Managers"}
    })

@app.route("/redfish/v1/Systems/system")
def system_info():
    if not check_auth():
        return authenticate()
    return jsonify({
        "@odata.id": "/redfish/v1/Systems/system",
        "Id": "system",
        "Name": "System",
        "PowerState": "On",
        "Status": {"State": "Enabled", "Health": "OK"},
        "BiosVersion": "v2.0",
        "Manufacturer": "MockVendor",
        "Model": "MockServer"
    })

if __name__ == "__main__":
    print("Запуск mock OpenBMC на http://localhost:5000")
    print("Логин: root, Пароль: 0penBmc")
    app.run(host="0.0.0.0", port=5000, ssl_context="adhoc")