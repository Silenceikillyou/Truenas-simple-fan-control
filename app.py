import os
import glob
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Path to the hwmon directory for your nct6797 chip.
# Override with the HWMON_PATH env var if the number changes after a reboot.
HWMON_PATH = os.environ.get("HWMON_PATH", "/sys/class/hwmon/hwmon2")

# Which pwm channels to expose in the UI (1-6 on the nct6797)
CHANNELS = [1, 2, 3, 4, 5, 6]


def read_int(path, default=None):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return default


def write_int(path, value):
    with open(path, "w") as f:
        f.write(str(int(value)))


def resolve_hwmon_path():
    """Auto-detect the nct6797/nct6775 hwmon path if the configured one is missing."""
    if os.path.isdir(HWMON_PATH):
        name_file = os.path.join(HWMON_PATH, "name")
        if os.path.exists(name_file):
            return HWMON_PATH
    for hwmon_dir in glob.glob("/sys/class/hwmon/hwmon*"):
        name_file = os.path.join(hwmon_dir, "name")
        if os.path.exists(name_file):
            with open(name_file) as f:
                name = f.read().strip()
            if name.startswith("nct6"):
                return hwmon_dir
    return HWMON_PATH


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    base = resolve_hwmon_path()
    chip_name = read_int(os.path.join(base, "name"), None)
    try:
        with open(os.path.join(base, "name")) as f:
            chip_name = f.read().strip()
    except FileNotFoundError:
        chip_name = None

    channels = []
    for i in CHANNELS:
        fan_rpm = read_int(os.path.join(base, f"fan{i}_input"))
        pwm_enable = read_int(os.path.join(base, f"pwm{i}_enable"))
        pwm_value = read_int(os.path.join(base, f"pwm{i}_value")) or read_int(
            os.path.join(base, f"pwm{i}")
        )
        pwm_mode = read_int(os.path.join(base, f"pwm{i}_mode"))
        channels.append(
            {
                "channel": i,
                "fan_rpm": fan_rpm,
                "pwm_enable": pwm_enable,
                "pwm_value": pwm_value,
                "pwm_mode": pwm_mode,
            }
        )

    temps = {}
    for label, fname in [
        ("CPUTIN", "temp2_input"),
        ("SYSTIN", "temp1_input"),
    ]:
        val = read_int(os.path.join(base, fname))
        if val is not None:
            temps[label] = round(val / 1000, 1)

    return jsonify({"hwmon_path": base, "chip": chip_name, "channels": channels, "temps": temps})


@app.route("/api/pwm/<int:channel>", methods=["POST"])
def set_pwm(channel):
    if channel not in CHANNELS:
        return jsonify({"error": "invalid channel"}), 400

    base = resolve_hwmon_path()
    data = request.get_json(force=True)

    try:
        if "enable" in data:
            # 1 = manual control, 2 = automatic (BIOS/EC thermal curve)
            write_int(os.path.join(base, f"pwm{channel}_enable"), data["enable"])

        if "value" in data:
            value = max(0, min(255, int(data["value"])))
            write_int(os.path.join(base, f"pwm{channel}"), value)
    except (FileNotFoundError, PermissionError, OSError) as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
