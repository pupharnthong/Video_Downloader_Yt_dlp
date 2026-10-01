# app.py  —  pip install -U flask yt-dlp gunicorn   (+ ffmpeg)
# Render: ใส่ cookies.txt เป็น Secret File (จะไปอยู่ที่ /etc/secrets/cookies.txt)
#         หรือใส่ Environment Variable ชื่อ YT_COOKIES เป็นเนื้อหาไฟล์ cookies.txt ทั้งก้อน
import os, base64, uuid, threading, shutil, tempfile
from flask import Flask, render_template_string, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))

JOBS = {}
LOCK = threading.Lock()


# ---------- cookies resolver ----------
def resolve_cookie_file():
    """หา cookies.txt จาก: Render Secret File -> env var -> ไฟล์ข้าง app.py"""
    for p in ("/etc/secrets/cookies.txt",
              os.environ.get("COOKIE_FILE", ""),
              os.path.join(HERE, "cookies.txt")):
        if p and os.path.exists(p):
            return p
    raw = os.environ.get("YT_COOKIES")
    if raw:
        tmp = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
        if not os.path.exists(tmp):
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(raw.replace("\\n", "\n"))
        return tmp
    return None


COOKIE_FILE = resolve_cookie_file()
ON_SERVER = bool(os.environ.get("RENDER") or os.environ.get("PORT"))


def bg_src():
    p = os.path.join(HERE, "bg.mp4")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
    return "https://cdn.coverr.co/videos/coverr-a-mountain-range-at-sunset-3633/1080p.mp4"


def base_opts(browser=None):
    """บนเซิร์ฟเวอร์บังคับใช้ cookies.txt เสมอ (ไม่มีเบราว์เซอร์ให้ดึง)"""
    o = {
        'quiet': True, 'no_warnings': True, 'noprogress': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web_safari', 'web']}},
        'http_headers': {'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'},
        'retries': 5, 'extractor_retries': 3, 'socket_timeout': 30,
    }
    ck = resolve_cookie_file()
    if ck:
        o['cookiefile'] = ck
    elif not ON_SERVER and browser and browser not in ("none", "cookies.txt"):
        o['cookiesfrombrowser'] = (browser, None, None, None)
    return o


def friendly(e):
    m = str(e)
    if "not a bot" in m or "Sign in to confirm" in m:
        if not resolve_cookie_file():
            return ("ไม่พบ cookies.txt — อัปโหลดเป็น Secret File ชื่อ cookies.txt บน Render "
                    "หรือตั้ง env YT_COOKIES เป็นเนื้อหาไฟล์")
        return ("cookies หมดอายุหรือถูก YouTube ปฏิเสธ — export ใหม่จากหน้าต่าง Incognito "
                "แล้วปิดหน้าต่างทันทีก่อนอัปโหลด")
    if "ffmpeg" in m.lower():
        return "เซิร์ฟเวอร์ยังไม่มี FFmpeg — เพิ่มไฟล์ apt.toml หรือใช้ Docker ที่ลง ffmpeg"
    if "Private video" in m or "unavailable" in m:
        return "วิดีโอนี้เป็นส่วนตัวหรือถูกลบ"
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
                j['percent'] = round(d.get('downloaded_bytes', 0) / total * 100, 1) if total else 0
                sp = d.get('speed') or 0
                j['speed'] = f"{sp/1048576:.1f} MB/s" if sp else ""
                eta = d.get('eta')
                j['eta'] = f"{eta//60}:{eta%60:02d}" if eta else ""
                j['status'] = 'downloading'
            elif d['status'] == 'finished':
                j['status'] = 'merging'; j['percent'] = 100

    opts = {**base_opts(browser), 'format': FORMATS.get(q, 'bv*+ba/b'),
            'outtmpl': os.path.join(tmp, "%(title).100s.%(ext)s"),
            'merge_output_format': 'mp4', 'progress_hooks': [hook]}
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
.auth{margin-top:calc(var(--u)*.9);font-size:calc(var(--u)*.76);color:#333;display:flex;
 align-items:center;gap:.6em}
.dot{width:.65em;height:.65em;border-radius:50%;display:inline-block}
.ok{background:#2d7a4f}.bad{background:#c0392b}
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
    <span class="dot {{ 'ok' if cookies else 'bad' }}"></span>
    <span>{{ 'Cookies loaded' if cookies else 'No cookies.txt — YouTube may block this server' }}</span>
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
  const r=await post('/api/info',{url:$('url').value.trim()});
  s(r.ok?r.text:'Error: '+r.error);
}
async function dl(){
  const b=$('dlbtn'); b.disabled=true; $('prog').style.display='block'; $('fill').style.width='0%';
  s('Starting...');
  const r=await post('/api/start',{url:$('url').value.trim(), q:$('q').value});
  if(!r.ok){s('Error: '+r.error); b.disabled=false; return}
  poll(r.job,b);
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
    return render_template_string(PAGE, bg=bg_src(), cookies=bool(resolve_cookie_file()))


@app.post("/api/info")
def api_info():
    d = request.get_json(force=True)
    try:
        with yt_dlp.YoutubeDL(base_opts()) as y:
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
    threading.Thread(target=run_job, args=(job, d["url"], d.get("q", "Best"), None),
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
