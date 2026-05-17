import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `ws://${window.location.hostname}:4001`
const MAX_MESSAGES = 500
const RECONNECT_DELAY = 3000

export function useWebSocket() {
  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const ws = useRef(null)
  const reconnectTimeout = useRef(null)

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        setConnected(true)
        console.log('[WS] Connected')
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'connected') return
          setMessages(prev => {
            const next = [...prev, data]
            return next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next
          })
        } catch (e) {
          console.warn('[WS] Parse error:', e)
        }
      }

      ws.current.onclose = () => {
        setConnected(false)
        console.log('[WS] Disconnected, reconnecting...')
        reconnectTimeout.current = setTimeout(connect, RECONNECT_DELAY)
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    } catch (e) {
      console.error('[WS] Connection error:', e)
      reconnectTimeout.current = setTimeout(connect, RECONNECT_DELAY)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, [connect])

  return { messages, connected }
}
