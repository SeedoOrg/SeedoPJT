// audio_queue.js
const soundQueue = [];
let isPlaying = false;

function playNextInQueue() {
  if (isPlaying || soundQueue.length === 0) return;

  const audioData = soundQueue.shift();
  const sound = new Howl({
    src: [audioData],
    format: ["mp3"],
    autoplay: true,
    onend: function () {
      isPlaying = false;
      playNextInQueue();
    },
  });

  isPlaying = true;
  sound.play();
}

function addToQueue(audioData) {
  soundQueue.push(audioData);
  playNextInQueue();
}

// This file needs to be included in your HTML before any other script that uses it.
