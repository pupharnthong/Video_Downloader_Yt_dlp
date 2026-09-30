# app.py  —  pip install -U flask yt-dlp   (+ ffmpeg ใน PATH)
# รัน: python app.py  ->  http://127.0.0.1:5000
# วาง bg.mp4 ข้างไฟล์นี้ (ถ้าไม่มีจะใช้วิดีโอจากเน็ต)
# ถ้าเจอ "Sign in to confirm you're not a bot": วาง cookies.txt ข้างไฟล์นี้ แล้วเลือก cookies.txt ใน UI
import os, base64, uuid, threading, shutil, tempfile
from flask import Flask, render_template_string, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(HERE, "cookies.txt")

JOBS = {}          # job_id -> {status, percent, speed, eta, title, file, error}
LOCK = threading.Lock()


def bg_src():
    p = os.path.join(HERE, "bg.mp4")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
    return "https://cdn.coverr.co/videos/coverr-a-mountain-range-at-sunset-3633/1080p.mp4"


def base_opts(browser):
    o = {'quiet': True, 'no_warnings': True, 'noprogress': True}
    if browser == "cookies.txt":
        if not os.path.exists(COOKIE_FILE):
            raise FileNotFoundError("ไม่พบ cookies.txt ข้างไฟล์ app.py")
        o['cookiefile'] = COOKIE_FILE
    elif browser and browser != "none":
        o['cookiesfrombrowser'] = (browser, None, None, None)
    return o


def friendly(e):
    m = str(e)
    if "not a bot" in m or "Sign in to confirm" in m:
        return "YouTube ขอยืนยันตัวตน — ใช้ cookies.txt หรือเลือกเบราว์เซอร์ที่ล็อกอินไว้ (ต้องรันบนเครื่องตัวเอง)"
    if "cookies" in m.lower() and "could not" in m.lower():
        return "หา cookie ของเบราว์เซอร์ไม่เจอ — ลองใช้ cookies.txt แทน"
    if "being used by another process" in m or "Permission denied" in m:
        return "ไฟล์ cookie ถูกล็อก — ปิดเบราว์เซอร์ให้สนิทแล้วลองใหม่"
    if "ffmpeg" in m.lower():
        return "ต้องติดตั้ง FFmpeg ก่อน ถึงจะรวมภาพ+เสียงได้"
    return m[:300]


FORMATS = {'Best': 'bv*+ba/b', '1080p': 'bv*[height<=1080]+ba/b',
           '720p': 'bv*[height<=720]+ba/b', '480p': 'bv*[height<=480]+ba/b',
           'Audio only': 'ba'}


def run_job(job_id, url, q, browser):
    tmp = tempfile.mkdtemp(prefix="dl_")

    def hook(d):
        with LOCK:
            j = JOBS[job_id]
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                done = d.get('downloaded_bytes', 0)
                j['percent'] = round(done / total * 100, 1) if total else 0
                sp = d.get('speed') or 0
                j['speed'] = f"{sp/1048576:.1f} MB/s" if sp else ""
                eta = d.get('eta')
                j['eta'] = f"{eta//60}:{eta%60:02d}" if eta else ""
                j['status'] = 'downloading'
            elif d['status'] == 'finished':
                j['status'] = 'merging'
                j['percent'] = 100

    opts = {**base_opts(browser), 'format': FORMATS.get(q, 'bv*+ba/b'),
            'outtmpl': os.path.join(tmp, "%(title).100s.%(ext)s"),
            'merge_output_format': 'mp4', 'retries': 5,
            'progress_hooks': [hook], 'noprogress': True}
    if q == "Audio only":
        opts.pop('merge_output_format', None)
        opts['postprocessors'] = [{'key': 'FFmpegExtractAudio',
                                   'preferredcodec': 'mp3', 'preferredquality': '192'}]
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=True)
        files = [os.path.join(tmp, f) for f in os.listdir(tmp)]
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            raise RuntimeError("ไม่พบไฟล์ผลลัพธ์")
        path = max(files, key=os.path.getsize)
        with LOCK:
            JOBS[job_id].update(status='done', percent=100, file=path,
                                dir=tmp, title=info.get('title', 'video'))
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        with LOCK:
            JOBS[job_id].update(status='error', error=friendly(e))


PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Video Downloader</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Inter,sans-serif}
html,body{height:100%;overflow:hidden;color:#1a1a1a}
:root{--u:clamp(11px,1.25vw,17px)}
#bg{position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:-2}
.veil{position:fixed;inset:0;z-index:-1;
 background:linear-gradient(180deg,rgba(245,243,240,.85) 0%,rgba(245,243,240,.45) 30%,rgba(0,0,0,0) 60%)}
.hero{position:relative;height:100%;display:flex;flex-direction:column;align-items:center;
 padding:13vh 4vw 4vh;text-align:center;gap:calc(var(--u)*.7)}
.badge{background:rgba(255,255,255,.75);backdrop-filter:blur(8px);border-radius:999px;
 padding:.5em 1.2em;font-size:calc(var(--u)*.78);box-shadow:0 2px 10px rgba(0,0,0,.08)}
h1{font-size:clamp(30px,5.2vw,68px);letter-spacing:-.04em;line-height:1.05;margin-top:.2em}
p.sub{font-size:calc(var(--u)*1.02);color:#3c3c3c;line-height:1.5}
.bar{margin-top:calc(var(--u)*1.4);display:flex;flex-wrap:wrap;justify-content:center;
 gap:calc(var(--u)*.6);width:min(92vw,720px)}
input{flex:1 1 240px;min-width:180px;border:0;border-radius:999px;padding:1em 1.5em;
 font-size:calc(var(--u)*.85);outline:none;background:rgba(255,255,255,.92);box-shadow:0 4px 18px rgba(0,0,0,.12)}
select{border:0;border-radius:999px;padding:0 1em;background:rgba(255,255,255,.92);
 font-size:calc(var(--u)*.8);outline:none;box-shadow:0 4px 18px rgba(0,0,0,.10)}
button{border:0;border-radius:999px;padding:1em 1.6em;font-size:calc(var(--u)*.85);
 font-weight:600;cursor:pointer;white-space:nowrap}
button.ghost{background:#fff;box-shadow:0 4px 18px rgba(0,0,0,.14)}
.glow{position:relative;color:#fff;background:#2b1a5e;isolation:isolate;padding:1em 2em;transition:transform .18s ease}
.glow:before{content:'';position:absolute;inset:0;border-radius:inherit;z-index:-1;
 background:linear-gradient(90deg,#7c3aed,#a855f7,#c084fc,#8b5cf6,#7c3aed);
 background-size:300% 100%;animation:slide 4s linear infinite}
.glow:after{content:'';position:absolute;inset:-6px;border-radius:inherit;z-index:-2;filter:blur(18px);
 opacity:.55;background:linear-gradient(90deg,#7c3aed,#c084fc,#8b5cf6);background-size:300% 100%;
 animation:slide 4s linear infinite;transition:opacity .25s ease}
@keyframes slide{to{background-position:300% 0}}
.glow:hover{transform:translateY(-2px) scale(1.04)}
.glow:hover:after{opacity:1;inset:-10px}
.glow:active{transform:translateY(1px) scale(.98)}
.glow[disabled]{opacity:.6;cursor:wait;transform:none}
.auth{margin-top:calc(var(--u)*.9);display:flex;align-items:center;justify-content:center;
 gap:calc(var(--u)*.5);font-size:calc(var(--u)*.78);color:#333}
.auth select{padding:.55em 1em}
.prog{margin-top:calc(var(--u)*1);width:min(92vw,720px);height:10px;border-radius:999px;
 background:rgba(255,255,255,.65);overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.10);display:none}
.prog i{display:block;height:100%;width:0;border-radius:999px;transition:width .25s ease;
 background:linear-gradient(90deg,#7c3aed,#c084fc,#8b5cf6);background-size:300% 100%;animation:slide 2s linear infinite}
#status{margin-top:calc(var(--u)*.7);font-size:calc(var(--u)*.8);color:#333;min-height:1.4em;
 max-width:min(92vw,720px);word-break:break-word}
@media (max-height:560px){.hero{padding-top:5vh}}
</style></head><body>
<video id="bg" autoplay muted loop playsinline src="{{ bg }}"></video>
<div class="veil"></div>

<div class="hero">
  <div class="badge">Video + Audio merged</div>
  <h1>Download with ease.</h1>
  <p class="sub">Paste a link, pick a resolution, and get a clean MP4.<br>So you can take a breath.</p>

  <div class="bar">
    <input id="url" placeholder="https://youtu.be/...">
    <select id="q"><option>Best</option><option>1080p</option><option>720p</option>
      <option>480p</option><option>Audio only</option></select>
    <button class="ghost" onclick="fetchInfo()">Fetch</button>
    <button class="glow" id="dlbtn" onclick="dl()">Download</button>
  </div>

  <div class="auth">
    <span>Cookies from</span>
    <select id="br">
      <option value="none">None</option>
      <option value="cookies.txt" selected>cookies.txt</option>
      <option value="chrome">Chrome</option><option value="edge">Edge</option>
      <option value="firefox">Firefox</option><option value="brave">Brave</option>
    </select>
  </div>

  <div class="prog" id="prog"><i id="fill"></i></div>
  <div id="status"></div>
</div>

<script>
const $=i=>document.getElementById(i), s=t=>$('status').innerText=t;
async function post(u,b){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(b)})).json()}

async function fetchInfo(){
  s('Fetching...');
  const r = await post('/api/info',{url:$('url').value.trim(), browser:$('br').value});
  s(r.ok ? r.text : 'Error: '+r.error);
}

async function dl(){
  const b=$('dlbtn'); b.disabled=true; $('prog').style.display='block'; $('fill').style.width='0%';
  s('Starting...');
  const r = await post('/api/start',{url:$('url').value.trim(), q:$('q').value, browser:$('br').value});
  if(!r.ok){s('Error: '+r.error); b.disabled=false; return}
  poll(r.job, b);
}

function poll(job,b){
  const t=setInterval(async()=>{
    const p=await (await fetch('/api/progress/'+job)).json();
    $('fill').style.width=(p.percent||0)+'%';
    if(p.status==='downloading') s(`Downloading ${p.percent}%  ${p.speed}  ${p.eta?'ETA '+p.eta:''}`);
    else if(p.status==='merging') s('Merging video + audio...');
    else if(p.status==='done'){clearInterval(t); s('Ready — saving file...'); b.disabled=false;
      window.location='/api/file/'+job;}
    else if(p.status==='error'){clearInterval(t); s('Error: '+p.error); b.disabled=false;
      $('prog').style.display='none';}
  },600);
}
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, bg=bg_src())


@app.post("/api/info")
def api_info():
    d = request.get_json(force=True)
    try:
        with yt_dlp.YoutubeDL(base_opts(d.get("browser"))) as y:
            i = y.extract_info(d["url"], download=False)
        dur = i.get('duration') or 0
        return jsonify(ok=True, text=f"{i.get('title')} · {dur//60}:{dur%60:02d} · {i.get('uploader','')}")
    except Exception as e:
        return jsonify(ok=False, error=friendly(e))


@app.post("/api/start")
def api_start():
    d = request.get_json(force=True)
    if not d.get("url"):
        return jsonify(ok=False, error="กรุณาวางลิงก์ก่อน")
    job = uuid.uuid4().hex
    with LOCK:
        JOBS[job] = {'status': 'queued', 'percent': 0, 'speed': '', 'eta': ''}
    threading.Thread(target=run_job,
                     args=(job, d["url"], d.get("q", "Best"), d.get("browser")),
                     daemon=True).start()
    return jsonify(ok=True, job=job)


@app.get("/api/progress/<job>")
def api_progress(job):
    with LOCK:
        j = JOBS.get(job)
    return jsonify(j or {'status': 'error', 'error': 'job not found'})


@app.get("/api/file/<job>")
def api_file(job):
    with LOCK:
        j = JOBS.get(job)
    if not j or j.get('status') != 'done':
        return "not ready", 404
    path, folder = j['file'], j['dir']

    @after_this_request
    def cleanup(resp):
        def rm():
            shutil.rmtree(folder, ignore_errors=True)
            with LOCK:
                JOBS.pop(job, None)
        threading.Timer(15, rm).start()
        return resp

    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
