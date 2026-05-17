import React, { useRef, useEffect, useState } from 'react'
import './AudioPlayer.css'

function AudioPlayer({ messages }) {
  const audioCtx = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [autoPlay, setAutoPlay] = useState(true)
  const [volume, setVolume] = useState(0.7)
  const [lastPlayed, setLastPlayed] = useState(null)
  const gainNode = useRef(null)

  useEffect(() => {
    audioCtx.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 8000 })
    gainNode.current = audioCtx.current.createGain()
    gainNode.current.connect(audioCtx.current.destination)
    gainNode.current.gain.value = volume
    return () => audioCtx.current?.close()
  }, [])

  useEffect(() => {
    if (gainNode.current) gainNode.current.gain.value = volume
  }, [volume])

  // Auto-play incoming audio
  useEffect(() => {
    if (!autoPlay || !messages.length) return
    const last = messages[messages.length - 1]
    if (last.type === 'audio' && last.data?.pcm_b64) {
      playAudio(last.data.pcm_b64, last.data)
    }
  }, [messages, autoPlay])

  const playAudio = async (pcmBase64, meta) => {
    if (!audioCtx.current) return
    if (audioCtx.current.state === 'suspended') await audioCtx.current.resume()

    try {
      const raw = atob(pcmBase64)
      const buffer = new Int16Array(raw.length / 2)
      for (let i = 0; i < buffer.length; i++) {
        buffer[i] = raw.charCodeAt(i * 2) | (raw.charCodeAt(i * 2 + 1) << 8)
      }

      const audioBuffer = audioCtx.current.createBuffer(1, buffer.length, 8000)
      const channelData = audioBuffer.getChannelData(0)
      for (let i = 0; i < buffer.length; i++) {
        channelData[i] = buffer[i] / 32768
      }

      const source = audioCtx.current.createBufferSource()
      source.buffer = audioBuffer
      source.connect(gainNode.current)
      source.onended = () => setPlaying(false)
      source.start()
      setPlaying(true)
      setLastPlayed(meta)
    } catch (e) {
      console.warn('[Audio] Playback error:', e)
    }
  }

  return (
    <div className="audio-player glass">
      <div className="audio-header">
        <span className={`audio-indicator ${playing ? 'active' : ''}`}>🔊</span>
        <span className="audio-title">Decrypted Audio</span>
      </div>
      <div className="audio-controls">
        <button
          className={`audio-btn ${autoPlay ? 'on' : ''}`}
          onClick={() => setAutoPlay(!autoPlay)}
          title="Auto-play decrypted audio"
        >
          {autoPlay ? '⏵ AUTO' : '⏸ MUTED'}
        </button>
        <input
          type="range" min="0" max="1" step="0.05"
          value={volume} onChange={e => setVolume(parseFloat(e.target.value))}
          className="audio-volume"
          title={`Volume: ${Math.round(volume * 100)}%`}
        />
        <span className="audio-vol-label">{Math.round(volume * 100)}%</span>
      </div>
      {lastPlayed && (
        <div className="audio-meta">
          <span>RID: {lastPlayed.radio_id}</span>
          <span>TG: {lastPlayed.talkgroup || '—'}</span>
          <span>{lastPlayed.protocol}</span>
        </div>
      )}
    </div>
  )
}

export default AudioPlayer
