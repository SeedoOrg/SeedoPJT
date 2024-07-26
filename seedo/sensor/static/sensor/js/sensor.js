let previousPrediction = 0;
let activeSendorRequests = 0;
const MAX_CONCURRENT_SENSOR_REQUESTS = 2;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

async function sendSensorData(sensorData) {
  var csrftoken = getCookie("csrftoken");
  try {
    const response = await fetch("/sensor/fall_recognition/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken,
      },
      body: JSON.stringify({ sensor_data: sensorData }),
    });

    const result = await response.json();

    previousPrediction = result.prediction;

    document.getElementById("fall_recognition").textContent = `Prediction: ${result.prediction}`;
  } catch (error) {
    console.error("Error sending sensor data:", error);
  } finally {
    activeSendorRequests--;
  }
}

class CircularBuffer {
  constructor(size) {
    this.size = size;
    this.buffer = [];
  }

  push(item) {
    if (this.buffer.length >= this.size) {
      this.buffer.shift();
    }
    this.buffer.push(item);
  }

  getBuffer() {
    return this.buffer;
  }

  getLastItem() {
    return this.buffer.length > 0 ? this.buffer[this.buffer.length - 1] : null;
  }
}

document.addEventListener("DOMContentLoaded", function () {
  let sensoring = false;
  let sensorDataBuffer = new CircularBuffer(30);
  const frameRate = 30;
  let frameticks = 0;

  var walking_mode = localStorage.getItem("walking_mode");
  if (walking_mode === "true") {
    startSensoring();
  }

  // frame 구간별 센서 데이터 전송
  function maybeSendSensorData() {
    if (activeSendorRequests < MAX_CONCURRENT_SENSOR_REQUESTS) {
      if (sensorDataBuffer.getBuffer().length >= 30) {
        const sensorData = sensorDataBuffer.getBuffer();
        if (frameticks % 15 === 0) {
          activeSendorRequests++;
          sendSensorData(sensorData);
        }
      }
    }
  }

  function createNewFrame() {
    return {
      timestamp: Date.now(),
      gps: { latitude: null, longitude: null },
      acc: { x: null, y: null, z: null },
      gyro: { alpha: null, beta: null, gamma: null },
    };
  }

  async function updateSensorData(event) {
    if (sensoring) {
      frameticks++;
      const frame = createNewFrame();

      try {
        await Promise.all([updateGPS(frame), Promise.resolve(frame)]);

        // 가속도 센서값 업데이트
        try {
          if (event.acceleration && event.acceleration !== undefined) {
            let accel = event.acceleration;
            frame.acc = {
              x: accel.x || 0,
              y: accel.y || 0,
              z: accel.z || 0,
            };
            document.getElementById("accelerometer").textContent = `Accelerometer: x=${accel.x.toFixed(2)}, y=${accel.y.toFixed(2)}, z=${accel.z.toFixed(2)}`;
          } else {
            const lastItem = sensorDataBuffer.getLastItem();
            frame.acc = lastItem ? lastItem.acc : { x: 0, y: 0, z: 0 };
            document.getElementById("accelerometer").textContent = `Accelerometer: x=${frame.acc.x.toFixed(
              2,
            )}, y=${frame.acc.y.toFixed(2)}, z=${frame.acc.z.toFixed(2)}`;
          }
        } catch (error) {
          const lastItem = sensorDataBuffer.getLastItem();
          frame.acc = lastItem ? lastItem.acc : { x: 0, y: 0, z: 0 };
          document.getElementById("accelerometer").textContent = `Accelerometer: x=${frame.acc.x.toFixed(
            2,
          )}, y=${frame.acc.y.toFixed(2)}, z=${frame.acc.z.toFixed(2)}`;
        }

        // 자이로 센서값 업데이트
        try {
          if (event.alpha !== null && event.alpha !== undefined) {
            frame.gyro = {
              alpha: event.alpha || 0,
              beta: event.beta || 0,
              gamma: event.gamma || 0,
            };
            document.getElementById("gyroscope").textContent = `Gyroscope: alpha=${event.alpha.toFixed(
              2,
            )}, beta=${event.beta.toFixed(2)}, gamma=${event.gamma.toFixed(2)}`;
          } else {
            const lastItem = sensorDataBuffer.getLastItem();
            frame.gyro = lastItem ? lastItem.gyro : { alpha: 0, beta: 0, gamma: 0 };
            document.getElementById("gyroscope").textContent = `Gyroscope: alpha=${frame.gyro.alpha.toFixed(2)}, beta=${frame.gyro.beta.toFixed(
              2,
            )}, gamma=${frame.gyro.gamma.toFixed(2)}`;
          }
        } catch (error) {
          const lastItem = sensorDataBuffer.getLastItem();
          frame.gyro = lastItem ? lastItem.gyro : { alpha: 0, beta: 0, gamma: 0 };
          document.getElementById("gyroscope").textContent = `Gyroscope: alpha=${frame.gyro.alpha.toFixed(2)}, beta=${frame.gyro.beta.toFixed(
            2,
          )}, gamma=${frame.gyro.gamma.toFixed(2)}`;
        }

        sensorDataBuffer.push(frame);
        maybeSendSensorData();
      } catch (error) {
        console.error("Error updating sensor data:", error);
      }
    }
  }

  function updateGPS(frame) {
    return new Promise((resolve) => {
      if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
          function (position) {
            frame.gps = {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
            };
            document.getElementById("location").textContent = `Location: Latitude ${position.coords.latitude}, Longitude ${position.coords.longitude}`;
            resolve();
          },
          function (error) {
            frame.gps = { latitude: 0, longitude: 0 };
            document.getElementById("location").textContent = `Location: Latitude 0, Longitude 0`;
            resolve();
          },
        );
      } else {
        console.error("Geolocation not supported");
        frame.gps = { latitude: 0, longitude: 0 };
        resolve();
      }
    });
  }

  function startSensoring() {
    sensoring = true;
    var sensoringStatusElement = document.getElementById("sensoring-status");

    if (sensoringStatusElement) {
      sensoringStatusElement.textContent = "Sensoring...";
    }

    if (window.DeviceMotionEvent) {
      window.addEventListener("devicemotion", updateSensorData);
    } else {
      console.error("Accelerometer not supported");
    }

    if (window.DeviceOrientationEvent) {
      window.addEventListener("deviceorientation", updateSensorData);
    } else {
      console.error("Gyroscope not supported");
    }

    setInterval(updateSensorData, 1000 / frameRate);
  }

  function stopSensoring() {
    frameticks = 0;
    sensoring = false;
    document.getElementById("sensoring-status").textContent = "Sensoring stopped.";
    window.removeEventListener("devicemotion", updateSensorData);
    window.removeEventListener("deviceorientation", updateSensorData);
  }

  var startSensorButton = document.getElementById("start-sensor");
  if (startSensorButton) {
    startSensorButton.addEventListener("click", startSensoring);
  }

  var stopSensor = document.getElementById("stop-sensor");
  if (stopSensor) {
    stopSensor.addEventListener("click", stopSensoring);
  }
});
