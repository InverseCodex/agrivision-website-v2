# app.py (copy-paste ready)
from flask import Flask, render_template, request, redirect, session
from werkzeug.exceptions import HTTPException
from supabase import create_client, Client
from datetime import datetime, timedelta
import secrets
import os
import uuid
import traceback
import requests
import subprocess
import tempfile
import json

# =========================
# SUPABASE SETTINGS
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

IMAGE_BUCKET = os.getenv("SUPABASE_IMAGE_BUCKET", "image_transmission")

PAIR_EXP_MINUTES = 10

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TF_PYTHON = os.getenv("TF_PYTHON", os.path.join(BASE_DIR, ".venv_tf", "Scripts", "python.exe"))
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(BASE_DIR, "models", "CROP_MODEL.h5"))
MODEL_INPUT_SIZE = os.getenv("MODEL_INPUT_SIZE", "224,224")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_change_me")


# =========================
# ERROR HANDLER (doesn't break 404)
# =========================
@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    print("UNHANDLED EXCEPTION:", e)
    traceback.print_exc()
    return {"error": "server exception", "detail": str(e)}, 500


# =========================
# PAGES
# =========================
@app.route("/")
def home():
    if "username" not in session:
        return redirect("/login")
    return render_template("index.html", username=session["username"], user_id=session["user_id"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["user"]
        password = request.form["pass"]

        existing_user = supabase.table("userAccounts").select("*").eq("email", email).execute()
        if existing_user.data and len(existing_user.data) > 0:
            return render_template("register.html", error="Email already registered")

        user_id = str(uuid.uuid4())

        response = supabase.table("userAccounts").insert({
            "user_id": user_id,
            "username": username,
            "password": password,  # TODO: hash later
            "email": email
        }).execute()

        if response.data is not None:
            return redirect("/login")
        return f"Supabase insert error: {response.error}"

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["user"]
        password = request.form["pass"]

        response = supabase.table("userAccounts").select("*").eq("username", username).execute()
        data = response.data

        if not data:
            return "Username not found!"

        user = data[0]

        if password == user["password"]:
            session["username"] = user["username"]
            session["user_id"] = user["user_id"]
            return redirect("/")
        return "Incorrect password!"

    if "username" in session:
        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# DEVICE PAIRING
# =========================
@app.route("/requests/create", methods=["POST"])
def create_device_request():
    if "user_id" not in session:
        return redirect("/login")

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    pair_code = (
        "".join(secrets.choice(alphabet) for _ in range(4))
        + "-"
        + "".join(secrets.choice("0123456789") for _ in range(4))
    )

    expires_at = (datetime.utcnow() + timedelta(minutes=PAIR_EXP_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

    resp = supabase.table("deviceRequests").insert({
        "requested_by": session["user_id"],
        "status": "pending",
        "pair_code": pair_code,
        "expires_at": expires_at
    }).execute()

    if not resp.data:
        return {"error": f"Supabase error: {resp.error}"}, 500

    row = resp.data[0]
    return {
        "request_id": row["id"],
        "pair_code": row["pair_code"],
        "expires_at": row.get("expires_at"),
        "status": row.get("status")
    }


@app.route("/device/connect", methods=["POST"])
def device_connect():
    payload = request.get_json(silent=True) or {}
    pair_code = payload.get("pair_code")

    if not pair_code:
        return {"error": "pair_code required"}, 400

    resp = supabase.table("deviceRequests").select("*").eq("pair_code", pair_code).execute()
    if not resp.data:
        return {"error": "invalid pair_code"}, 404

    req_row = resp.data[0]

    if req_row.get("status") != "pending":
        return {"error": f"request not pending (status={req_row.get('status')})"}, 400

    if req_row.get("expires_at"):
        try:
            exp = datetime.fromisoformat(req_row["expires_at"].replace("Z", ""))
            if datetime.utcnow() > exp:
                supabase.table("deviceRequests").update({"status": "expired"}).eq("id", req_row["id"]).execute()
                return {"error": "pair_code expired"}, 400
        except Exception:
            pass

    device_id = str(uuid.uuid4())

    upd = supabase.table("deviceRequests").update({
        "status": "paired",
        "paired_device_id": device_id
    }).eq("id", req_row["id"]).execute()

    if not upd.data:
        return {"error": f"update failed: {upd.error}"}, 500

    return {
        "message": "paired",
        "request_id": req_row["id"],
        "device_id": device_id,
        "requested_by": req_row["requested_by"],
        "requested_at": req_row.get("requested_at")
    }


@app.route("/device/connect_user", methods=["POST"])
def device_connect_user():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if not user_id:
        return {"error": "user_id required"}, 400

    u = supabase.table("userAccounts").select("user_id").eq("user_id", user_id).execute()
    if not u.data:
        return {"error": "user_id not found"}, 404

    device_id = str(uuid.uuid4())

    req = supabase.table("deviceRequests").insert({
        "requested_by": user_id,
        "status": "paired",
        "pair_code": f"USERLINK-{uuid.uuid4().hex[:6]}",
        "paired_device_id": device_id,
    }).execute()

    if not req.data:
        return {"error": f"create request failed: {req.error}"}, 500

    row = req.data[0]
    return {"message": "paired", "request_id": row["id"], "device_id": device_id}


# =========================
# DEVICE -> WEBSITE IMAGE UPLOAD
# =========================
@app.route("/device/upload", methods=["POST"])
def device_upload():
    request_id = request.form.get("request_id")
    device_id = request.form.get("device_id")
    file = request.files.get("image")

    if not request_id or not file:
        return {"error": "request_id and image file required"}, 400

    resp = supabase.table("deviceRequests").select("*").eq("id", request_id).execute()
    if not resp.data:
        return {"error": "invalid request_id"}, 404

    req_row = resp.data[0]
    if req_row.get("status") != "paired":
        return {"error": f"request not paired (status={req_row.get('status')})"}, 400

    if device_id and req_row.get("paired_device_id") and str(device_id) != str(req_row["paired_device_id"]):
        return {"error": "device_id does not match paired device"}, 403

    requested_by = req_row["requested_by"]

    original_name = file.filename or "image"
    ext = ""
    if "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[1].lower()

    storage_name = f"{uuid.uuid4()}{ext}"
    storage_path = f"{request_id}/{requested_by}/{storage_name}"

    file_bytes = file.read()
    content_type = file.mimetype or "application/octet-stream"

    storage = supabase.storage.from_(IMAGE_BUCKET)
    up = storage.upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type}
    )

    if isinstance(up, dict) and up.get("error"):
        return {"error": up["error"]}, 500

    ins = supabase.table("requestImages").insert({
        "request_id": request_id,
        "requested_by": requested_by,
        "image_path": storage_path,
        "original_filename": original_name,
        "content_type": content_type
    }).execute()

    if not ins.data:
        return {"error": f"metadata insert failed: {ins.error}"}, 500

    return {"message": "uploaded", "request_id": request_id, "image_path": storage_path}


# =========================
# WEBSITE -> DEVICE MISSION (queue + poll)
# Requires a table: public.deviceMissions (jsonb mission, status, request_id, device_id)
# =========================
@app.route("/mission/upload", methods=["POST"])
def mission_upload():
    """
    Called by your website when you click UPLOAD MISSION.
    It queues the mission for the latest paired device of this user.
    Accepts JSON body:
      { "target": { "lat":..., "lng":..., "alt_m":... }, ... }
    """
    if "user_id" not in session:
        return {"error": "Not logged in"}, 401

    payload = request.get_json(silent=True) or {}
    mission = payload.get("mission") or payload

    tgt = (mission or {}).get("target") or {}
    if tgt.get("lat") is None or tgt.get("lng") is None or tgt.get("alt_m") is None:
        return {"error": "target.lat, target.lng, target.alt_m required"}, 400

    user_id = session["user_id"]

    # Find latest paired device request for this user
    r = (
        supabase.table("deviceRequests")
        .select("id, status, paired_device_id, requested_by, requested_at")
        .eq("requested_by", user_id)
        .eq("status", "paired")
        .order("requested_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return {"error": "No paired device found. Pair your Raspberry Pi first."}, 400

    req_row = r.data[0]
    request_id = req_row["id"]
    device_id = req_row.get("paired_device_id")
    if not device_id:
        return {"error": "paired_device_id missing for this request"}, 400

    ins = (
        supabase.table("deviceMissions")
        .insert({
            "request_id": request_id,
            "requested_by": user_id,
            "device_id": device_id,
            "mission": mission,
            "status": "pending",
        })
        .execute()
    )

    if not ins.data:
        return {"error": f"mission queue insert failed: {ins.error}"}, 500

    return {
        "message": "mission queued",
        "request_id": request_id,
        "device_id": device_id,
        "mission_id": ins.data[0]["id"],
    }


@app.route("/device/mission/poll", methods=["POST"])
def device_mission_poll():
    """
    Called by Raspberry Pi (polling):
      POST { "request_id": "...", "device_id": "..." }
    Returns:
      { "mission": null } or { "mission_id": "...", "mission": {...} }
    """
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    device_id = payload.get("device_id")

    if not request_id or not device_id:
        return {"error": "request_id and device_id required"}, 400

    # Verify request is paired and device matches
    r = supabase.table("deviceRequests").select("id, status, paired_device_id").eq("id", request_id).execute()
    if not r.data:
        return {"error": "invalid request_id"}, 404

    req_row = r.data[0]
    if req_row.get("status") != "paired":
        return {"error": "not paired"}, 400
    if str(req_row.get("paired_device_id")) != str(device_id):
        return {"error": "device mismatch"}, 403

    # Get newest pending mission
    m = (
        supabase.table("deviceMissions")
        .select("id, mission, created_at")
        .eq("request_id", request_id)
        .eq("device_id", device_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not m.data:
        return {"mission": None}

    row = m.data[0]

    # Mark delivered
    supabase.table("deviceMissions").update({
        "status": "delivered",
        "delivered_at": datetime.utcnow().isoformat()
    }).eq("id", row["id"]).execute()

    return {"mission_id": row["id"], "mission": row["mission"], "created_at": row.get("created_at")}


# =========================
# HISTORY + ANALYSIS
# =========================
@app.route("/history/images")
def history_images():
    if "user_id" not in session:
        return {"error": "Not logged in"}, 401

    user_id = session["user_id"]

    resp = (
        supabase.table("requestImages")
        .select("id, image_path, original_filename, uploaded_at, request_id")
        .eq("requested_by", user_id)
        .order("uploaded_at", desc=True)
        .execute()
    )

    rows = resp.data or []
    public_base = f"{SUPABASE_URL}/storage/v1/object/public/{IMAGE_BUCKET}/"

    images = []
    for r in rows:
        images.append({
            "id": r["id"],
            "url": public_base + r["image_path"],
            "image_path": r["image_path"],
            "request_id": r["request_id"],
            "filename": r.get("original_filename"),
            "uploaded_at": r.get("uploaded_at")
        })

    return {"images": images}


@app.route("/analysis/run", methods=["POST"])
def analysis_run():
    if "user_id" not in session:
        return {"error": "Not logged in"}, 401

    payload = request.get_json(silent=True) or {}
    image_id = payload.get("image_id")
    if not image_id:
        return {"error": "image_id required"}, 400

    resp = (
        supabase.table("requestImages")
        .select("id, requested_by, image_path, request_id")
        .eq("id", image_id)
        .execute()
    )
    if not resp.data:
        return {"error": "image not found"}, 404

    row = resp.data[0]

    if row["requested_by"] != session["user_id"]:
        return {"error": "forbidden"}, 403

    public_base = f"{SUPABASE_URL}/storage/v1/object/public/{IMAGE_BUCKET}/"
    original_url = public_base + row["image_path"]

    r = requests.get(original_url, timeout=30)
    if r.status_code != 200:
        return {"error": "failed to fetch original image"}, 500

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "input.jpg")
        out_path = os.path.join(td, "output.png")

        with open(in_path, "wb") as f:
            f.write(r.content)

        cmd = [
            TF_PYTHON,
            "ml_infer.py",
            "--model", MODEL_PATH,
            "--input", in_path,
            "--output", out_path,
            "--size", MODEL_INPUT_SIZE
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"error": "ml failed", "detail": proc.stderr}, 500

        try:
            ml_json = json.loads((proc.stdout or "").strip() or "{}")
        except Exception:
            return {"error": "ml output parse failed", "detail": proc.stdout}, 500

        if not os.path.exists(out_path):
            return {"error": "ml did not produce output"}, 500

        with open(out_path, "rb") as f:
            result_png_bytes = f.read()

    result_path = f"results/{row['request_id']}/{row['requested_by']}/{uuid.uuid4()}.png"
    storage = supabase.storage.from_(IMAGE_BUCKET)

    up = storage.upload(
        path=result_path,
        file=result_png_bytes,
        file_options={"content-type": "image/png"}
    )

    if isinstance(up, dict) and up.get("error"):
        return {"error": up["error"]}, 500

    result_url = public_base + result_path

    return {
        "original_url": original_url,
        "result_url": result_url,
        "metrics": {"health_score": ml_json.get("health_score", 0)}
    }


# =========================
# GEOJSON (testing)
# =========================
@app.route("/geojson/targets")
def geojson_targets():
    sample = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Target A"},
                "geometry": {"type": "Point", "coordinates": [120.9842, 14.5995]}
            },
            {
                "type": "Feature",
                "properties": {"name": "Target B"},
                "geometry": {"type": "Point", "coordinates": [121.0500, 14.6500]}
            }
        ]
    }
    return sample
@app.route("/device/missions/latest", methods=["GET"])
def device_missions_latest():
    """
    Raspberry Pi polls this:
      GET /device/missions/latest?user_id=...

    Returns latest pending mission for that user (requested_by).
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return {"error": "user_id required"}, 400

    resp = (
        supabase.table("deviceMissions")
        .select("id, mission, status, created_at")
        .eq("requested_by", user_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not resp.data:
        return {"mission": None}, 200

    row = resp.data[0]
    return {
        "mission_id": row["id"],
        "mission": row["mission"],
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }, 200


@app.route("/device/missions/ack", methods=["POST"])
def device_missions_ack():
    """
    Raspberry Pi ACK after it saves mission.json:
      POST /device/missions/ack
      { "mission_id": "...", "user_id": "..." }

    Marks mission delivered so it won't be returned again.
    """
    payload = request.get_json(silent=True) or {}
    mission_id = payload.get("mission_id")
    user_id = payload.get("user_id")

    if not mission_id or not user_id:
        return {"error": "mission_id and user_id required"}, 400

    # (Optional) ensure this mission belongs to that user
    check = (
        supabase.table("deviceMissions")
        .select("id, requested_by, status")
        .eq("id", mission_id)
        .limit(1)
        .execute()
    )

    if not check.data:
        return {"error": "mission not found"}, 404

    row = check.data[0]
    if row["requested_by"] != user_id:
        return {"error": "forbidden"}, 403

    upd = (
        supabase.table("deviceMissions")
        .update({
            "status": "delivered",
            "delivered_at": datetime.utcnow().isoformat()
        })
        .eq("id", mission_id)
        .execute()
    )

    if not upd.data:
        return {"error": f"ack update failed: {upd.error}"}, 500

    return {"message": "acked", "mission_id": mission_id}, 200


if __name__ == "__main__":
    app.run(debug=True)
