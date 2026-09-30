import os, base64, uuid
from flask import Flask, render_template_string, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(HERE, "cookies.txt")

def bg_src():
    p = os.path.join(HERE, "bg.mp4")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
    return "https://cdn.coverr.co/videos/coverr-a-mountain-range-at-sunset-3633/1080p.mp4"

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8">
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
 justify-content:flex-start;padding:14vh 4vw 4vh;text-align:center;gap:calc(var(--u)*.7)}
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

.glow{position:relative;color:#fff;background:#2b1a5e;isolation:isolate;
 padding:1em 2em;transition:transform .18s ease}
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
#status{margin-top:calc(var(--u)*.8);font-size:calc(var(--u)*.8);color:#333;min-height:1.4em;
 max-width:min(92vw,720px);word-break:break-word}
@media (max-height:560px){.hero{padding-top:5vh}}
</style></head><body>
<video id="bg" autoplay muted loop playsinline src="__BG__"></video>
<div class="veil"></div>

<div class="hero">
  <div class="badge">Video + Audio Web Service</div>
  <h1>Download with ease.</h1>
  <p class="sub">Paste a link, pick a resolution, and get a clean MP4.<br>So you can take a breath.</p>

  <div class="bar">
    <input id="url" placeholder="https://youtu.be/...">
    <select id="q">
      <option>Best</option><option>1080p</option><option>720p</option>
      <option>480p</option><option>Audio only</option>
    </select>
    <button class="ghost" onclick="fetchInfo()">Fetch</button>
    <button class="glow" id="dlbtn" onclick="dl()">Download</button>
  </div>

  <div class="auth">
    <span>Cookies</span>
    <select id="br">
      <option value="none">None</option>
      <option value="cookies.txt" selected>cookies.txt</option>
    </select>
  </div>

  <div id="status"></div>
</div>

<script>
const s = t => document.getElementById('status').innerText = t;

async function fetchInfo(){
  const url = document.getElementById('url').value.trim();
  const br = document.getElementById('br').value;
  if (!url) return s('กรุณาวางลิงก์ก่อน');
  s('Fetching...');
  try {
    const res = await fetch('/api/info', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, browser: br})
    });
    const data = await res.json();
    s(data.result);
  } catch (e) { s('Error fetching info'); }
}

function dl(){
  const url = document.getElementById('url').value.trim();
  const q = document.getElementById('q').value;
  const br = document.getElementById('br').value;
  if (!url) return s('กรุณาวางลิงก์ก่อน');
  
  s('Processing download on server... please wait...');
  window.location.href = `/api/download?url=${encodeURIComponent(url)}&q=${encodeURIComponent(q)}&browser=${encodeURIComponent(br)}`;
}
</script></body></html>
""".replace("__BG__", bg_src())


def base_opts(browser):
    o = {'quiet': True, 'no_warnings': True, 'noprogress': True}
    if browser == "cookies.txt":
        if os.path.exists(COOKIE_FILE):
            o['cookiefile'] = COOKIE_FILE
    return o


def friendly(e):
    m = str(e)
    if "not a bot" in m or "Sign in to confirm" in m:
        return "YouTube ขอยืนยันตัวตน — แนะนำให้แนบไฟล์ cookies.txt ในโปรเจกต์"
    if "ffmpeg" in m.lower():
        return "ระบบเซิร์ฟเวอร์ยังไม่มี FFmpeg สำหรับรวมไฟล์"
    return f"Error: {m[:300]}"


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/api/info', methods=['POST'])
def info():
    data = request.json or {}
    url = data.get('url', '')
    browser = data.get('browser', 'cookies.txt')
    if not url:
        return jsonify({'result': 'กรุณาวางลิงก์ก่อน'})
    try:
        with yt_dlp.YoutubeDL(base_opts(browser)) as y:
            d = y.extract_info(url, download=False)
        dur = d.get('duration') or 0
        res = f"{d.get('title','(no title)')} · {dur//60}:{dur%60:02d} · {d.get('uploader','')}"
        return jsonify({'result': res})
    except Exception as e:
        return jsonify({'result': friendly(e)})


@app.route('/api/download')
def download():
    url = request.args.get('url', '')
    q = request.args.get('q', 'Best')
    browser = request.args.get('browser', 'cookies.txt')

    if not url:
        return "กรุณาวางลิงก์ก่อน", 400

    tmp_dir = "/tmp"
    unique_id = str(uuid.uuid4())
    out_tmpl = os.path.join(tmp_dir, f"{unique_id}_%(title)s.%(ext)s")

    fmt = {
        'Best': 'b/bv*+ba',
        '1080p': 'bv*[height<=1080]+ba/b',
        '720p': 'bv*[height<=720]+ba/b',
        '480p': 'bv*[height<=480]+ba/b',
        'Audio only': 'ba'
    }.get(q, 'b')

    opts = {
        **base_opts(browser),
        'format': fmt,
        'outtmpl': out_tmpl,
        'retries': 3,
        'overwrites': True
    }

    if q == "Audio only":
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }]

    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info_dict = y.extract_info(url, download=True)
            filepath = y.prepare_filename(info_dict)

        if q == "Audio only":
            filepath = os.path.splitext(filepath)[0] + ".mp3"

        filename = os.path.basename(filepath).replace(f"{unique_id}_", "")

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            return response

        return send_file(filepath, as_attachment=True, download_name=filename)

    except Exception as e:
        return f"Download failed: {friendly(e)}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
