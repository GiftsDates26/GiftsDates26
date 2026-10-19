// Camera + microphone access for video calls.
export async function requestCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    return { ok: false, code: "UNSUPPORTED", message: "Your browser does not support video calls. Please use the latest Chrome, Safari, Edge or Firefox." };
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }, audio: { echoCancellation: true, noiseSuppression: true } });
    return { ok: true, stream };
  } catch (e) {
    const name = e?.name || "";
    if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError")
      return { ok: false, code: "DENIED", message: "Camera and microphone access was blocked. Click the camera icon in your browser's address bar, choose \"Allow\", then press Try again." };
    if (name === "NotFoundError" || name === "DevicesNotFoundError" || name === "OverconstrainedError")
      return { ok: false, code: "NO_DEVICE", message: "No camera or microphone was found. Connect a camera and microphone, then press Try again." };
    if (name === "NotReadableError" || name === "TrackStartError")
      return { ok: false, code: "IN_USE", message: "Your camera is being used by another app. Close the other app, then press Try again." };
    return { ok: false, code: "ERROR", message: "We couldn't start your camera. Please check your camera and microphone, then press Try again." };
  }
}

export function stopStream(stream) {
  try { stream?.getTracks().forEach(t => t.stop()); } catch { /* noop */ }
}
