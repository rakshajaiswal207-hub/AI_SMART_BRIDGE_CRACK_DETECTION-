# AI-Based Smart Bridge Crack Detection System

Laboratory inspection-support prototype. An ESP32-CAM sends a bridge-surface JPEG to a Flask application. OpenCV highlights long, thin crack-like regions, MySQL or SQLite stores the record, and the dashboard shows the original image, the processed mask, the highlighted result, the status, and the date and time.

This is a screening aid. It does not judge structural safety.

## Run the dashboard

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/

The page can process three built-in demonstration images (artificial crack, crack-free surface, dim light) or a photograph you upload. Those built-in images are generated stand-ins so the software can be shown before the camera is connected. For the miniature bridge, upload a photo of the model or send one from the ESP32-CAM.

If MySQL is not running, records are stored in `data/inspections.db`. The dashboard footer names the database in use.

## Use MySQL

Start MySQL, then either import `schema.sql` or let the application create the `bridge_crack.inspections` table. Set the connection if it is not `root` with an empty password on `127.0.0.1`:

```powershell
$env:DB_ENGINE = "mysql"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = "your-password"
.\.venv\Scripts\python.exe app.py
```

`DB_ENGINE=mysql` stops the application if MySQL cannot be reached. The default `auto` falls back to SQLite.

## ESP32-CAM

1. Install the ESP32 board package in the Arduino IDE and select the AI-Thinker ESP32-CAM.
2. Edit `firmware/esp32_cam/esp32_cam.ino`: Wi-Fi name, password, and `SERVER_URL`.
3. `SERVER_URL` must be the laptop's LAN address, for example `http://192.168.1.20:5000/upload`. Find it with `ipconfig`.
4. Flash with GPIO0 connected to GND (adapter GND to GND, 5 V to 5 V, TX to U0R, RX to U0T). Remove the GPIO0 link, then power the board from a regulated 5 V supply.
5. Allow Python through the Windows firewall on private networks so the camera can reach port 5000.

The sketch captures a JPEG about every 15 seconds and POSTs it. The dashboard refreshes the history every few seconds.

## Detection settings

The image is converted to grayscale and contrast-enhanced with CLAHE (section 9.3). A multi-scale Hessian ridge filter then scores how much each pixel looks like the center of a dark line, which separates cracks from round stones and stains. Strong ridge pixels seed a crack and it grows into weaker connected ridge pixels (hysteresis), so a crack that fades as it narrows is still followed. Connected cracks are kept when they are long, thin and darker than the surface around them. Edges of painted lines are ignored, and grass is ignored in colorful scenes.

The main knobs are at the top of `crack_detection.py`. Raise `SEED_LEVEL` or `GROW_LEVEL` if gravel texture is traced; lower `GROW_LEVEL` if a faint crack stops short. `LONG_CRACK` is the shortest crack kept, as a fraction of the image diagonal.

## What is stored

| Field | Meaning |
| --- | --- |
| id | Inspection id |
| captured_date / captured_time | When the image was received |
| original_path / result_path | Original JPEG and highlighted image |
| status | `Crack-like region detected` or `No crack detected` |
| region_count | How many separate connected cracks were found |

The processed mask is saved beside the record and shown on the dashboard. It is not a separate database column.

## Fill in the test tables

After you run the miniature-bridge photographs, write the observed pass or fail in Table 10.1 and the counts and times in Table 10.2. The result panel shows processing time for an image just after it is processed. The console prints the same line. Do not copy results from the generated samples into the report as if they were the physical model.