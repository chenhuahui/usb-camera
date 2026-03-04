# USB Camera Service

通过飞书控制 USB 摄像头拍照，通过网页查看实时视频。

## 功能

- 📸 **拍照**: 通过飞书消息触发拍照
- 📹 **视频流**: 网页实时查看摄像头画面（每0.5秒刷新）
- 🔄 **自动重连**: 摄像头断连后自动检测并重连
- 🔄 **旋转**: 支持画面旋转

## 使用方式

```bash
# 启动服务
python3 camera_service.py

# 访问地址
http://localhost:8766
```

## API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 网页预览 |
| `/stream.jpg` | GET | 视频流 |
| `/photo` | POST | 拍照 |
| `/status` | GET | 状态 |

## 配置

修改 `camera_service.py` 中的配置：
- `VIDEO_DEVICE`: 摄像头设备路径
- `PORT`: 服务端口
