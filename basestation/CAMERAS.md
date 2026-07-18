# Camera Pipeline: Diagnosis and Redesign Notes

Status: **not started** — investigation notes and agreed direction, written 2026-07-18.
Context: robot code and basestation now run on the same computer (currently a
Jetson Orin NX 16GB, possible future switch to Orin Nano 8GB).

Repository pointers and the full topic contract are in
[REDESIGN_PLAN.md](REDESIGN_PLAN.md) ("Context needed to work on this from any
machine"). Legacy code cited below (`views.py`, `VideoFeedCard.jsx`,
`camera_publisher_node.cpp`) lives in the legacy basestation repo
(`UOW-TronSoc/ARCh2026-BaseStation`) and the legacy robot workspace
(`kanga_cameras` package) respectively.

## How cameras work today (legacy basestation)

Three supposed paths, but only two are real:

1. **ROS path is a dead end.** `kanga_cameras` (`camera_publisher_node.cpp`)
   captures `/dev/video2`/`video4`, JPEG-encodes each frame on CPU, and
   publishes `CompressedImage` on `/camera/top` and `/camera/back` — but
   **nothing in the basestation subscribes to any image topic** (see comment in
   `backendapi/views.py` line ~229: "not ROS topics"). Only Foxglove/rviz can
   see these.
2. **USB + IP cams both go through Django.** A thread per camera
   (`DirectCameraSource`) holds an OpenCV `VideoCapture` (FFmpeg for RTSP, V4L2
   for USB) and keeps the latest decoded raw frame in memory.
3. **The frontend polls single JPEG frames.** `VideoFeedCard.jsx` does not use
   the MJPEG stream endpoint — each `<img>` load completion triggers the next
   HTTP request (`?single=1&t=...`). Every displayed frame costs one HTTP
   round-trip plus one Python JPEG encode.

### Why the IP cams lag ~0.5 s

Path: camera H.264 encode -> RTSP/TCP -> FFmpeg decode to raw BGR in Django ->
JPEG re-encode per request -> HTTP poll over Wi-Fi -> browser decode.
Aggressive low-latency FFmpeg flags and a buffer-drain loop are already in the
code and maxed out; the frame-polling transport alone adds 100-300 ms, so the
architecture has a hard latency floor. The camera's own web viewer decodes its
H.264 stream directly, hence the visible difference.

### Why cameras have been chronically unreliable

- **Device contention:** Django scans and opens *all* of `/dev/video*` while
  `kanga_cameras` opens video2/video4 from its config. V4L2 streaming is
  exclusive — boot order decides which process wins. The 25-retry loops and
  hotplug rescans in `views.py` are symptoms.
- **JPEG polling costs 5-10x the bandwidth of H.264** for the same quality
  (640x480@15 as JPEG poll is ~3-6 Mbit/s vs ~0.5 Mbit/s as H.264), saturating
  rover Wi-Fi exactly when range is worst.
- Frame rate collapses as RTT grows (each frame is a full round trip), so video
  degrades to a freeze at distance instead of degrading gracefully.

## Agreed redesign: MediaMTX + hardware H.264 + WebRTC

```
IP cams (10.0.0.5/6) --RTSP pull, H.264 passthrough, no transcode--> MediaMTX
USB cams --GStreamer: v4l2src -> <encoder> -> rtspclientsink------> MediaMTX
D435i / ZED 2i --ROS driver owns device (depth stays in ROS)
               --bridge node: color topic -> <encoder> ------------> MediaMTX
MediaMTX --WebRTC (WHEP), ~100-300 ms glass-to-glass--> browser <video> elements
```

- **One owner per `/dev/video*` device**, declared in a single camera config.
  Plain USB cams are owned by their GStreamer pipeline; depth cams by their ROS
  driver. No process ever competes for a device again.
- **IP cams are pure passthrough** — zero CPU on the Jetson, and this alone
  should fix the 0.5 s delay.
- **Frontend:** `VideoFeedCard` swaps the polling `<img>` for a `<video>` +
  small WHEP client; camera list comes from MediaMTX paths. MediaMTX only pulls
  and serves a stream while someone is watching, so unwatched cameras cost
  zero bandwidth.
- **Encoder element is a per-camera config value**: `nvv4l2h264enc` (NVENC) on
  Orin NX, `x264enc` (software, ultrafast/zerolatency) where no NVENC exists.
- **Retired at the end:** all Django camera code and the `kanga_cameras`
  publisher (unless robot code later needs raw frames, in which case the
  GStreamer pipeline tees into a ROS publisher).
- **Rollout is per-camera and low-risk:** point MediaMTX at one IP cam first
  (it is just an extra RTSP client), compare latency side by side, then migrate
  USB cams, then depth cams. Keep old MJPEG endpoints as fallback until every
  feed is verified.

### Expected gains

- Latency: ~0.5 s+ -> ~100-300 ms glass-to-glass.
- Bandwidth: ~5-10x more quality per bit; e.g. 720p30 H.264 at ~1-2 Mbit/s vs
  ~4-10 Mbit/s for a worse 640p15 JPEG poll. More cameras and/or better
  resolution/frame rate in the same Wi-Fi budget.
- Under congestion WebRTC drops bitrate (blurrier video) instead of freezing.

## Hardware constraint: encoder availability

Verified against NVIDIA datasheets (July 2026):

| | Orin NX 16GB | Orin NX 8GB | Orin Nano 8GB |
|---|---|---|---|
| Hardware encoder (NVENC) | Yes | Yes (identical to 16GB) | **None** |
| H.264 encode capacity | 1x4K60 / 5x1080p60 / 11x1080p30 | Same | Software only (~1080p30 per 1-2 CPU cores) |
| Simultaneous rover cam streams (720p15-ish) | More than we need | Same | ~2-3, eating CPU the robot wants |
| Hardware decode (NVDEC) | 1x8K30 / 9x1080p60 | Same | 1x4K60 / 5x1080p60 |
| CPU | 8x A78AE @ 2.0 GHz | 6x A78AE @ 2.0 GHz | 6x A78AE @ 1.5-1.7 GHz |
| GPU / AI | 100 TOPS, 2x DLA | 70 TOPS, 1x DLA | 40 TOPS (67 "Super"), no DLA |
| RAM / bandwidth | 16 GB @ 102 GB/s | 8 GB @ 102 GB/s | 8 GB @ 68-102 GB/s |
| Module price (approx.) | ~US$600 | ~US$400 | ~US$250 |

Key points:

- **Both NX variants share the same NVENC** — for video, NX 8GB == NX 16GB.
  The 16GB advantages (cores, TOPS, RAM) matter for ZED depth / SLAM /
  inference, not streaming.
- **Orin Nano has no NVENC at all** (NVIDIA's official guidance is software
  encode or buy an NX). On a Nano: IP cams unaffected (passthrough); USB cams
  need `x264enc` at ~0.5 core per 480-720p15 stream (2-3 streams realistic);
  hardware decode is retained but barely used in this design.
- If switching to a Nano, also evaluate ZED 2i CUDA depth load on the smaller
  GPU — a bigger platform question than video.
- Even software encode beats today's pipeline: the current path software-decodes
  RTSP *and* JPEG-encodes every frame in Python for 5-10x the bandwidth.

## Option: dedicated encoder box for USB cams (if on Orin Nano)

A small SBC on the rover's wired network that owns the USB cams and publishes
RTSP into MediaMTX. From MediaMTX's perspective it is indistinguishable from an
IP camera. Encoded H.264 is ~1-2 Mbit/s/stream, so the Ethernet hop is
negligible. Completely decoupled from the control path: if it dies you lose
video, not the robot.

Ranking:

1. **Real IP cameras / UVC cams with onboard H.264** — same offload, no second
   Linux system to image, power, and boot reliably. Prefer these when buying.
2. **Orange Pi 5 / 5 Plus (RK3588)** — has a real hardware encoder (rated 8K30);
   several 1080p30 streams at near-zero CPU for ~US$100. Caveat: encoder is
   exposed via Rockchip MPP (`mpph264enc` GStreamer / ffmpeg-rkmpp) and wants a
   vendor/Armbian kernel — verify software state hands-on before committing.
3. **Raspberry Pi 4** — has hardware H.264 encode (VideoCore VI via mainline
   `v4l2h264enc`), but capped at ~1080p30 *total* across all streams: one
   1080p30 or two 720p25-30 cams. Encode quality per bit is mediocre but fine
   for teleop. Good free prototype if one is in a drawer.
4. **Orin Nano software encode** — fine for 2-3 modest streams if the CPU
   budget allows.
5. **Raspberry Pi 5** — dropped the hardware encoder (HEVC decode only) and has
   a weaker CPU than the Nano; not worth buying for this.

## Phase 2 task list (from the main plan)

1. Install MediaMTX as a systemd service; configure RTSP pull for IP cams
   10.0.0.5/6 with WebRTC (WHEP) output; verify latency vs direct view.
2. Per-USB-camera GStreamer pipeline (`v4l2src -> <encoder> ->
   rtspclientsink`) into MediaMTX, encoder element configurable, driven by one
   camera-ownership config.
3. D435i/ZED2i via ROS drivers (depth stays in ROS); bridge color image topic
   -> encoder -> MediaMTX for the webpage.
4. Replace `VideoFeedCard` JPEG polling with a WHEP WebRTC `<video>` element;
   camera list from MediaMTX paths.
5. Retire Django camera code and the `kanga_cameras` publisher (or keep a topic
   tee only where robot code needs frames); delete the cameras-only Django
   service.
