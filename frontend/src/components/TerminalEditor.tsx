"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";
import { FitAddon } from "xterm-addon-fit";
import { SearchAddon } from "xterm-addon-search";
import { WebLinksAddon } from "xterm-addon-web-links";
import { RotateCcw, Plus, Power, WifiOff } from "lucide-react";

export default function TerminalEditor() {
  const { user, isAuthenticated } = useAuth();
  const { toast } = useToastLocal();
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    initTerminal();
    return () => {
      cleanup();
    };
  }, []);

  function initTerminal() {
    const container = containerRef.current;
    if (!container) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: '"Roboto Mono", "Menlo", monospace',
      fontWeight: 400,
      letterSpacing: 0.5,
      lineHeight: 1.2,
      theme: {
        background: "#0a0a0c",
        foreground: "#e5e5e5",
        cursor: "#38bdf8",
        black: "#1f1f23",
        red: "#ef4444",
        green: "#22c55e",
        yellow: "#f59e0b",
        blue: "#38bdf8",
        magenta: "#c084fc",
        cyan: "#22d3ee",
        white: "#e5e5e5",
        brightBlack: "#4b4b50",
        brightRed: "#f87171",
        brightGreen: "#86efac",
        brightYellow: "#fbbf24",
        brightBlue: "#4fd1f8",
        brightMagenta: "#d8b4fe",
        brightCyan: "#67e8f9",
        brightWhite: "#f3f4f6",
      },
      allowProposedApi: true,
      scrollback: 5000,
      disableStdin: false,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new SearchAddon());
    term.loadAddon(new WebLinksAddon());

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    term.open(container);
    fitAddon.fit();

    container.innerHTML = "";
    container.appendChild(term.element!);

    connectWs();

    const onResize = () => {
      fitAddon.fit();
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const t = termRef.current!;
        const size = { cols: t.cols, rows: t.rows };
        wsRef.current.send(
          JSON.stringify({ type: "resize", cols: size.cols, rows: size.rows })
        );
      }
    };
    window.addEventListener("resize", onResize);

    term.onData((data) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
    });

    (termRef as any)._resizeListener = onResize;
  }

  function connectWs() {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const token = sessionStorage.getItem("tt_ws_token") || undefined;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const qs = token ? `?token=${encodeURIComponent(token)}` : "";
    const url = `${protocol}//${window.location.host}/api/terminal/ws${qs}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;
    setReconnecting(false);

    ws.onopen = () => {
      setConnected(true);
      const term = termRef.current;
      const fit = fitAddonRef.current;
      if (term && fit) {
        fit.fit();
        const t = term;
        const size = { cols: t.cols, rows: t.rows };
        ws.send(JSON.stringify({ type: "resize", cols: size.cols, rows: size.rows }));
      }
      toast({ title: "Connected", description: "Terminal session established.", type: "success" });
    };

    ws.onmessage = (e) => {
      const term = termRef.current;
      if (!term) return;
      const reader = new FileReader();
      reader.readAsArrayBuffer(e.data);
      reader.onload = () => {
        const bytes = new Uint8Array(reader.result as ArrayBuffer);
        term.write(new TextDecoder().decode(bytes));
      };
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (event.wasClean) return;
      setReconnecting(true);
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWs();
      }, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function cleanup() {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    const ws = wsRef.current;
    if (ws) ws.close();
    const term = termRef.current;
    if (term) {
      term.dispose();
      termRef.current = null;
    }
    const container = containerRef.current;
    if (container) {
      container.innerHTML = "";
    }
  }

  const sendCommand = useCallback(
    (text: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(text);
      const term = termRef.current;
      if (term) term.write(`\r\n[local] ${text}\r\n`);
    },
    []
  );

  const clearTerminal = useCallback(() => {
    const term = termRef.current;
    if (term) term.clear();
  }, []);

  const disconnect = useCallback(() => {
    const ws = wsRef.current;
    if (ws) ws.close();
    setConnected(false);
  }, []);

  return (
    <div className="flex h-full flex-col bg-[#0a0a0c]">
      <header className="h-12 border-b border-[#27272a] bg-[#0a0a0c] flex items-center justify-between px-4 shrink-0 z-10">
        <div className="flex items-center gap-2">
          <div className={`flex h-2 w-2 rounded-full ${connected ? "bg-[#22c55e] animate-pulse" : "bg-[#4b4b50]"}`} />
          <span className="text-xs font-medium text-gray-300">
            {connected ? "SESSION ACTIVE" : reconnecting ? "RECONNECTING..." : "DISCONNECTED"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={clearTerminal}
            className="btn-ghost px-3 py-1.5 text-xs border border-[#27272a] hover:border-[#38bdf8]"
            title="Clear"
          >
            <RotateCcw className="w-4 h-4" /> Clear
          </button>
          <button
            onClick={() => {
              const input = window.prompt("Send text to terminal:");
              if (input) sendCommand(input);
            }}
            className="btn-ghost px-3 py-1.5 text-xs border border-[#27272a] hover:border-[#38bdf8]"
            title="Send text"
          >
            <Plus className="w-4 h-4" /> Send
          </button>
          <button
            onClick={disconnect}
            className="btn-ghost px-3 py-1.5 text-xs border border-[#27272a] hover:border-[#ef4444] hover:text-[#ef4444]"
            title="Disconnect"
          >
            <Power className="w-4 h-4" /> Disconnect
          </button>
        </div>
      </header>

      <div className="flex-1 relative overflow-hidden">
        <div ref={containerRef} className="absolute inset-0" />
        {!connected && !reconnecting && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0a0a0c]">
            <WifiOff className="h-12 w-12 text-gray-700 mb-3" />
            <p className="text-gray-400 text-sm">Terminal disconnected. Reconnecting automatically...</p>
          </div>
        )}
      </div>

      <div className="h-8 border-t border-[#27272a] bg-[#0f0f11] flex items-center justify-between px-3 shrink-0 text-xs text-gray-500">
        <div className="flex items-center gap-3">
          <span>User: {user?.username}</span>
          <span>•</span>
          <span>Isolated container sandbox</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-[#22c55e]" : "bg-[#4b4b50]"}`} />
          <span>{connected ? "Connected" : "Disconnected"}</span>
        </div>
      </div>
    </div>
  );
}
