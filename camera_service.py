#!/usr/bin/env python3
"""
USB 摄像头服务 - 支持断线重连
"""

import os
import subprocess
import time
import json
import base64
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

VIDEO_DEVICE = "/dev/video0"
PHOTO_PATH = "/tmp/camera_photo.jpg"
STREAM_PATH = "/tmp/camera_stream.jpg"
PORT = 8766

# 全局变量
stream_proc = None
last_device_check = 0
device_available = True

def check_device():
    """检查设备是否可用，必要时尝试切换设备"""
    global VIDEO_DEVICE, device_available
    
    if os.path.exists(VIDEO_DEVICE):
        device_available = True
        return True
    
    # 尝试切换设备
    for dev in ["/dev/video0", "/dev/video1", "/dev/video2"]:
        if os.path.exists(dev):
            VIDEO_DEVICE = dev
            device_available = True
            print(f"切换到设备: {dev}")
            return True
    
    device_available = False
    return False

def start_stream():
    """启动视频流进程，带重连"""
    global stream_proc
    
    # 检查设备
    if not check_device():
        print("摄像头设备不可用")
        return False
    
    # 如果进程存在且在工作，就不管
    if stream_proc and stream_proc.poll() is None:
        return True
    
    # 启动新进程
    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'v4l2', '-i', VIDEO_DEVICE,
            '-vf', 'fps=5,scale=640:-1,transpose=2,transpose=2',
            '-q:v', '10', '-update', '1', STREAM_PATH
        ]
        stream_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"视频流进程启动 (PID: {stream_proc.pid})")
        return True
    except Exception as e:
        print(f"启动视频流失败: {e}")
        return False

def restart_stream_if_needed():
    """检查并重启视频流"""
    global stream_proc, last_device_check
    
    now = time.time()
    # 每3秒检查一次
    if now - last_device_check < 3:
        return
    last_device_check = now
    
    # 检查设备
    if not check_device():
        print("设备未找到，等待...")
        stream_proc = None
        return
    
    # 检查进程状态
    if stream_proc is None:
        start_stream()
        return
    
    # 进程可能挂了
    if stream_proc.poll() is not None:
        print("视频流进程已退出，尝试重启...")
        start_stream()
        return
    
    # 检查输出文件是否更新
    try:
        mtime = os.path.getmtime(STREAM_PATH)
        if now - mtime > 5:  # 5秒没更新
            print("视频流卡住，尝试重启...")
            stream_proc.terminate()
            stream_proc = None
            time.sleep(0.5)
            start_stream()
    except:
        pass

def take_photo():
    """拍照"""
    if not check_device():
        return {"success": False, "error": "摄像头不可用"}
    
    try:
        cmd = ['ffmpeg', '-y', '-f', 'v4l2', '-i', VIDEO_DEVICE, 
               '-vframes', '1', '-q:v', '2', PHOTO_PATH]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        
        if result.returncode != 0:
            return {"success": False, "error": "拍照失败"}
        
        return {"success": True, "path": PHOTO_PATH}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

class CameraHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        
        # 每次请求都检查视频流
        restart_stream_if_needed()
        
        if path == "/" or path == "/index":
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = '''<!DOCTYPE html>
<html>
<head>
    <title>USB Camera</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; text-align: center; padding: 20px; background: #f0f0f0; }
        h1 { color: #333; }
        img { max-width: 100%; border: 3px solid #333; border-radius: 8px; }
        .btn { padding: 12px 24px; margin: 10px; font-size: 16px; cursor: pointer; 
               background: #007bff; color: white; border: none; border-radius: 5px; }
        .btn:hover { background: #0056b3; }
        .status { padding: 10px; background: #d4edda; border-radius: 5px; margin: 10px; }
        .error { background: #f8d7da; }
    </style>
</head>
<body>
    <h1>📷 USB 摄像头</h1>
    <div id="status" class="status">设备: ''' + VIDEO_DEVICE + ''' - 连接中...</div>
    <img id="video" src="/stream.jpg?t=''' + str(int(time.time())) + '''" style="max-width:640px;">
    <br><br>
    <button class="btn" onclick="document.getElementById('video').src='/stream.jpg?t='+new Date().getTime()">🔄 刷新视频</button>
    <button class="btn" onclick="fetch('/photo', {method: 'POST'}).then(r=>r.json()).then(d=>{if(d.success){document.getElementById('video').src=d.image+'&t='+new Date().getTime();alert('已拍照!')}else{alert(d.error)}})">📸 拍照</button>
    <script>
    setInterval(()=>{
        document.getElementById('video').src='/stream.jpg?t='+new Date().getTime();
    }, 1000);
    
    // 定期检查状态
    setInterval(()=>{
        fetch('/status').then(r=>r.json()).then(d=>{
            document.getElementById('status').innerHTML = '设备: ' + d.device + (d.exists ? ' - 已连接 ✅' : ' - 未连接 ❌');
            if(!d.exists) document.getElementById('status').className = 'status error';
        });
    }, 3000);
    </script>
</body>
</html>'''
            self.wfile.write(html.encode('utf-8'))
            
        elif path == "/stream.jpg":
            if not device_available:
                self.send_error(503)
                return
            try:
                with open(STREAM_PATH, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_error(404)
                
        elif path == "/status":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            check_device()
            resp = {
                "device": VIDEO_DEVICE, 
                "exists": device_available, 
                "time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.wfile.write(json.dumps(resp).encode())
            
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == "/photo":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            result = take_photo()
            if result["success"]:
                with open(PHOTO_PATH, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                result = {"success": True, "image": f"data:image/jpeg;base64,{img_data}"}
            
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass

def signal_handler(sig, frame):
    print("\n收到退出信号，正在关闭...")
    if stream_proc:
        stream_proc.terminate()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    check_device()
    start_stream()
    
    print(f"🚀 摄像头服务: http://localhost:{PORT}")
    print(f"📷 当前设备: {VIDEO_DEVICE}")
    
    server = HTTPServer(('0.0.0.0', PORT), CameraHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == "__main__":
    main()
