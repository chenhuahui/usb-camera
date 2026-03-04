package main

import (
	"encoding/base64"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"sync"
	"time"
)

var (
	videoDevice = "/dev/video0"
	photoPath   = "/tmp/camera_photo.jpg"
	port        = "8766"
	mu          sync.Mutex
)

func main() {
	// 检查摄像头
	if _, err := os.Stat(videoDevice); os.IsNotExist(err) {
		log.Printf("警告: 摄像头设备 %s 不存在", videoDevice)
	}

	// HTTP 路由
	http.HandleFunc("/photo", takePhotoHandler)
	http.HandleFunc("/stream", streamHandler)
	http.HandleFunc("/status", statusHandler)

	// 网页端点
	http.HandleFunc("/", indexHandler)

	addr := ":" + port
	log.Printf("摄像头服务启动: http://localhost%s", addr)
	log.Printf("拍照接口: POST /photo")
	log.Printf("视频流: http://localhost%s/stream", addr)
	log.Fatal(http.ListenAndServe(addr, nil))
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(`<!DOCTYPE html>
<html>
<head>
    <title>USB Camera</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; text-align: center; padding: 20px; }
        img { max-width: 100%; border: 2px solid #333; }
        .btn { padding: 10px 20px; margin: 10px; font-size: 16px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>USB 摄像头</h1>
    <img id="video" src="/stream" style="max-width: 640px;">
    <br><br>
    <button class="btn" onclick="location.reload()">刷新</button>
    <button class="btn" onclick="fetch('/photo', {method: 'POST'})">拍照</button>
</body>
</html>`))
}

func takePhotoHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "仅支持 POST", http.StatusMethodNotAllowed)
		return
	}

	mu.Lock()
	defer mu.Unlock()

	// 使用 ffmpeg 拍照
	cmd := exec.Command("ffmpeg", "-y", "-f", "v4l2", "-i", videoDevice, 
		"-vframes", "1", "-q:v", "2", photoPath)
	
	if err := cmd.Run(); err != nil {
		log.Printf("拍照失败: %v", err)
		http.Error(w, fmt.Sprintf("拍照失败: %v", err), http.StatusInternalServerError)
		return
	}

	// 读取图片并转为 base64
	data, err := os.ReadFile(photoPath)
	if err != nil {
		http.Error(w, fmt.Sprintf("读取图片失败: %v", err), http.StatusInternalServerError)
		return
	}

	base64Img := base64.StdEncoding.EncodeToString(data)
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(fmt.Sprintf(`{"success": true, "image": "data:image/jpeg;base64,%s"}`, base64Img)))
}

func streamHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "multipart/x-mixed-replace; boundary=frame")
	
	cmd := exec.Command("ffmpeg", "-f", "v4l2", "-i", videoDevice,
		"-vf", "scale=640:-1", "-r", "10", "-q:v", "15", "-f", "mjpeg", "-")
	
	cmd.Stdout = w
	cmd.Stderr = os.Stderr
	
	if err := cmd.Run(); err != nil {
		log.Printf("视频流错误: %v", err)
	}
}

func statusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	_, err := os.Stat(videoDevice)
	deviceExist := err == nil
	
	w.Write([]byte(fmt.Sprintf(`{
		"device": "%s",
		"exists": %v,
		"time": "%s"
	}`, videoDevice, deviceExist, time.Now().Format(time.RFC3339))))
}
