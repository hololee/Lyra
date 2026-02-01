import axios from 'axios';
import { AlertCircle, Lock, Settings as SettingsIcon, Unlock } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { decrypt } from '../utils/crypto';

export default function TerminalPage() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termInstance = useRef<Terminal | null>(null);
  const fitAddonInstance = useRef<FitAddon | null>(null);
  const wsInstance = useRef<WebSocket | null>(null);

  const [isUnlocked, setIsUnlocked] = useState(false);
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null); // null means loading
  const [masterPassword, setMasterPassword] = useState('');
  const [error, setError] = useState('');
  const [authMethod, setAuthMethod] = useState<string | null>(null);

  // Check auth method and configuration first
  useEffect(() => {
    const checkAuth = async () => {
        try {
            const [methodRes, userRes] = await Promise.all([
                axios.get('settings/ssh_auth_method'),
                axios.get('settings/ssh_username')
            ]);

            const method = methodRes.data.value;
            const username = userRes.data.value;

            if (!username) {
                setIsConfigured(false);
                return;
            }

            setAuthMethod(method);
            setIsConfigured(true);

            if (method !== 'key') {
                setIsUnlocked(true); // Don't need password if not using key
            }
        } catch {
            setIsConfigured(false);
        }
    };
    checkAuth();
  }, []);

  useEffect(() => {
    if (!isUnlocked || !terminalRef.current || isConfigured === false) return;

    // Initialize Terminal
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: '"JetBrains Mono", "Fira Code", monospace',
      fontSize: 14,
      theme: {
        background: '#000000',
        foreground: '#ffffff',
        cursor: '#4ade80',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(terminalRef.current);
    fitAddon.fit();

    termInstance.current = term;
    fitAddonInstance.current = fitAddon;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = import.meta.env.DEV
        ? 'ws://localhost:8000/api/terminal/ws'
        : `${protocol}//${window.location.host}/api/terminal/ws`;

    const ws = new WebSocket(wsUrl);
    wsInstance.current = ws;

    ws.binaryType = 'blob';

    ws.onopen = async () => {
        term.write('\r\n\x1b[32m[Connected to Terminal Service]\x1b[0m\r\n');

        let privateKey = '';
        if (authMethod === 'key') {
            const encrypted = localStorage.getItem('ssh_private_key_encrypted');
            if (!encrypted) {
                term.write('\r\n\x1b[31m[Error: SSH Key not found in browser storage. Please select key in Settings.]\x1b[0m\r\n');
                ws.close();
                return;
            }
            try {
                privateKey = await decrypt(encrypted, masterPassword);
                term.write('\x1b[32m[Key Decrypted Successfully]\x1b[0m\r\n');
            } catch {
                term.write('\r\n\x1b[31m[Decryption Failed: Invalid Passphrase]\x1b[0m\r\n');
                ws.close();
                return;
            }
        }

        const initData = {
            type: 'INIT',
            privateKey: privateKey,
            rows: term.rows,
            cols: term.cols
        };
        ws.send(JSON.stringify(initData));
    };

    ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
             term.write(event.data);
        } else {
            const reader = new FileReader();
            reader.onload = () => {
                term.write(reader.result as string);
            };
            reader.readAsText(event.data);
        }
    };

    ws.onclose = () => {
        term.write('\r\n\x1b[31m[Connection Closed]\x1b[0m\r\n');
    };

    term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(data);
        }
    });

    const handleResize = () => {
        fitAddon.fit();
        if (ws.readyState === WebSocket.OPEN) {
             ws.send(`RESIZE:${term.rows},${term.cols}`);
        }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      ws.close();
      term.dispose();
    };
  }, [isUnlocked, isConfigured, authMethod, masterPassword]);

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    if (!masterPassword) {
        setError('Please enter your master passphrase.');
        return;
    }
    setError('');
    setIsUnlocked(true);
  };

  if (isConfigured === null) {
      return (
          <div className="h-full flex items-center justify-center bg-[#18181b]">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          </div>
      );
  }

  if (isConfigured === false) {
      return (
          <div className="h-full flex items-center justify-center bg-[#18181b] p-6">
              <div className="max-w-md w-full bg-[#27272a] rounded-2xl border border-[#3f3f46] p-8 shadow-2xl">
                  <div className="flex flex-col items-center text-center space-y-6">
                      <div className="w-20 h-20 bg-amber-500/10 rounded-full flex items-center justify-center text-amber-500">
                          <AlertCircle size={48} />
                      </div>
                      <div className="space-y-2">
                        <h2 className="text-2xl font-bold text-white">Setup Required</h2>
                        <p className="text-gray-400">Host server connection is not configured yet. Please provide SSH details in the settings.</p>
                      </div>
                      <Link
                        to="/settings"
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
                      >
                        <SettingsIcon size={20} />
                        Go to Settings
                      </Link>
                  </div>
              </div>
          </div>
      );
  }

  if (!isUnlocked) {
    return (
        <div className="h-full flex items-center justify-center bg-[#18181b] p-6">
            <div className="max-w-md w-full bg-[#27272a] rounded-2xl border border-[#3f3f46] p-8 shadow-2xl">
                <div className="flex flex-col items-center text-center space-y-4">
                    <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center text-blue-400 mb-2">
                        <Lock size={32} />
                    </div>
                    <h2 className="text-2xl font-bold text-white">Terminal Locked</h2>
                    <p className="text-gray-400">Enter your master passphrase to decrypt your SSH key and connect.</p>

                    <form onSubmit={handleUnlock} className="w-full space-y-4 mt-6">
                        <div className="relative">
                            <input
                                type="password"
                                autoFocus
                                value={masterPassword}
                                onChange={(e) => setMasterPassword(e.target.value)}
                                placeholder="Master Passphrase"
                                className="w-full bg-[#18181b] border border-[#3f3f46] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-all pl-11"
                            />
                            <Unlock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
                        </div>

                        {error && (
                            <div className="flex items-center gap-2 text-red-400 text-sm">
                                <AlertCircle size={16} />
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
                        >
                            <Unlock size={18} />
                            Unlock & Connect
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
  }

  return (
    <div className="p-8 h-full flex flex-col space-y-8 bg-[#18181b]">
      <header className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-white">Terminal</h2>
          <p className="text-gray-400 mt-1">Direct access to host shell via SSH</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 bg-[#27272a] px-3 py-1.5 rounded-full border border-[#3f3f46]">
          <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
          Connected via WebSocket
        </div>
      </header>
       <div className="flex-1 bg-black rounded-xl border border-[#3f3f46] p-2 overflow-hidden shadow-2xl ring-1 ring-white/5">
         <div ref={terminalRef} className="w-full h-full" />
       </div>
    </div>
  );
}
